#  Copyright (c) 2025 AshokShau
#  Licensed under the GNU AGPL v3.0: https://www.gnu.org/licenses/agpl-3.0.html
#  Part of the TgMusicBot project. All rights reserved where applicable.
#  Modified by Devin - Major modifications and improvements

import asyncio
import time
from typing import Optional, List, Dict, Any, Union
from contextlib import asynccontextmanager

from cachetools import TTLCache, LRUCache
from pymongo import AsyncMongoClient, ReturnDocument
from pymongo.errors import (
    ConnectionFailure, 
    ServerSelectionTimeoutError, 
    AutoReconnect,
    DuplicateKeyError,
    BulkWriteError,
    InvalidOperation
)
from pymongo.operations import UpdateOne, InsertOne

from TgMusic.logger import LOGGER
from ._config import config


class DatabaseMetrics:
    """Performance metrics tracking for database operations."""
    
    def __init__(self):
        self.query_count = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.connection_errors = 0
        self.retry_count = 0
        self.avg_query_time = 0.0
        self._query_times = []

    def record_query(self, duration: float):
        self.query_count += 1
        self._query_times.append(duration)
        if len(self._query_times) > 100:  # Keep last 100 queries
            self._query_times.pop(0)
        self.avg_query_time = sum(self._query_times) / len(self._query_times)

    def cache_hit(self):
        self.cache_hits += 1

    def cache_miss(self):
        self.cache_misses += 1

    def connection_error(self):
        self.connection_errors += 1

    def retry(self):
        self.retry_count += 1

    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        return (self.cache_hits / total * 100) if total > 0 else 0.0

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_queries": self.query_count,
            "cache_hit_rate": f"{self.cache_hit_rate:.2f}%",
            "avg_query_time": f"{self.avg_query_time:.3f}s",
            "connection_errors": self.connection_errors,
            "retries": self.retry_count
        }


class Database:
    """High-performance database layer with advanced caching and error handling."""
    
    # Connection settings
    MAX_POOL_SIZE = 10
    MIN_POOL_SIZE = 5
    MAX_IDLE_TIME_MS = 30000
    CONNECT_TIMEOUT_MS = 5000
    SERVER_SELECTION_TIMEOUT_MS = 5000
    
    # Retry settings
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0
    BACKOFF_FACTOR = 2.0
    
    # Cache settings
    CHAT_CACHE_SIZE = 2000
    CHAT_CACHE_TTL = 1800  # 30 minutes
    BOT_CACHE_SIZE = 500
    BOT_CACHE_TTL = 3600   # 1 hour
    USER_CACHE_SIZE = 5000
    USER_CACHE_TTL = 1200  # 20 minutes

    def __init__(self):
        self._initialize_client()
        self._initialize_databases()
        self._initialize_caches()
        self.metrics = DatabaseMetrics()
        self._connection_healthy = True
        self._last_health_check = time.time()
        self._health_check_interval = 30  # seconds
        self._connection_monitor_task = None

    def _initialize_client(self):
        """Initialize MongoDB client with optimized settings."""
        self.mongo_client = AsyncMongoClient(
            config.MONGO_URI,
            maxPoolSize=self.MAX_POOL_SIZE,
            minPoolSize=self.MIN_POOL_SIZE,
            maxIdleTimeMS=self.MAX_IDLE_TIME_MS,
            connectTimeoutMS=self.CONNECT_TIMEOUT_MS,
            serverSelectionTimeoutMS=self.SERVER_SELECTION_TIMEOUT_MS,
            retryWrites=True,
            retryReads=True,
            w="majority",
            readPreference="primaryPreferred",
            heartbeatFrequencyMS=10000,
            socketTimeoutMS=20000,
        )

    def _initialize_databases(self):
        """Initialize database collections."""
        _db = self.mongo_client[config.DB_NAME]
        self.chat_db = _db["chats"]
        self.users_db = _db["users"]
        self.bot_db = _db["bot"]
        self.language = _db["language"]

    def _initialize_caches(self):
        """Initialize optimized multi-level caching."""
        # L1 Cache: Frequently accessed data (LRU)
        self.chat_cache_l1 = LRUCache(maxsize=500)
        self.bot_cache_l1 = LRUCache(maxsize=100)
        
        # L2 Cache: Time-based eviction (TTL)  
        self.chat_cache = TTLCache(maxsize=self.CHAT_CACHE_SIZE, ttl=self.CHAT_CACHE_TTL)
        self.bot_cache = TTLCache(maxsize=self.BOT_CACHE_SIZE, ttl=self.BOT_CACHE_TTL)
        self.user_cache = TTLCache(maxsize=self.USER_CACHE_SIZE, ttl=self.USER_CACHE_TTL)

    async def _reconnect_client(self):
        """Reconnect to MongoDB after connection loss."""
        try:
            LOGGER.info("Attempting to reconnect to MongoDB...")
            
            # Close existing connection if it exists
            if hasattr(self, 'mongo_client') and self.mongo_client:
                try:
                    await self.mongo_client.close()
                except Exception:
                    pass
            
            # Reinitialize client
            self._initialize_client()
            self._initialize_databases()
            
            # Test connection
            await self.mongo_client.admin.command("ping")
            
            LOGGER.info("Successfully reconnected to MongoDB")
            self._connection_healthy = True
            self._last_health_check = time.time()
            
        except Exception as e:
            LOGGER.error(f"Failed to reconnect to MongoDB: {e}")
            self._connection_healthy = False
            raise

    async def _execute_with_retry(self, operation, *args, **kwargs):
        """Execute database operation with exponential backoff retry."""
        delay = self.RETRY_DELAY
        
        for attempt in range(self.MAX_RETRIES):
            try:
                start_time = time.time()
                result = await operation(*args, **kwargs)
                duration = time.time() - start_time
                self.metrics.record_query(duration)
                return result
                
            except (ConnectionFailure, ServerSelectionTimeoutError, AutoReconnect, InvalidOperation) as e:
                self.metrics.connection_error()
                self.metrics.retry()
                self._connection_healthy = False
                
                # Handle InvalidOperation (client closed)
                if isinstance(e, InvalidOperation) and "after close" in str(e):
                    LOGGER.warning("Database client was closed, attempting to reconnect...")
                    await self._reconnect_client()
                
                if attempt == self.MAX_RETRIES - 1:
                    LOGGER.error(f"Database operation failed after {self.MAX_RETRIES} attempts: {e}")
                    raise RuntimeError(f"Database operation failed: {str(e)}") from e
                
                LOGGER.warning(f"Database operation failed (attempt {attempt + 1}), retrying in {delay}s: {e}")
                await asyncio.sleep(delay)
                delay *= self.BACKOFF_FACTOR
                
            except Exception as e:
                LOGGER.error(f"Unexpected database error: {e}", exc_info=True)
                raise

    async def _check_connection_health(self):
        """Periodically check database connection health."""
        while True:
            try:
                await asyncio.sleep(self._health_check_interval)
                await self.mongo_client.admin.command("ping")
                self._connection_healthy = True
                self._last_health_check = time.time()
            except Exception as e:
                self._connection_healthy = False
                LOGGER.warning(f"Database health check failed: {e}")

    async def ping(self) -> None:
        """Test database connectivity with enhanced error handling."""
        try:
            await self._execute_with_retry(self.mongo_client.admin.command, "ping")
            LOGGER.info("Database connection completed successfully.")
            
            # Start connection monitoring
            if not self._connection_monitor_task:
                self._connection_monitor_task = asyncio.create_task(self._check_connection_health())
                
        except Exception as e:
            LOGGER.error("Database ping failed: %s", e)
            raise RuntimeError(f"Database connection failed: {str(e)}") from e

    async def get_chat(self, chat_id: int) -> Optional[dict]:
        """Get chat with multi-level caching and optimized queries."""
        # Check L1 cache first (fastest)
        if chat_id in self.chat_cache_l1:
            self.metrics.cache_hit()
            return self.chat_cache_l1[chat_id]
        
        # Check L2 cache
        if chat_id in self.chat_cache:
            self.metrics.cache_hit()
            chat_data = self.chat_cache[chat_id]
            self.chat_cache_l1[chat_id] = chat_data  # Promote to L1
            return chat_data
        
        self.metrics.cache_miss()
        
        try:
            chat = await self._execute_with_retry(
                self.chat_db.find_one, 
                {"_id": chat_id},
                {"_id": 1, "play_type": 1, "assistant": 1, "auth_users": 1, "buttons": 1, "thumb": 1}
            )
            
            if chat:
                self.chat_cache[chat_id] = chat
                self.chat_cache_l1[chat_id] = chat
            
            return chat
            
        except (RuntimeError, InvalidOperation) as e:
            LOGGER.warning("Database error getting chat %s: %s", chat_id, e)
            return None
        except Exception as e:
            LOGGER.error("Unexpected error getting chat %s: %s", chat_id, e)
            return None

    async def add_chat(self, chat_id: int) -> None:
        """Add chat with optimized upsert and caching."""
        if await self.get_chat(chat_id) is None:
            try:
                await self._execute_with_retry(
                    self.chat_db.update_one,
                    {"_id": chat_id}, 
                    {"$setOnInsert": {"created_at": time.time()}}, 
                    upsert=True
                )
                
                # Update cache
                new_chat = {"_id": chat_id, "created_at": time.time()}
                self.chat_cache[chat_id] = new_chat
                self.chat_cache_l1[chat_id] = new_chat
                
                LOGGER.info("Added chat: %s", chat_id)
                
            except DuplicateKeyError:
                pass  # Chat already exists
            except (RuntimeError, InvalidOperation) as e:
                LOGGER.warning("Database error adding chat %s: %s", chat_id, e)
            except Exception as e:
                LOGGER.error("Unexpected error adding chat %s: %s", chat_id, e)

    async def _update_chat_field(self, chat_id: int, key: str, value: Any) -> None:
        """Update chat field with optimized caching strategy."""
        try:
            await self._execute_with_retry(
                self.chat_db.update_one,
                {"_id": chat_id}, 
                {"$set": {key: value}}, 
                upsert=True
            )
            
            # Update all cache levels
            for cache in [self.chat_cache, self.chat_cache_l1]:
                if chat_id in cache:
                    cache[chat_id][key] = value
                else:
                    cache[chat_id] = {key: value}
                    
        except (RuntimeError, InvalidOperation) as e:
            LOGGER.warning("Database error updating chat field %s for %s: %s", key, chat_id, e)
        except Exception as e:
            LOGGER.error("Unexpected error updating chat field %s for %s: %s", key, chat_id, e)

    async def get_play_type(self, chat_id: int) -> int:
        chat = await self.get_chat(chat_id)
        return chat.get("play_type", 0) if chat else 0

    async def set_play_type(self, chat_id: int, play_type: int) -> None:
        await self._update_chat_field(chat_id, "play_type", play_type)

    async def get_assistant(self, chat_id: int) -> Optional[str]:
        chat = await self.get_chat(chat_id)
        return chat.get("assistant") if chat else None

    async def set_assistant(self, chat_id: int, assistant: str) -> None:
        await self._update_chat_field(chat_id, "assistant", assistant)

    async def bulk_update_chats(self, updates: List[Dict[str, Any]]) -> int:
        """Perform bulk chat updates for better performance."""
        if not updates:
            return 0
            
        try:
            operations = [
                UpdateOne(
                    {"_id": update["chat_id"]},
                    {"$set": update["data"]},
                    upsert=True
                ) for update in updates
            ]
            
            result = await self._execute_with_retry(
                self.chat_db.bulk_write,
                operations,
                ordered=False
            )
            
            # Update cache for successful operations
            for update in updates:
                chat_id = update["chat_id"]
                for cache in [self.chat_cache, self.chat_cache_l1]:
                    if chat_id in cache:
                        cache[chat_id].update(update["data"])
            
            LOGGER.info("Bulk updated %d chats", result.modified_count)
            return result.modified_count
            
        except BulkWriteError as e:
            LOGGER.error("Bulk write error: %s", e.details)
            return 0
        except Exception as e:
            LOGGER.error("Error in bulk update: %s", e)
            return 0

    async def clear_all_assistants(self) -> int:
        """Clear all assistants with optimized bulk operation."""
        try:
            result = await self._execute_with_retry(
                self.chat_db.update_many,
                {"assistant": {"$exists": True}}, 
                {"$unset": {"assistant": ""}}
            )

            # Clear from all cache levels
            for cache in [self.chat_cache, self.chat_cache_l1]:
                for chat_id in list(cache.keys()):
                    if isinstance(cache[chat_id], dict) and "assistant" in cache[chat_id]:
                        cache[chat_id]["assistant"] = None

            LOGGER.info(f"Cleared assistants from {result.modified_count} chats")
            return result.modified_count
            
        except Exception as e:
            LOGGER.error("Error clearing assistants: %s", e)
            return 0

    async def remove_assistant(self, chat_id: int) -> None:
        await self._update_chat_field(chat_id, "assistant", None)

    async def add_auth_user(self, chat_id: int, auth_user: int) -> None:
        """Add authorized user with atomic operation."""
        try:
            await self._execute_with_retry(
                self.chat_db.update_one,
                {"_id": chat_id}, 
                {"$addToSet": {"auth_users": auth_user}}, 
                upsert=True
            )
            
            # Update cache
            for cache in [self.chat_cache, self.chat_cache_l1]:
                if chat_id in cache:
                    auth_users = cache[chat_id].get("auth_users", [])
                    if auth_user not in auth_users:
                        auth_users.append(auth_user)
                        cache[chat_id]["auth_users"] = auth_users
                        
        except Exception as e:
            LOGGER.error("Error adding auth user %s to %s: %s", auth_user, chat_id, e)

    async def remove_auth_user(self, chat_id: int, auth_user: int) -> None:
        """Remove authorized user with atomic operation."""
        try:
            await self._execute_with_retry(
                self.chat_db.update_one,
                {"_id": chat_id}, 
                {"$pull": {"auth_users": auth_user}}
            )
            
            # Update cache
            for cache in [self.chat_cache, self.chat_cache_l1]:
                if chat_id in cache and "auth_users" in cache[chat_id]:
                    auth_users = cache[chat_id]["auth_users"]
                    if auth_user in auth_users:
                        auth_users.remove(auth_user)
                        cache[chat_id]["auth_users"] = auth_users
                        
        except Exception as e:
            LOGGER.error("Error removing auth user %s from %s: %s", auth_user, chat_id, e)

    async def reset_auth_users(self, chat_id: int) -> None:
        await self._update_chat_field(chat_id, "auth_users", [])

    async def get_auth_users(self, chat_id: int) -> list[int]:
        chat = await self.get_chat(chat_id)
        return chat.get("auth_users", []) if chat else []

    async def is_auth_user(self, chat_id: int, user_id: int) -> bool:
        return user_id in await self.get_auth_users(chat_id)

    async def set_buttons_status(self, chat_id: int, status: bool) -> None:
        await self._update_chat_field(chat_id, "buttons", status)

    async def get_buttons_status(self, chat_id: int) -> bool:
        chat = await self.get_chat(chat_id)
        return chat.get("buttons", True) if chat else True

    async def set_thumbnail_status(self, chat_id: int, status: bool) -> None:
        await self._update_chat_field(chat_id, "thumb", status)

    async def get_thumbnail_status(self, chat_id: int) -> bool:
        chat = await self.get_chat(chat_id)
        return chat.get("thumb", True) if chat else True

    async def remove_chat(self, chat_id: int) -> None:
        """Remove chat with cache cleanup."""
        try:
            await self._execute_with_retry(
                self.chat_db.delete_one, 
                {"_id": chat_id}
            )
            
            # Remove from all cache levels
            self.chat_cache.pop(chat_id, None)
            self.chat_cache_l1.pop(chat_id, None)
            
        except Exception as e:
            LOGGER.error("Error removing chat %s: %s", chat_id, e)

    async def add_user(self, user_id: int) -> None:
        """Add user with caching."""
        if user_id not in self.user_cache:
            try:
                await self._execute_with_retry(
                    self.users_db.update_one,
                    {"_id": user_id}, 
                    {"$setOnInsert": {"created_at": time.time()}}, 
                    upsert=True
                )
                self.user_cache[user_id] = True
                
            except Exception as e:
                LOGGER.error("Error adding user %s: %s", user_id, e)

    async def remove_user(self, user_id: int) -> None:
        """Remove user with cache cleanup."""
        try:
            await self._execute_with_retry(
                self.users_db.delete_one, 
                {"_id": user_id}
            )
            self.user_cache.pop(user_id, None)
            
        except Exception as e:
            LOGGER.error("Error removing user %s: %s", user_id, e)

    async def is_user_exist(self, user_id: int) -> bool:
        """Check user existence with caching."""
        if user_id in self.user_cache:
            self.metrics.cache_hit()
            return True
            
        self.metrics.cache_miss()
        try:
            exists = await self._execute_with_retry(
                self.users_db.find_one, 
                {"_id": user_id}
            ) is not None
            
            if exists:
                self.user_cache[user_id] = True
            return exists
            
        except Exception as e:
            LOGGER.error("Error checking user existence %s: %s", user_id, e)
            return False

    async def get_all_users(self) -> List[int]:
        """Get all users with optimized projection."""
        try:
            return [
                user["_id"] async for user in 
                self.users_db.find({}, {"_id": 1})
            ]
        except Exception as e:
            LOGGER.error("Error getting all users: %s", e)
            return []

    async def get_all_chats(self) -> List[int]:
        """Get all chats with optimized projection."""
        try:
            return [
                chat["_id"] async for chat in 
                self.chat_db.find({}, {"_id": 1})
            ]
        except Exception as e:
            LOGGER.error("Error getting all chats: %s", e)
            return []

    async def get_logger_status(self, bot_id: int) -> bool:
        """Get logger status with optimized caching."""
        # Check L1 cache
        if bot_id in self.bot_cache_l1:
            self.metrics.cache_hit()
            return self.bot_cache_l1[bot_id].get("logger", False)
        
        # Check L2 cache
        if bot_id in self.bot_cache:
            self.metrics.cache_hit()
            status = self.bot_cache[bot_id].get("logger", False)
            self.bot_cache_l1[bot_id] = {"logger": status}
            return status

        self.metrics.cache_miss()
        try:
            bot_data = await self._execute_with_retry(
                self.bot_db.find_one,
                {"_id": bot_id},
                {"logger": 1}
            )
            status = bot_data.get("logger", False) if bot_data else False

            # Update both cache levels
            cache_data = {"logger": status}
            self.bot_cache[bot_id] = cache_data
            self.bot_cache_l1[bot_id] = cache_data

            return status
            
        except Exception as e:
            LOGGER.error("Error getting logger status for %s: %s", bot_id, e)
            return False

    async def set_logger_status(self, bot_id: int, status: bool) -> None:
        """Set logger status with cache update."""
        try:
            await self._execute_with_retry(
                self.bot_db.update_one,
                {"_id": bot_id}, 
                {"$set": {"logger": status}}, 
                upsert=True
            )

            # Update both cache levels
            cache_data = {"logger": status}
            self.bot_cache[bot_id] = cache_data
            self.bot_cache_l1[bot_id] = cache_data
            
        except Exception as e:
            LOGGER.error("Error setting logger status for %s: %s", bot_id, e)

    async def get_auto_end(self, bot_id: int) -> bool:
        """Get auto-end status with caching."""
        # Check L1 cache
        if bot_id in self.bot_cache_l1:
            self.metrics.cache_hit()
            return self.bot_cache_l1[bot_id].get("auto_end", True)
        
        # Check L2 cache
        if bot_id in self.bot_cache:
            self.metrics.cache_hit()
            status = self.bot_cache[bot_id].get("auto_end", True)
            self.bot_cache_l1[bot_id] = {"auto_end": status}
            return status

        self.metrics.cache_miss()
        try:
            bot_data = await self._execute_with_retry(
                self.bot_db.find_one,
                {"_id": bot_id},
                {"auto_end": 1}
            )
            status = bot_data.get("auto_end", True) if bot_data else True

            # Update cache
            cache_data = {"auto_end": status}
            self.bot_cache[bot_id] = cache_data
            self.bot_cache_l1[bot_id] = cache_data

            return status
            
        except Exception as e:
            LOGGER.error("Error getting auto_end status for %s: %s", bot_id, e)
            return True

    async def set_auto_end(self, bot_id: int, status: bool) -> None:
        """Set auto-end status with cache update."""
        try:
            await self._execute_with_retry(
                self.bot_db.update_one,
                {"_id": bot_id}, 
                {"$set": {"auto_end": status}}, 
                upsert=True
            )
            
            # Update cache
            cache_data = {"auto_end": status}
            self.bot_cache[bot_id] = cache_data
            self.bot_cache_l1[bot_id] = cache_data
            
        except Exception as e:
            LOGGER.error("Error setting auto_end status for %s: %s", bot_id, e)

    async def get_database_stats(self) -> Dict[str, Any]:
        """Get comprehensive database statistics."""
        try:
            stats = {
                "connection_healthy": self._connection_healthy,
                "last_health_check": self._last_health_check,
                **self.metrics.get_stats(),
                "cache_sizes": {
                    "chat_l1": len(self.chat_cache_l1),
                    "chat_l2": len(self.chat_cache),
                    "bot_l1": len(self.bot_cache_l1),
                    "bot_l2": len(self.bot_cache),
                    "user": len(self.user_cache),
                },
                "collections": {
                    "chats": await self.chat_db.estimated_document_count(),
                    "users": await self.users_db.estimated_document_count(),
                    "bots": await self.bot_db.estimated_document_count(),
                }
            }
            return stats
            
        except Exception as e:
            LOGGER.error("Error getting database stats: %s", e)
            return {"error": str(e)}

    async def optimize_database(self) -> None:
        """Perform database optimization tasks."""
        try:
            # Create indexes for better performance
            await self._execute_with_retry(
                self.chat_db.create_index, [("assistant", 1)]
            )
            await self._execute_with_retry(
                self.chat_db.create_index, [("auth_users", 1)]
            )
            await self._execute_with_retry(
                self.users_db.create_index, [("created_at", 1)]
            )
            
            LOGGER.info("Database optimization completed")
            
        except Exception as e:
            LOGGER.error("Error optimizing database: %s", e)

    async def close(self) -> None:
        """Close database connection with cleanup."""
        try:
            # Cancel monitoring task
            if self._connection_monitor_task:
                self._connection_monitor_task.cancel()
                try:
                    await self._connection_monitor_task
                except asyncio.CancelledError:
                    pass
            
            # Clear caches
            self.chat_cache.clear()
            self.chat_cache_l1.clear()
            self.bot_cache.clear()
            self.bot_cache_l1.clear()
            self.user_cache.clear()
            
            # Close connection
            await self.mongo_client.close()
            
            LOGGER.info("Database connection closed successfully.")
            LOGGER.info("Final stats: %s", self.metrics.get_stats())
            
        except Exception as e:
            LOGGER.error("Error closing database: %s", e)

    async def get_user_language(self, user_id: int) -> Optional[dict]:
        """Get user's language preference."""
        try:
            return await self._execute_with_retry(
                self.users_db.find_one,
                {"_id": user_id},
                {"language": 1}
            )
        except Exception as e:
            LOGGER.error("Error getting user language for %s: %s", user_id, e)
            return None

    async def set_user_language(self, user_id: int, language: str) -> None:
        """Set user's language preference."""
        try:
            await self._execute_with_retry(
                self.users_db.update_one,
                {"_id": user_id},
                {"$set": {"language": language}},
                upsert=True
            )
            
            # Update cache
            if user_id in self.user_cache:
                self.user_cache[user_id]["language"] = language
                
        except Exception as e:
            LOGGER.error("Error setting user language for %s: %s", user_id, e)

    async def get_chat_language(self, chat_id: int) -> str:
        """Get chat's language preference."""
        try:
            chat_data = await self._execute_with_retry(
                self.chat_db.find_one,
                {"_id": chat_id},
                {"language": 1}
            )
            return chat_data.get("language", "en-US") if chat_data else "en-US"
        except Exception as e:
            LOGGER.error("Error getting chat language for %s: %s", chat_id, e)
            return "en-US"

    async def set_chat_language(self, chat_id: int, language: str) -> None:
        """Set chat's language preference."""
        try:
            await self._execute_with_retry(
                self.chat_db.update_one,
                {"_id": chat_id},
                {"$set": {"language": language}},
                upsert=True
            )
            
            # Update cache
            if chat_id in self.chat_cache:
                self.chat_cache[chat_id]["language"] = language
                
        except Exception as e:
            LOGGER.error("Error setting chat language for %s: %s", chat_id, e)

    async def update_chat_activity(self, chat_id: int) -> None:
        """Update chat's last activity timestamp."""
        try:
            current_time = time.time()
            await self._execute_with_retry(
                self.chat_db.update_one,
                {"_id": chat_id},
                {"$set": {"last_activity": current_time}},
                upsert=True
            )
            
            # Update cache
            if chat_id in self.chat_cache:
                self.chat_cache[chat_id]["last_activity"] = current_time
                
        except Exception as e:
            LOGGER.error("Error updating chat activity for %s: %s", chat_id, e)

    async def get_chat_last_activity(self, chat_id: int) -> Optional[float]:
        """Get chat's last activity timestamp."""
        try:
            chat_data = await self._execute_with_retry(
                self.chat_db.find_one,
                {"_id": chat_id},
                {"last_activity": 1}
            )
            return chat_data.get("last_activity") if chat_data else None
        except Exception as e:
            LOGGER.error("Error getting chat last activity for %s: %s", chat_id, e)
            return None

    async def get_inactive_chats(self, max_inactive_days: int = 7) -> List[int]:
        """Get list of chats that have been inactive for more than specified days."""
        try:
            cutoff_time = time.time() - (max_inactive_days * 24 * 3600)  # Convert days to seconds
            
            cursor = self.chat_db.find(
                {"last_activity": {"$lt": cutoff_time}},
                {"_id": 1}
            )
            
            inactive_chats = []
            async for doc in cursor:
                inactive_chats.append(doc["_id"])
            
            return inactive_chats
            
        except Exception as e:
            LOGGER.error("Error getting inactive chats: %s", e)
            return []

    async def get_chat_activity_stats(self) -> Dict[str, Any]:
        """Get chat activity statistics."""
        try:
            current_time = time.time()
            one_week_ago = current_time - (7 * 24 * 3600)
            one_day_ago = current_time - (24 * 3600)
            
            # Count chats active in different time periods
            total_chats = await self._execute_with_retry(
                self.chat_db.count_documents, {}
            )
            
            active_last_week = await self._execute_with_retry(
                self.chat_db.count_documents,
                {"last_activity": {"$gte": one_week_ago}}
            )
            
            active_last_day = await self._execute_with_retry(
                self.chat_db.count_documents,
                {"last_activity": {"$gte": one_day_ago}}
            )
            
            inactive_chats = await self._execute_with_retry(
                self.chat_db.count_documents,
                {"last_activity": {"$lt": one_week_ago}}
            )
            
            return {
                "total_chats": total_chats,
                "active_last_week": active_last_week,
                "active_last_day": active_last_day,
                "inactive_over_week": inactive_chats,
                "current_time": current_time
            }
            
        except Exception as e:
            LOGGER.error("Error getting chat activity stats: %s", e)
            return {"error": str(e)}


db: Database = Database()

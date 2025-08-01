#  Copyright (c) 2025 AshokShau
#  Licensed under the GNU AGPL v3.0: https://www.gnu.org/licenses/agpl-3.0.html
#  Part of the TgMusicBot project. All rights reserved where applicable.

import asyncio
import time
from collections import deque
from typing import Any, Optional, TypeAlias, Union, Dict, List
from dataclasses import dataclass, field

from cachetools import TTLCache, LRUCache
from pytdbot import types

from TgMusic.core._dataclass import CachedTrack
from TgMusic.logger import LOGGER

@dataclass
class CacheMetrics:
    """Performance metrics for cache operations."""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    clears: int = 0
    errors: int = 0
    avg_access_time: float = 0.0
    _access_times: List[float] = field(default_factory=list)

    def record_hit(self, access_time: float = 0.0):
        self.hits += 1
        self._record_access_time(access_time)

    def record_miss(self, access_time: float = 0.0):
        self.misses += 1
        self._record_access_time(access_time)

    def record_set(self):
        self.sets += 1

    def record_delete(self):
        self.deletes += 1

    def record_clear(self):
        self.clears += 1

    def record_error(self):
        self.errors += 1

    def _record_access_time(self, access_time: float):
        if access_time > 0:
            self._access_times.append(access_time)
            if len(self._access_times) > 100:  # Keep last 100 accesses
                self._access_times.pop(0)
            self.avg_access_time = sum(self._access_times) / len(self._access_times)

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0

    def get_stats(self) -> Dict[str, Any]:
        return {
            "hit_rate": f"{self.hit_rate:.2f}%",
            "total_operations": self.hits + self.misses + self.sets + self.deletes,
            "hits": self.hits,
            "misses": self.misses,
            "sets": self.sets,
            "deletes": self.deletes,
            "clears": self.clears,
            "errors": self.errors,
            "avg_access_time": f"{self.avg_access_time:.4f}s",
        }


class OptimizedCache:
    """High-performance multi-level cache with metrics and automatic cleanup."""
    
    def __init__(
        self,
        l1_maxsize: int = 500,
        l2_maxsize: int = 2000,
        l2_ttl: int = 1800,
        cleanup_interval: int = 300,
    ):
        # L1: Fast LRU cache for frequently accessed items
        self._l1_cache = LRUCache(maxsize=l1_maxsize)
        
        # L2: TTL cache for larger storage with expiration
        self._l2_cache = TTLCache(maxsize=l2_maxsize, ttl=l2_ttl)
        
        # Thread safety
        self._lock = asyncio.Lock()
        
        # Metrics tracking
        self.metrics = CacheMetrics()
        
        # Cleanup task
        self._cleanup_interval = cleanup_interval
        self._cleanup_task = None
        self._stopped = False

    async def start_cleanup_task(self):
        """Start the automatic cleanup task."""
        if not self._cleanup_task:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self):
        """Periodically clean up expired entries and optimize cache."""
        while not self._stopped:
            try:
                await asyncio.sleep(self._cleanup_interval)
                await self._cleanup()
            except asyncio.CancelledError:
                break
            except Exception as e:
                LOGGER.error("Error in cache cleanup: %s", e)
                self.metrics.record_error()

    async def _cleanup(self):
        """Perform cache cleanup and optimization."""
        async with self._lock:
            try:
                # Force TTL cache cleanup
                expired_keys = []
                current_time = time.time()
                
                # Check L2 cache for manual cleanup if needed
                for key in list(self._l2_cache.keys()):
                    if key in self._l2_cache:  # Still exists after potential auto-cleanup
                        continue
                    expired_keys.append(key)
                
                # Log cleanup stats
                if expired_keys:
                    LOGGER.debug("Cleaned up %d expired cache entries", len(expired_keys))
                    
            except Exception as e:
                LOGGER.error("Error during cache cleanup: %s", e)
                self.metrics.record_error()

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache with metrics tracking."""
        start_time = time.time()
        
        try:
            async with self._lock:
                # Check L1 cache first (fastest)
                if key in self._l1_cache:
                    value = self._l1_cache[key]
                    access_time = time.time() - start_time
                    self.metrics.record_hit(access_time)
                    return value
                
                # Check L2 cache
                if key in self._l2_cache:
                    value = self._l2_cache[key]
                    # Promote to L1 cache
                    self._l1_cache[key] = value
                    access_time = time.time() - start_time
                    self.metrics.record_hit(access_time)
                    return value
                
                # Cache miss
                access_time = time.time() - start_time
                self.metrics.record_miss(access_time)
                return None
                
        except Exception as e:
            LOGGER.error("Error getting cache key %s: %s", key, e)
            self.metrics.record_error()
            return None

    async def set(self, key: str, value: Any) -> bool:
        """Set value in cache with metrics tracking."""
        try:
            async with self._lock:
                # Set in both cache levels
                self._l1_cache[key] = value
                self._l2_cache[key] = value
                self.metrics.record_set()
                return True
                
        except Exception as e:
            LOGGER.error("Error setting cache key %s: %s", key, e)
            self.metrics.record_error()
            return False

    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        try:
            async with self._lock:
                deleted = False
                if key in self._l1_cache:
                    del self._l1_cache[key]
                    deleted = True
                if key in self._l2_cache:
                    del self._l2_cache[key]
                    deleted = True
                
                if deleted:
                    self.metrics.record_delete()
                return deleted
                
        except Exception as e:
            LOGGER.error("Error deleting cache key %s: %s", key, e)
            self.metrics.record_error()
            return False

    async def clear(self) -> None:
        """Clear all cache data."""
        try:
            async with self._lock:
                self._l1_cache.clear()
                self._l2_cache.clear()
                self.metrics.record_clear()
                
        except Exception as e:
            LOGGER.error("Error clearing cache: %s", e)
            self.metrics.record_error()

    async def get_size(self) -> Dict[str, int]:
        """Get cache size information."""
        try:
            async with self._lock:
                return {
                    "l1_size": len(self._l1_cache),
                    "l2_size": len(self._l2_cache),
                    "l1_maxsize": self._l1_cache.maxsize,
                    "l2_maxsize": self._l2_cache.maxsize,
                }
        except Exception as e:
            LOGGER.error("Error getting cache size: %s", e)
            return {"error": str(e)}

    async def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics."""
        size_info = await self.get_size()
        return {
            **self.metrics.get_stats(),
            **size_info,
        }

    async def stop(self):
        """Stop the cache and cleanup tasks."""
        self._stopped = True
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass


# Global optimized caches
chat_invite_cache = OptimizedCache(l1_maxsize=200, l2_maxsize=1000, l2_ttl=1000)

ChatMemberStatus: TypeAlias = Union[
    types.ChatMemberStatusCreator,
    types.ChatMemberStatusAdministrator,
    types.ChatMemberStatusMember,
    types.ChatMemberStatusRestricted,
    types.ChatMemberStatusLeft,
    types.ChatMemberStatusBanned,
]

ChatMemberStatusResult: TypeAlias = Union[ChatMemberStatus, types.Error]
user_status_cache = OptimizedCache(l1_maxsize=1000, l2_maxsize=5000, l2_ttl=1000)


class OptimizedChatCacher:
    """High-performance chat caching system with metrics and error handling."""
    
    def __init__(self):
        self.chat_cache: Dict[int, Dict[str, Any]] = {}
        self.metrics = CacheMetrics()
        self._lock = asyncio.Lock()
        self._operation_count = 0
        
    async def _safe_operation(self, operation: str, func, *args, **kwargs):
        """Execute cache operation safely with metrics tracking."""
        start_time = time.time()
        self._operation_count += 1
        
        try:
            result = func(*args, **kwargs)
            operation_time = time.time() - start_time
            
            if result is not None:
                self.metrics.record_hit(operation_time)
            else:
                self.metrics.record_miss(operation_time)
                
            # Log slow operations
            if operation_time > 0.01:  # 10ms threshold
                LOGGER.warning(
                    "Slow cache operation '%s' took %.3fs for chat %s", 
                    operation, operation_time, args[0] if args else "unknown"
                )
                
            return result
            
        except Exception as e:
            LOGGER.error("Error in cache operation '%s': %s", operation, e)
            self.metrics.record_error()
            return None

    def add_song(self, chat_id: int, song: CachedTrack) -> Optional[CachedTrack]:
        """Add song to chat queue with error handling."""
        try:
            data = self.chat_cache.setdefault(
                chat_id, {"is_active": True, "queue": deque()}
            )
            data["queue"].append(song)
            self.metrics.record_set()
            return song
        except Exception as e:
            LOGGER.error("Error adding song to chat %s: %s", chat_id, e)
            self.metrics.record_error()
            return None

    def get_upcoming_track(self, chat_id: int) -> Optional[CachedTrack]:
        """Get next track in queue."""
        try:
            queue = self.chat_cache.get(chat_id, {}).get("queue")
            return queue[1] if queue and len(queue) > 1 else None
        except Exception as e:
            LOGGER.error("Error getting upcoming track for chat %s: %s", chat_id, e)
            self.metrics.record_error()
            return None

    def get_playing_track(self, chat_id: int) -> Optional[CachedTrack]:
        """Get currently playing track."""
        try:
            queue = self.chat_cache.get(chat_id, {}).get("queue")
            return queue[0] if queue else None
        except Exception as e:
            LOGGER.error("Error getting playing track for chat %s: %s", chat_id, e)
            self.metrics.record_error()
            return None

    def remove_current_song(self, chat_id: int) -> Optional[CachedTrack]:
        """Remove and return current song from queue."""
        try:
            queue = self.chat_cache.get(chat_id, {}).get("queue")
            if queue:
                song = queue.popleft()
                self.metrics.record_delete()
                return song
            return None
        except Exception as e:
            LOGGER.error("Error removing current song from chat %s: %s", chat_id, e)
            self.metrics.record_error()
            return None

    def is_active(self, chat_id: int) -> bool:
        """Check if chat has active playback."""
        try:
            return self.chat_cache.get(chat_id, {}).get("is_active", False)
        except Exception as e:
            LOGGER.error("Error checking if chat %s is active: %s", chat_id, e)
            self.metrics.record_error()
            return False

    def set_active(self, chat_id: int, active: bool) -> bool:
        """Set chat active status."""
        try:
            data = self.chat_cache.setdefault(
                chat_id, {"is_active": active, "queue": deque()}
            )
            data["is_active"] = active
            self.metrics.record_set()
            return True
        except Exception as e:
            LOGGER.error("Error setting active status for chat %s: %s", chat_id, e)
            self.metrics.record_error()
            return False

    def clear_chat(self, chat_id: int) -> bool:
        """Clear all chat data."""
        try:
            if chat_id in self.chat_cache:
                del self.chat_cache[chat_id]
                self.metrics.record_delete()
                return True
            return False
        except Exception as e:
            LOGGER.error("Error clearing chat %s: %s", chat_id, e)
            self.metrics.record_error()
            return False

    def get_queue_length(self, chat_id: int) -> int:
        """Get queue length for chat."""
        try:
            return len(self.chat_cache.get(chat_id, {}).get("queue", deque()))
        except Exception as e:
            LOGGER.error("Error getting queue length for chat %s: %s", chat_id, e)
            self.metrics.record_error()
            return 0

    def get_loop_count(self, chat_id: int) -> int:
        """Get loop count for current track."""
        try:
            queue = self.chat_cache.get(chat_id, {}).get("queue", deque())
            return queue[0].loop if queue else 0
        except Exception as e:
            LOGGER.error("Error getting loop count for chat %s: %s", chat_id, e)
            self.metrics.record_error()
            return 0

    def set_loop_count(self, chat_id: int, loop: int) -> bool:
        """Set loop count for current track."""
        try:
            queue = self.chat_cache.get(chat_id, {}).get("queue", deque())
            if queue:
                queue[0].loop = loop
                self.metrics.record_set()
                return True
            return False
        except Exception as e:
            LOGGER.error("Error setting loop count for chat %s: %s", chat_id, e)
            self.metrics.record_error()
            return False

    def remove_track(self, chat_id: int, queue_index: int) -> bool:
        """Remove track at specific index from queue."""
        try:
            queue = self.chat_cache.get(chat_id, {}).get("queue")
            if queue and 0 <= queue_index < len(queue):
                queue_list = list(queue)
                queue_list.pop(queue_index)
                self.chat_cache[chat_id]["queue"] = deque(queue_list)
                self.metrics.record_delete()
                return True
            return False
        except Exception as e:
            LOGGER.error("Error removing track %d from chat %s: %s", queue_index, chat_id, e)
            self.metrics.record_error()
            return False

    def get_queue(self, chat_id: int) -> List[CachedTrack]:
        """Get complete queue for chat."""
        try:
            return list(self.chat_cache.get(chat_id, {}).get("queue", deque()))
        except Exception as e:
            LOGGER.error("Error getting queue for chat %s: %s", chat_id, e)
            self.metrics.record_error()
            return []

    def get_active_chats(self) -> List[int]:
        """Get list of all active chats."""
        try:
            return [
                chat_id for chat_id, data in self.chat_cache.items() 
                if data.get("is_active", False)
            ]
        except Exception as e:
            LOGGER.error("Error getting active chats: %s", e)
            self.metrics.record_error()
            return []

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics."""
        try:
            return {
                **self.metrics.get_stats(),
                "total_chats": len(self.chat_cache),
                "active_chats": len(self.get_active_chats()),
                "total_operations": self._operation_count,
                "average_queue_length": self._get_average_queue_length(),
            }
        except Exception as e:
            LOGGER.error("Error getting cache stats: %s", e)
            return {"error": str(e)}

    def _get_average_queue_length(self) -> float:
        """Calculate average queue length across all chats."""
        try:
            if not self.chat_cache:
                return 0.0
            
            total_length = sum(
                len(data.get("queue", deque())) 
                for data in self.chat_cache.values()
            )
            return total_length / len(self.chat_cache)
        except Exception:
            return 0.0

    async def cleanup_inactive_chats(self, max_inactive_time: int = 3600) -> int:
        """Clean up chats that have been inactive for too long."""
        try:
            current_time = time.time()
            inactive_chats = []
            
            for chat_id, data in list(self.chat_cache.items()):
                if not data.get("is_active", False):
                    # Check if chat has been inactive for too long
                    last_activity = data.get("last_activity", current_time)
                    if current_time - last_activity > max_inactive_time:
                        inactive_chats.append(chat_id)
            
            # Remove inactive chats
            for chat_id in inactive_chats:
                self.clear_chat(chat_id)
            
            if inactive_chats:
                LOGGER.info("Cleaned up %d inactive chats", len(inactive_chats))
            
            return len(inactive_chats)
            
        except Exception as e:
            LOGGER.error("Error cleaning up inactive chats: %s", e)
            return 0

    async def optimize_memory(self) -> Dict[str, int]:
        """Optimize memory usage by cleaning up empty queues and inactive chats."""
        try:
            cleaned_chats = 0
            optimized_queues = 0
            
            for chat_id, data in list(self.chat_cache.items()):
                queue = data.get("queue", deque())
                
                # Remove chats with empty queues and inactive status
                if not queue and not data.get("is_active", False):
                    del self.chat_cache[chat_id]
                    cleaned_chats += 1
                    continue
                
                # Optimize queue structure if needed
                if len(queue) > 0:
                    # Convert to deque if it's not already
                    if not isinstance(queue, deque):
                        data["queue"] = deque(queue)
                        optimized_queues += 1
            
            LOGGER.info(
                "Memory optimization completed: %d chats cleaned, %d queues optimized",
                cleaned_chats, optimized_queues
            )
            
            return {
                "cleaned_chats": cleaned_chats,
                "optimized_queues": optimized_queues,
                "total_chats": len(self.chat_cache),
            }
            
        except Exception as e:
            LOGGER.error("Error optimizing memory: %s", e)
            return {"error": str(e)}


# Create optimized chat cache instance
chat_cache = OptimizedChatCacher()

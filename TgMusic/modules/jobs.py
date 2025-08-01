# Copyright (c) 2025 AshokShau
# Licensed under the GNU AGPL v3.0: https://www.gnu.org/licenses/agpl-3.0.html

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from pytdbot import Client, types
from TgMusic.core import chat_cache, call, db, config
from TgMusic.logger import LOGGER
from pyrogram import errors
from pyrogram.client import Client as PyroClient


@dataclass
class JobMetrics:
    """Performance metrics for job operations."""
    vc_checks: int = 0
    vc_ended: int = 0
    leave_operations: int = 0
    errors: int = 0
    total_runtime: float = 0.0
    avg_processing_time: float = 0.0
    _processing_times: List[float] = field(default_factory=list)
    last_cleanup: float = field(default_factory=time.time)

    def record_vc_check(self, processing_time: float = 0.0):
        self.vc_checks += 1
        self._record_processing_time(processing_time)

    def record_vc_end(self):
        self.vc_ended += 1

    def record_leave_operation(self, processing_time: float = 0.0):
        self.leave_operations += 1
        self._record_processing_time(processing_time)

    def record_error(self):
        self.errors += 1

    def _record_processing_time(self, processing_time: float):
        if processing_time > 0:
            self._processing_times.append(processing_time)
            if len(self._processing_times) > 100:  # Keep last 100 operations
                self._processing_times.pop(0)
            self.avg_processing_time = sum(self._processing_times) / len(self._processing_times)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "vc_checks": self.vc_checks,
            "vc_ended": self.vc_ended,
            "leave_operations": self.leave_operations,
            "errors": self.errors,
            "total_runtime": f"{self.total_runtime:.2f}s",
            "avg_processing_time": f"{self.avg_processing_time:.4f}s",
            "last_cleanup": self.last_cleanup,
        }


class OptimizedInactiveCallManager:
    """High-performance job manager with advanced concurrency control and monitoring."""
    
    def __init__(self, bot: Client):
        self.bot = bot
        self._stop = asyncio.Event()
        self._vc_task: Optional[asyncio.Task] = None
        self._leave_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # Performance settings
        self._sleep_time = 30  # Reduced for better responsiveness
        self._min_played_time = 15  # Minimum play time before auto-end
        self._max_concurrent_operations = 5
        self._operation_timeout = 30
        
        # Concurrency control
        self._semaphore = asyncio.Semaphore(self._max_concurrent_operations)
        self._active_operations: Dict[str, asyncio.Task] = {}
        self._operation_lock = asyncio.Lock()
        
        # Metrics and monitoring
        self.metrics = JobMetrics()
        self._health_check_interval = 300  # 5 minutes
        self._last_health_check = time.time()
        
        # Error handling
        self._max_consecutive_errors = 5
        self._consecutive_errors = 0
        self._error_backoff = 1.0

    async def _execute_with_timeout(self, operation, *args, **kwargs):
        """Execute operation with timeout and error handling."""
        try:
            return await asyncio.wait_for(
                operation(*args, **kwargs), 
                timeout=self._operation_timeout
            )
        except asyncio.TimeoutError:
            LOGGER.error("Operation timed out after %s seconds", self._operation_timeout)
            self.metrics.record_error()
            return None
        except Exception as e:
            LOGGER.error("Operation failed: %s", e)
            self.metrics.record_error()
            return None

    async def _end_call_if_inactive(self, chat_id: int) -> bool:
        """Check and end inactive voice calls with enhanced error handling."""
        start_time = time.time()
        
        try:
            async with self._semaphore:  # Limit concurrent operations
                # Check voice chat users
                vc_users = await self._execute_with_timeout(call.vc_users, chat_id)
                if vc_users is None or isinstance(vc_users, types.Error):
                    if isinstance(vc_users, types.Error):
                        LOGGER.warning("VC Users Error for chat %s: %s", chat_id, vc_users.message)
                    return False

                # If more than 1 user (bot + user), keep playing
                if len(vc_users) > 1:
                    return False

                # Check played time
                played_time = await self._execute_with_timeout(call.played_time, chat_id)
                if played_time is None or isinstance(played_time, types.Error):
                    if isinstance(played_time, types.Error):
                        LOGGER.warning("Played Time Error for chat %s: %s", chat_id, played_time.message)
                    return False

                # Don't end if track just started
                if played_time < self._min_played_time:
                    return False

                # End the call
                try:
                    await self.bot.sendTextMessage(
                        chat_id, 
                        "⚠️ No active listeners. Leaving voice chat..."
                    )
                    await self._execute_with_timeout(call.end, chat_id)
                    self.metrics.record_vc_end()
                    LOGGER.info("Ended inactive call in chat %s after %ds", chat_id, played_time)
                    return True
                    
                except Exception as e:
                    LOGGER.error("Failed to end call in chat %s: %s", chat_id, e)
                    return False
                    
        except Exception as e:
            LOGGER.error("Error checking inactive call for chat %s: %s", chat_id, e)
            self.metrics.record_error()
            return False
            
        finally:
            processing_time = time.time() - start_time
            self.metrics.record_vc_check(processing_time)

    async def _process_chat_batch(self, chat_batch: List[int]) -> int:
        """Process a batch of chats concurrently with error handling."""
        if not chat_batch:
            return 0
            
        try:
            # Create tasks for concurrent processing
            tasks = [
                asyncio.create_task(self._end_call_if_inactive(chat_id))
                for chat_id in chat_batch
            ]
            
            # Execute with timeout
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Count successful operations
            ended_calls = sum(1 for result in results if result is True)
            
            # Log any exceptions
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    LOGGER.error("Error processing chat %s: %s", chat_batch[i], result)
                    self.metrics.record_error()
            
            return ended_calls
            
        except Exception as e:
            LOGGER.error("Error processing chat batch: %s", e)
            self.metrics.record_error()
            return 0

    async def _vc_loop(self):
        """Optimized voice chat monitoring loop with batch processing."""
        loop_start_time = time.time()
        
        while not self._stop.is_set():
            cycle_start = time.time()
            
            try:
                # Health check
                if self.bot.me is None:
                    await asyncio.sleep(2)
                    continue

                # Check if auto-end is enabled
                if not await db.get_auto_end(self.bot.me.id):
                    await asyncio.sleep(self._sleep_time)
                    continue

                # Get active chats
                active_chats = chat_cache.get_active_chats()
                if not active_chats:
                    await asyncio.sleep(self._sleep_time)
                    continue

                LOGGER.debug("Processing %d active chats for auto-end", len(active_chats))

                # Process chats in batches to avoid overwhelming the system
                batch_size = min(10, self._max_concurrent_operations)
                total_ended = 0
                
                for i in range(0, len(active_chats), batch_size):
                    batch = active_chats[i:i + batch_size]
                    ended_calls = await self._process_chat_batch(batch)
                    total_ended += ended_calls
                    
                    # Small delay between batches
                    if i + batch_size < len(active_chats):
                        await asyncio.sleep(0.5)

                if total_ended > 0:
                    LOGGER.info("Auto-ended %d inactive voice calls", total_ended)

                # Reset consecutive errors on success
                self._consecutive_errors = 0
                self._error_backoff = 1.0

            except Exception as e:
                self._consecutive_errors += 1
                self.metrics.record_error()
                
                LOGGER.exception("VC AutoEnd loop error (attempt %d): %s", 
                               self._consecutive_errors, e)
                
                # Exponential backoff for consecutive errors
                if self._consecutive_errors >= self._max_consecutive_errors:
                    self._error_backoff = min(self._error_backoff * 2, 60)
                    LOGGER.warning("Too many consecutive errors, backing off for %ss", 
                                 self._error_backoff)
                    await asyncio.sleep(self._error_backoff)
                    self._consecutive_errors = 0

            # Adaptive sleep time based on workload
            cycle_time = time.time() - cycle_start
            sleep_time = max(self._sleep_time - cycle_time, 5)
            
            await asyncio.sleep(sleep_time)

        # Update total runtime
        self.metrics.total_runtime = time.time() - loop_start_time

    async def _leave_loop(self):
        """Optimized auto-leave loop with precise scheduling."""
        while not self._stop.is_set():
            try:
                now = datetime.now()
                target = now.replace(hour=3, minute=0, second=0, microsecond=0)
                if now >= target:
                    target += timedelta(days=1)

                wait_time = (target - now).total_seconds()
                LOGGER.info("AutoLeave scheduled for %s (waiting %.2f hours)", 
                          target.strftime("%Y-%m-%d %H:%M:%S"), wait_time / 3600)

                # Use asyncio.wait_for for better cancellation handling
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=wait_time)
                    break  # Stop event was set
                except asyncio.TimeoutError:
                    pass  # Timeout reached, proceed with leave_all

                if self._stop.is_set():
                    break

                # Execute leave_all operation
                await self.leave_all()

                # Wait for next day or until stopped
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=86400)  # 24 hours
                    break
                except asyncio.TimeoutError:
                    continue  # Continue to next iteration

            except Exception as e:
                LOGGER.exception("AutoLeave loop error: %s", e)
                self.metrics.record_error()
                
                # Wait before retry to avoid tight error loop
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=3600)  # 1 hour
                    break
                except asyncio.TimeoutError:
                    continue

    async def _leave_chat(self, ub: PyroClient, chat_id: int, retry_count: int = 0) -> bool:
        """Leave a chat with enhanced error handling and retry logic."""
        max_retries = 3
        start_time = time.time()
        
        try:
            # Don't leave if chat is currently active
            if chat_cache.is_active(chat_id):
                return False
                
            # Execute leave operation with timeout
            await asyncio.wait_for(ub.leave_chat(chat_id), timeout=10)
            
            processing_time = time.time() - start_time
            self.metrics.record_leave_operation(processing_time)
            
            LOGGER.debug("Successfully left chat %s via %s (%.2fs)", 
                        chat_id, ub.name, processing_time)
            return True
            
        except errors.FloodWait as e:
            wait_time = e.value
            
            # Only retry if wait time is reasonable and we haven't exceeded retries
            if wait_time <= 100 and retry_count < max_retries:
                LOGGER.warning(
                    "FloodWait %ds for chat %s via %s (retry %d/%d)", 
                    wait_time, chat_id, ub.name, retry_count + 1, max_retries
                )
                await asyncio.sleep(wait_time)
                return await self._leave_chat(ub, chat_id, retry_count + 1)
            else:
                LOGGER.error(
                    "FloodWait too long (%ds) or max retries exceeded for chat %s via %s", 
                    wait_time, chat_id, ub.name
                )
                self.metrics.record_error()
                return False
                
        except errors.RPCError as e:
            # Don't retry RPC errors, they're usually permanent
            LOGGER.warning("RPC error leaving chat %s via %s: %s", chat_id, ub.name, e)
            self.metrics.record_error()
            return False
            
        except asyncio.TimeoutError:
            LOGGER.error("Timeout leaving chat %s via %s", chat_id, ub.name)
            self.metrics.record_error()
            return False
            
        except Exception as e:
            LOGGER.exception("Unexpected error leaving chat %s via %s: %s", chat_id, ub.name, e)
            self.metrics.record_error()
            return False

    async def _process_client_dialogs(self, client_name: str, ub: PyroClient) -> int:
        """Process dialogs for a single client and leave inactive chats."""
        try:
            chats_to_leave = []
            
            # Collect chats to leave
            async for dialog in ub.get_dialogs():
                chat = getattr(dialog, "chat", None)
                if chat and chat.id > 0:
                    continue  # Skip users/private chats
                chats_to_leave.append(chat.id)
            
            LOGGER.info("Client %s: Found %d chats to process", client_name, len(chats_to_leave))
            
            # Process chats in batches with rate limiting
            successful_leaves = 0
            batch_size = 5  # Smaller batches to avoid rate limits
            
            for i in range(0, len(chats_to_leave), batch_size):
                batch = chats_to_leave[i:i + batch_size]
                
                # Process batch concurrently
                tasks = [
                    asyncio.create_task(self._leave_chat(ub, chat_id))
                    for chat_id in batch
                ]
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Count successful operations
                for result in results:
                    if result is True:
                        successful_leaves += 1
                    elif isinstance(result, Exception):
                        LOGGER.error("Leave operation failed: %s", result)
                
                # Rate limiting between batches
                if i + batch_size < len(chats_to_leave):
                    await asyncio.sleep(2.0)
            
            LOGGER.info("Client %s: Successfully left %d/%d chats", 
                       client_name, successful_leaves, len(chats_to_leave))
            return successful_leaves
            
        except Exception as e:
            LOGGER.exception("Error processing dialogs for client %s: %s", client_name, e)
            self.metrics.record_error()
            return 0

    async def leave_all(self):
        """Optimized leave_all with concurrent processing and comprehensive monitoring."""
        if not config.AUTO_LEAVE:
            LOGGER.info("AutoLeave is disabled, skipping leave_all operation")
            return

        start_time = time.time()
        LOGGER.info("Starting optimized leave_all operation")

        try:
            # Track operation metrics
            total_left = 0
            processed_clients = 0
            
            # Get all available clients
            available_clients = list(call.calls.items())
            if not available_clients:
                LOGGER.warning("No clients available for leave_all operation")
                return
            
            LOGGER.info("Processing %d clients for leave_all", len(available_clients))
            
            # Process clients concurrently (but with limited concurrency)
            semaphore = asyncio.Semaphore(3)  # Max 3 clients processed simultaneously
            
            async def process_client_with_semaphore(client_data):
                client_name, call_instance = client_data
                async with semaphore:
                    try:
                        ub: PyroClient = call_instance.mtproto_client
                        if not ub:
                            LOGGER.warning("Client %s has no mtproto_client", client_name)
                            return 0
                        
                        return await self._process_client_dialogs(client_name, ub)
                    except Exception as e:
                        LOGGER.exception("Error processing client %s: %s", client_name, e)
                        self.metrics.record_error()
                        return 0
            
            # Execute all client operations
            tasks = [
                asyncio.create_task(process_client_with_semaphore(client_data))
                for client_data in available_clients
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for i, result in enumerate(results):
                client_name = available_clients[i][0]
                if isinstance(result, Exception):
                    LOGGER.error("Client %s processing failed: %s", client_name, result)
                    self.metrics.record_error()
                else:
                    total_left += result
                    processed_clients += 1
            
            # Log final statistics
            duration = time.time() - start_time
            LOGGER.info(
                "Leave_all completed: %d clients processed, %d total chats left, %.2fs duration",
                processed_clients, total_left, duration
            )
            
            # Update metrics
            self.metrics.last_cleanup = time.time()
            
        except Exception as e:
            LOGGER.critical("Fatal error in leave_all operation: %s", e, exc_info=True)
            self.metrics.record_error()
            
        finally:
            duration = time.time() - start_time
            LOGGER.info("Leave_all operation completed in %.2fs", duration)

    async def _health_check_loop(self):
        """Periodic health check and maintenance loop."""
        while not self._stop.is_set():
            try:
                await asyncio.sleep(self._health_check_interval)
                
                current_time = time.time()
                
                # Perform health checks
                health_status = {
                    "vc_task_running": self._vc_task and not self._vc_task.done(),
                    "leave_task_running": self._leave_task and not self._leave_task.done(),
                    "active_operations": len(self._active_operations),
                    "consecutive_errors": self._consecutive_errors,
                    "last_check": current_time,
                }
                
                # Log health status
                LOGGER.debug("Job manager health check: %s", health_status)
                
                # Clean up completed operations
                async with self._operation_lock:
                    completed_ops = [
                        name for name, task in self._active_operations.items()
                        if task.done()
                    ]
                    for name in completed_ops:
                        del self._active_operations[name]
                
                if completed_ops:
                    LOGGER.debug("Cleaned up %d completed operations", len(completed_ops))
                
                # Perform cache cleanup if needed
                if hasattr(chat_cache, 'cleanup_inactive_chats'):
                    cleaned = await chat_cache.cleanup_inactive_chats()
                    if cleaned > 0:
                        LOGGER.info("Health check cleaned up %d inactive chats", cleaned)
                
                self._last_health_check = current_time
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                LOGGER.error("Error in health check loop: %s", e)
                self.metrics.record_error()

    async def start(self):
        """Start all job manager tasks with enhanced monitoring."""
        try:
            self._stop.clear()
            
            # Start VC monitoring task
            if not self._vc_task or self._vc_task.done():
                self._vc_task = asyncio.create_task(self._vc_loop())
                LOGGER.info("VC inactivity auto-end loop started (interval: %ds)", self._sleep_time)

            # Start auto-leave task
            if not self._leave_task or self._leave_task.done():
                self._leave_task = asyncio.create_task(self._leave_loop())
                LOGGER.info("Auto-leave loop started (scheduled for 3:00 AM daily)")
            
            # Start health check task
            if not self._cleanup_task or self._cleanup_task.done():
                self._cleanup_task = asyncio.create_task(self._health_check_loop())
                LOGGER.info("Health check loop started (interval: %ds)", self._health_check_interval)

            # Track active operations
            async with self._operation_lock:
                if self._vc_task:
                    self._active_operations["vc_monitor"] = self._vc_task
                if self._leave_task:
                    self._active_operations["auto_leave"] = self._leave_task
                if self._cleanup_task:
                    self._active_operations["health_check"] = self._cleanup_task

            LOGGER.info("Job manager started successfully with %d active tasks", 
                       len(self._active_operations))
            
        except Exception as e:
            LOGGER.error("Error starting job manager: %s", e)
            self.metrics.record_error()
            raise

    async def stop(self, timeout: float = 30.0):
        """Stop all job manager tasks with graceful shutdown."""
        start_time = time.time()
        LOGGER.info("Stopping job manager (timeout: %.1fs)", timeout)
        
        try:
            # Signal all tasks to stop
            self._stop.set()
            
            # Collect all tasks
            tasks_to_stop = []
            if self._vc_task and not self._vc_task.done():
                tasks_to_stop.append(("vc_monitor", self._vc_task))
            if self._leave_task and not self._leave_task.done():
                tasks_to_stop.append(("auto_leave", self._leave_task))
            if self._cleanup_task and not self._cleanup_task.done():
                tasks_to_stop.append(("health_check", self._cleanup_task))
            
            if not tasks_to_stop:
                LOGGER.info("No active tasks to stop")
                return
            
            # Wait for tasks with timeout
            try:
                await asyncio.wait_for(
                    asyncio.gather(*[task for _, task in tasks_to_stop], return_exceptions=True),
                    timeout=timeout
                )
                LOGGER.info("All tasks stopped gracefully")
                
            except asyncio.TimeoutError:
                LOGGER.warning("Timeout waiting for tasks to stop, cancelling remaining tasks")
                
                # Cancel remaining tasks
                for name, task in tasks_to_stop:
                    if not task.done():
                        LOGGER.warning("Cancelling task: %s", name)
                        task.cancel()
                
                # Wait a bit more for cancellation
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*[task for _, task in tasks_to_stop], return_exceptions=True),
                        timeout=5.0
                    )
                except asyncio.TimeoutError:
                    LOGGER.error("Some tasks failed to cancel within timeout")
            
            # Clear task references
            self._vc_task = None
            self._leave_task = None
            self._cleanup_task = None
            
            # Clear active operations
            async with self._operation_lock:
                self._active_operations.clear()
            
            stop_time = time.time() - start_time
            LOGGER.info("Job manager stopped in %.2fs", stop_time)
            
        except Exception as e:
            LOGGER.error("Error stopping job manager: %s", e)
            self.metrics.record_error()
            raise

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive status of the job manager."""
        try:
            return {
                "is_running": not self._stop.is_set(),
                "tasks": {
                    "vc_monitor": {
                        "running": self._vc_task and not self._vc_task.done(),
                        "task_id": id(self._vc_task) if self._vc_task else None,
                    },
                    "auto_leave": {
                        "running": self._leave_task and not self._leave_task.done(),
                        "task_id": id(self._leave_task) if self._leave_task else None,
                    },
                    "health_check": {
                        "running": self._cleanup_task and not self._cleanup_task.done(),
                        "task_id": id(self._cleanup_task) if self._cleanup_task else None,
                    },
                },
                "settings": {
                    "sleep_time": self._sleep_time,
                    "min_played_time": self._min_played_time,
                    "max_concurrent_operations": self._max_concurrent_operations,
                    "operation_timeout": self._operation_timeout,
                },
                "health": {
                    "last_health_check": self._last_health_check,
                    "consecutive_errors": self._consecutive_errors,
                    "error_backoff": self._error_backoff,
                },
                "active_operations": len(self._active_operations),
                **self.metrics.get_stats(),
            }
        except Exception as e:
            LOGGER.error("Error getting job manager status: %s", e)
            return {"error": str(e)}


# Create optimized job manager instance
InactiveCallManager = OptimizedInactiveCallManager

# Copyright (c) 2025 Devin
# Licensed under the GNU AGPL v3.0: https://www.gnu.org/licenses/agpl-3.0.html
# Part of the TgMusicBotFork project. All rights reserved where applicable.

import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import psutil
import threading

from TgMusic.logger import LOGGER


@dataclass
class PerformanceMetrics:
    """Performance metrics for various operations."""
    operation: str
    start_time: float
    end_time: Optional[float] = None
    success: bool = True
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration(self) -> float:
        """Calculate operation duration in seconds."""
        if self.end_time is None:
            return time.time() - self.start_time
        return self.end_time - self.start_time


class SystemMetrics:
    """System resource monitoring."""
    
    def __init__(self):
        self.cpu_usage = deque(maxlen=100)
        self.memory_usage = deque(maxlen=100)
        self.disk_usage = deque(maxlen=100)
        self.network_io = deque(maxlen=100)
        self._monitoring = False
        self._monitor_thread = None
    
    def start_monitoring(self, interval: int = 30):
        """Start system metrics monitoring."""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, 
            args=(interval,), 
            daemon=True
        )
        self._monitor_thread.start()
        LOGGER.info("System metrics monitoring started")
    
    def stop_monitoring(self):
        """Stop system metrics monitoring."""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        LOGGER.info("System metrics monitoring stopped")
    
    def _monitor_loop(self, interval: int):
        """Monitor system resources in background thread."""
        while self._monitoring:
            try:
                # CPU usage
                cpu_percent = psutil.cpu_percent(interval=1)
                self.cpu_usage.append((time.time(), cpu_percent))
                
                # Memory usage
                memory = psutil.virtual_memory()
                self.memory_usage.append((time.time(), memory.percent))
                
                # Disk usage
                disk = psutil.disk_usage('/')
                self.disk_usage.append((time.time(), disk.percent))
                
                # Network I/O
                net_io = psutil.net_io_counters()
                self.network_io.append((time.time(), net_io.bytes_sent, net_io.bytes_recv))
                
                time.sleep(interval)
                
            except Exception as e:
                LOGGER.error(f"Error in system monitoring: {e}")
                time.sleep(interval)
    
    def get_current_stats(self) -> Dict[str, Any]:
        """Get current system statistics."""
        try:
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            net_io = psutil.net_io_counters()
            
            return {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": memory.percent,
                "memory_available": memory.available,
                "disk_percent": disk.percent,
                "disk_free": disk.free,
                "network_sent": net_io.bytes_sent,
                "network_recv": net_io.bytes_recv,
            }
        except Exception as e:
            LOGGER.error(f"Error getting system stats: {e}")
            return {}


class BotMetrics:
    """Bot-specific metrics tracking."""
    
    def __init__(self):
        self.command_executions = defaultdict(int)
        self.error_counts = defaultdict(int)
        self.response_times = defaultdict(list)
        self.active_chats = set()
        self.total_playbacks = 0
        self.failed_playbacks = 0
        self.downloads = defaultdict(int)
        self.cache_hits = 0
        self.cache_misses = 0
        self.start_time = time.time()
        
        # Performance tracking
        self.performance_metrics: List[PerformanceMetrics] = []
        self._max_metrics = 1000  # Keep last 1000 metrics
    
    def record_command(self, command: str, success: bool = True, 
                      duration: Optional[float] = None, error: Optional[str] = None):
        """Record command execution metrics."""
        self.command_executions[command] += 1
        
        if not success:
            self.error_counts[command] += 1
        
        if duration is not None:
            self.response_times[command].append(duration)
            # Keep only last 100 response times per command
            if len(self.response_times[command]) > 100:
                self.response_times[command] = self.response_times[command][-100:]
    
    def record_playback(self, success: bool = True):
        """Record playback attempt."""
        self.total_playbacks += 1
        if not success:
            self.failed_playbacks += 1
    
    def record_download(self, platform: str, success: bool = True):
        """Record download attempt."""
        key = f"{platform}_{'success' if success else 'failed'}"
        self.downloads[key] += 1
    
    def record_cache_access(self, hit: bool):
        """Record cache access."""
        if hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1
    
    def add_performance_metric(self, metric: PerformanceMetrics):
        """Add performance metric."""
        self.performance_metrics.append(metric)
        
        # Trim old metrics
        if len(self.performance_metrics) > self._max_metrics:
            self.performance_metrics = self.performance_metrics[-self._max_metrics:]
    
    def get_uptime(self) -> float:
        """Get bot uptime in seconds."""
        return time.time() - self.start_time
    
    def get_success_rate(self) -> Dict[str, float]:
        """Get success rates for different operations."""
        rates = {}
        
        # Command success rates
        for command, total in self.command_executions.items():
            errors = self.error_counts.get(command, 0)
            success_rate = ((total - errors) / total * 100) if total > 0 else 0
            rates[f"command_{command}"] = success_rate
        
        # Playback success rate
        if self.total_playbacks > 0:
            rates["playback"] = ((self.total_playbacks - self.failed_playbacks) / 
                               self.total_playbacks * 100)
        
        # Cache hit rate
        total_cache_access = self.cache_hits + self.cache_misses
        if total_cache_access > 0:
            rates["cache"] = (self.cache_hits / total_cache_access * 100)
        
        return rates
    
    def get_average_response_times(self) -> Dict[str, float]:
        """Get average response times for commands."""
        averages = {}
        for command, times in self.response_times.items():
            if times:
                averages[command] = sum(times) / len(times)
        return averages
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive bot statistics."""
        return {
            "uptime_seconds": self.get_uptime(),
            "uptime_formatted": str(timedelta(seconds=int(self.get_uptime()))),
            "total_commands": sum(self.command_executions.values()),
            "total_errors": sum(self.error_counts.values()),
            "active_chats": len(self.active_chats),
            "total_playbacks": self.total_playbacks,
            "failed_playbacks": self.failed_playbacks,
            "success_rates": self.get_success_rate(),
            "avg_response_times": self.get_average_response_times(),
            "cache_stats": {
                "hits": self.cache_hits,
                "misses": self.cache_misses,
                "hit_rate": (self.cache_hits / (self.cache_hits + self.cache_misses) * 100) 
                           if (self.cache_hits + self.cache_misses) > 0 else 0
            },
            "download_stats": dict(self.downloads),
            "command_breakdown": dict(self.command_executions),
            "error_breakdown": dict(self.error_counts),
        }


class MetricsManager:
    """Centralized metrics management."""
    
    def __init__(self):
        self.bot_metrics = BotMetrics()
        self.system_metrics = SystemMetrics()
        self._start_time = time.time()
    
    def start_monitoring(self):
        """Start all monitoring systems."""
        self.system_metrics.start_monitoring()
        LOGGER.info("Metrics monitoring started")
    
    def stop_monitoring(self):
        """Stop all monitoring systems."""
        self.system_metrics.stop_monitoring()
        LOGGER.info("Metrics monitoring stopped")
    
    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics from all sources."""
        return {
            "bot": self.bot_metrics.get_stats(),
            "system": self.system_metrics.get_current_stats(),
            "monitoring_active": self.system_metrics._monitoring,
        }
    
    def record_operation(self, operation: str, duration: float, 
                        success: bool = True, error: Optional[str] = None,
                        metadata: Optional[Dict[str, Any]] = None):
        """Record operation performance."""
        metric = PerformanceMetrics(
            operation=operation,
            start_time=time.time() - duration,
            end_time=time.time(),
            success=success,
            error_message=error,
            metadata=metadata or {}
        )
        self.bot_metrics.add_performance_metric(metric)
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get bot health status."""
        stats = self.get_comprehensive_stats()
        
        # Define health thresholds
        health_checks = {
            "cpu_ok": stats["system"].get("cpu_percent", 0) < 80,
            "memory_ok": stats["system"].get("memory_percent", 0) < 85,
            "disk_ok": stats["system"].get("disk_percent", 0) < 90,
            "uptime_ok": stats["bot"]["uptime_seconds"] > 300,  # 5 minutes
            "error_rate_ok": stats["bot"]["total_errors"] / max(stats["bot"]["total_commands"], 1) < 0.1,
        }
        
        overall_health = all(health_checks.values())
        
        return {
            "healthy": overall_health,
            "checks": health_checks,
            "issues": [k for k, v in health_checks.items() if not v],
            "stats": stats
        }


# Global metrics manager
metrics_manager = MetricsManager()


def performance_monitor(operation: str):
    """Decorator for automatic performance monitoring."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            error = None
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error = str(e)
                raise
            finally:
                duration = time.time() - start_time
                metrics_manager.record_operation(
                    operation=operation,
                    duration=duration,
                    success=success,
                    error=error
                )
        return wrapper
    return decorator 
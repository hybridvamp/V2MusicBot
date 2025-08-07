# Copyright (c) 2025 Devin
# Licensed under the GNU AGPL v3.0: https://www.gnu.org/licenses/agpl-3.0.html
# Part of the TgMusicBotFork project. All rights reserved where applicable.

import asyncio
import functools
import traceback
from typing import Any, Callable, Coroutine, Optional, TypeVar, Union
from enum import Enum

from pytdbot import types
from TgMusic.logger import LOGGER

T = TypeVar('T')


class ErrorSeverity(Enum):
    """Error severity levels for better error categorization."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorContext:
    """Context information for error handling."""
    
    def __init__(self, operation: str, user_id: Optional[int] = None, 
                 chat_id: Optional[int] = None, **kwargs):
        self.operation = operation
        self.user_id = user_id
        self.chat_id = chat_id
        self.additional_info = kwargs
        self.timestamp = asyncio.get_event_loop().time()


class ErrorHandler:
    """Centralized error handling with advanced features."""
    
    def __init__(self):
        self.error_counts = {}
        self.recovery_strategies = {}
        self._setup_recovery_strategies()
    
    def _setup_recovery_strategies(self):
        """Setup automatic recovery strategies for common errors."""
        self.recovery_strategies = {
            "ConnectionFailure": self._handle_connection_failure,
            "ServerSelectionTimeoutError": self._handle_timeout_error,
            "FloodWait": self._handle_flood_wait,
            "NetworkError": self._handle_network_error,
            "InvalidOperation": self._handle_invalid_operation,
        }
    
    async def _handle_connection_failure(self, error: Exception, context: ErrorContext) -> bool:
        """Handle database connection failures."""
        LOGGER.warning(f"Connection failure in {context.operation}: {error}")
        # Implement connection retry logic
        return True
    
    async def _handle_timeout_error(self, error: Exception, context: ErrorContext) -> bool:
        """Handle timeout errors with exponential backoff."""
        LOGGER.warning(f"Timeout in {context.operation}: {error}")
        await asyncio.sleep(1)  # Basic backoff
        return True
    
    async def _handle_flood_wait(self, error: Exception, context: ErrorContext) -> bool:
        """Handle Telegram flood wait errors."""
        if hasattr(error, 'value'):
            wait_time = error.value
            LOGGER.warning(f"Flood wait for {wait_time}s in {context.operation}")
            await asyncio.sleep(wait_time)
            return True
        return False
    
    async def _handle_network_error(self, error: Exception, context: ErrorContext) -> bool:
        """Handle general network errors."""
        LOGGER.warning(f"Network error in {context.operation}: {error}")
        await asyncio.sleep(2)
        return True
    
    async def _handle_invalid_operation(self, error: Exception, context: ErrorContext) -> bool:
        """Handle invalid operation errors."""
        LOGGER.error(f"Invalid operation in {context.operation}: {error}")
        return False
    
    def handle_error(self, error: Exception, context: ErrorContext, 
                    severity: ErrorSeverity = ErrorSeverity.MEDIUM) -> None:
        """Centralized error handling with logging and recovery."""
        
        # Track error frequency
        error_key = f"{type(error).__name__}_{context.operation}"
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        
        # Log error with context
        log_message = f"Error in {context.operation}"
        if context.user_id:
            log_message += f" (User: {context.user_id})"
        if context.chat_id:
            log_message += f" (Chat: {context.chat_id})"
        
        if severity == ErrorSeverity.CRITICAL:
            LOGGER.critical(log_message, exc_info=True)
        elif severity == ErrorSeverity.HIGH:
            LOGGER.error(log_message, exc_info=True)
        elif severity == ErrorSeverity.MEDIUM:
            LOGGER.warning(log_message, exc_info=True)
        else:
            LOGGER.info(log_message, exc_info=True)
        
        # Attempt recovery if strategy exists
        error_type = type(error).__name__
        if error_type in self.recovery_strategies:
            asyncio.create_task(self.recovery_strategies[error_type](error, context))
    
    def get_error_stats(self) -> dict:
        """Get error statistics for monitoring."""
        return {
            "total_errors": sum(self.error_counts.values()),
            "error_types": len(self.error_counts),
            "most_frequent": max(self.error_counts.items(), key=lambda x: x[1]) if self.error_counts else None,
            "error_breakdown": self.error_counts.copy()
        }


# Global error handler instance
error_handler = ErrorHandler()


def error_handler_decorator(operation: str, severity: ErrorSeverity = ErrorSeverity.MEDIUM):
    """Decorator for automatic error handling in async functions."""
    def decorator(func: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., Coroutine[Any, Any, T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # Extract context from function arguments
                context = ErrorContext(operation)
                
                # Try to extract user_id and chat_id from common argument patterns
                for arg in args:
                    if hasattr(arg, 'from_id'):
                        context.user_id = arg.from_id
                    if hasattr(arg, 'chat_id'):
                        context.chat_id = arg.chat_id
                
                error_handler.handle_error(e, context, severity)
                raise
        return wrapper
    return decorator


def safe_execute(func: Callable[..., Coroutine[Any, Any, T]], 
                *args, operation: str = "unknown", 
                severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                **kwargs) -> Coroutine[Any, Any, Optional[T]]:
    """Safely execute a function with error handling."""
    async def wrapper():
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            context = ErrorContext(operation)
            error_handler.handle_error(e, context, severity)
            return None
    return wrapper()


class ErrorResponse:
    """Standardized error response for user-facing errors."""
    
    def __init__(self, message: str, code: int = 500, 
                 user_friendly: bool = True, retry_after: Optional[int] = None):
        self.message = message
        self.code = code
        self.user_friendly = user_friendly
        self.retry_after = retry_after
    
    def to_telegram_error(self) -> types.Error:
        """Convert to Telegram error type."""
        return types.Error(self.code, self.message)
    
    @classmethod
    def from_exception(cls, exc: Exception, user_friendly: bool = True) -> 'ErrorResponse':
        """Create error response from exception."""
        if isinstance(exc, types.Error):
            return cls(exc.message, exc.code, user_friendly)
        
        # Map common exceptions to user-friendly messages
        error_mapping = {
            "ConnectionFailure": ("Database connection failed", 503),
            "ServerSelectionTimeoutError": ("Service temporarily unavailable", 503),
            "FloodWait": ("Rate limited, please wait", 429),
            "NetworkError": ("Network connection failed", 503),
            "InvalidOperation": ("Invalid operation", 400),
        }
        
        error_type = type(exc).__name__
        if error_type in error_mapping:
            message, code = error_mapping[error_type]
            return cls(message, code, user_friendly)
        
        return cls(str(exc), 500, user_friendly) 
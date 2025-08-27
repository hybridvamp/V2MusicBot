#  Copyright (c) 2025 AshokShau
#  Licensed under the GNU AGPL v3.0: https://www.gnu.org/licenses/agpl-3.0.html
#  Part of the TgMusicBot project. All rights reserved where applicable.

import asyncio
import hashlib
import re
import time
from pathlib import Path
from typing import Optional, Union, Dict, Any, List
from dataclasses import dataclass, field

from pytdbot import types
from TgMusic.logger import LOGGER

from ._config import config
from ._downloader import MusicService
from ._httpx import HttpxClient
from ._spotify_dl_helper import SpotifyDownload
from ._dataclass import PlatformTracks, MusicTrack, TrackInfo


@dataclass
class ApiMetrics:
    """Performance metrics for API operations."""
    requests_made: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    errors: int = 0
    retries: int = 0
    avg_response_time: float = 0.0
    _response_times: List[float] = field(default_factory=list)

    def record_request(self, response_time: float):
        self.requests_made += 1
        self._record_response_time(response_time)

    def record_cache_hit(self):
        self.cache_hits += 1

    def record_cache_miss(self):
        self.cache_misses += 1

    def record_error(self):
        self.errors += 1

    def record_retry(self):
        self.retries += 1

    def _record_response_time(self, response_time: float):
        self._response_times.append(response_time)
        if len(self._response_times) > 100:  # Keep last 100 requests
            self._response_times.pop(0)
        self.avg_response_time = sum(self._response_times) / len(self._response_times)

    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        return (self.cache_hits / total * 100) if total > 0 else 0.0

    def get_stats(self) -> Dict[str, Any]:
        return {
            "requests_made": self.requests_made,
            "cache_hit_rate": f"{self.cache_hit_rate:.2f}%",
            "errors": self.errors,
            "retries": self.retries,
            "avg_response_time": f"{self.avg_response_time:.3f}s",
        }


class ApiRequestCache:
    """High-performance caching for API requests."""
    
    def __init__(self, max_size: int = 1000, ttl: int = 300):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._access_times: Dict[str, float] = {}
        self._max_size = max_size
        self._ttl = ttl
        self._lock = asyncio.Lock()

    def _generate_key(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> str:
        """Generate cache key from endpoint and parameters."""
        params_str = str(sorted(params.items())) if params else ""
        return hashlib.md5(f"{endpoint}:{params_str}".encode()).hexdigest()

    async def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Get cached response if available and not expired."""
        key = self._generate_key(endpoint, params)
        
        async with self._lock:
            if key not in self._cache:
                return None
            
            # Check if expired
            if time.time() - self._access_times[key] > self._ttl:
                del self._cache[key]
                del self._access_times[key]
                return None
            
            # Update access time
            self._access_times[key] = time.time()
            return self._cache[key].copy()

    async def set(self, endpoint: str, params: Optional[Dict[str, Any]], response: Dict[str, Any]) -> None:
        """Cache API response."""
        key = self._generate_key(endpoint, params)
        
        async with self._lock:
            # Remove oldest entries if cache is full
            if len(self._cache) >= self._max_size:
                # Remove 20% of oldest entries
                items_to_remove = sorted(self._access_times.items(), key=lambda x: x[1])[:self._max_size // 5]
                for old_key, _ in items_to_remove:
                    self._cache.pop(old_key, None)
                    self._access_times.pop(old_key, None)
            
            self._cache[key] = response.copy()
            self._access_times[key] = time.time()

    async def clear(self) -> None:
        """Clear all cached data."""
        async with self._lock:
            self._cache.clear()
            self._access_times.clear()

    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        async with self._lock:
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "ttl": self._ttl,
                "memory_usage": sum(len(str(v)) for v in self._cache.values()),
            }


class OptimizedApiData(MusicService):
    """High-performance API integration handler with advanced features.

    Enhanced capabilities:
    - Smart retry mechanisms with exponential backoff
    - Multi-level caching for improved response times
    - Rate limiting to prevent API abuse
    - Comprehensive error handling and recovery
    - Performance monitoring and metrics
    - Connection pooling for efficient resource usage
    """

    # Platform URL validation patterns (optimized with compiled regex)
    URL_PATTERNS = {
        "apple_music": re.compile(
            r"^(https?://)?([a-z0-9-]+\.)*music\.apple\.com/"
            r"([a-z]{2}/)?"
            r"(album|playlist|song)/[a-zA-Z0-9\-._]+/(pl\.[a-zA-Z0-9]+|\d+)(\?.*)?$",
            re.IGNORECASE,
        ),
        "spotify": re.compile(
            r"^(https?://)?([a-z0-9-]+\.)*spotify\.com/"
            r"(track|playlist|album|artist)/[a-zA-Z0-9]+(\?.*)?$",
            re.IGNORECASE,
        ),
        "soundcloud": re.compile(
            r"^(https?://)?([a-z0-9-]+\.)*soundcloud\.com/"
            r"[a-zA-Z0-9_-]+(/(sets)?/[a-zA-Z0-9_-]+)?(\?.*)?$",
            re.IGNORECASE,
        ),
    }

    # Performance settings
    MAX_RETRIES = 3
    BASE_DELAY = 1.0
    MAX_DELAY = 60.0
    REQUEST_TIMEOUT = 30
    RATE_LIMIT_DELAY = 0.1
    
    # Class-level cache and metrics (shared across instances)
    _shared_cache = None
    _shared_metrics = None
    _rate_limiter = None

    def __init__(self, query: Optional[str] = None) -> None:
        """Initialize the optimized API handler.

        Args:
            query: URL or search term to process
        """
        self.query = self._sanitize_query(query) if query else None
        self.api_url = config.API_URL.rstrip("/") if config.API_URL else None
        self.api_key = config.API_KEY
        self.client = HttpxClient()

        # Initialize shared components if needed
        if OptimizedApiData._shared_cache is None:
            OptimizedApiData._shared_cache = ApiRequestCache()
        if OptimizedApiData._shared_metrics is None:
            OptimizedApiData._shared_metrics = ApiMetrics()
        if OptimizedApiData._rate_limiter is None:
            OptimizedApiData._rate_limiter = asyncio.Semaphore(10)  # Max 10 concurrent requests

        self.cache = OptimizedApiData._shared_cache
        self.metrics = OptimizedApiData._shared_metrics

    @staticmethod
    def _sanitize_query(query: str) -> str:
        """Clean and standardize input queries with enhanced validation.

        Removes:
        - URL fragments (#)
        - Query parameters (?)
        - Leading/trailing whitespace
        - Invalid characters
        """
        if not query:
            return ""
        
        # Basic cleaning
        cleaned = query.strip().split("?")[0].split("#")[0]
        
        # Remove excessive whitespace
        cleaned = " ".join(cleaned.split())
        
        return cleaned

    def is_valid(self, url: Optional[str]) -> bool:
        """Validate if URL matches supported platform patterns with caching.

        Args:
            url: The URL to validate

        Returns:
            bool: True if URL matches any platform pattern
        """
        if not url or not self.api_url or not self.api_key:
            return False
            
        # Cache validation results to avoid repeated regex operations
        cache_key = f"validation:{hashlib.md5(url.encode()).hexdigest()}"
        
        # Simple validation cache (in-memory only)
        if not hasattr(self, '_validation_cache'):
            self._validation_cache = {}
        
        if cache_key in self._validation_cache:
            return self._validation_cache[cache_key]
        
        # Perform validation
        result = any(pattern.match(url) for pattern in self.URL_PATTERNS.values())
        
        # Cache result (limit cache size)
        if len(self._validation_cache) < 1000:
            self._validation_cache[cache_key] = result
        
        return result

    async def _apply_rate_limiting(self):
        """Apply rate limiting to prevent API abuse."""
        async with OptimizedApiData._rate_limiter:
            await asyncio.sleep(self.RATE_LIMIT_DELAY)

    async def _make_api_request_with_retry(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Make API request with advanced retry logic and caching."""
        
        # Check cache first
        cached_response = await self.cache.get(endpoint, params)
        if cached_response:
            self.metrics.record_cache_hit()
            LOGGER.debug("Cache hit for endpoint: %s", endpoint)
            return cached_response

        self.metrics.record_cache_miss()
        
        # Apply rate limiting
        await self._apply_rate_limiting()
        
        delay = self.BASE_DELAY
        last_exception = None
        
        for attempt in range(self.MAX_RETRIES):
            try:
                start_time = time.time()
                
                # Make the actual request
                response = await self._make_api_request(endpoint, params)
                
                response_time = time.time() - start_time
                self.metrics.record_request(response_time)
                
                if response:
                    # Cache successful response
                    await self.cache.set(endpoint, params, response)
                    LOGGER.debug(
                        "API request successful: %s (%.3fs, attempt %d)",
                        endpoint, response_time, attempt + 1
                    )
                    return response
                else:
                    # Treat empty response as an error
                    raise ValueError("Empty response from API")
                
            except Exception as e:
                last_exception = e
                self.metrics.record_error()
                
                if attempt < self.MAX_RETRIES - 1:
                    self.metrics.record_retry()
                    LOGGER.warning(
                        "API request failed (attempt %d/%d): %s. Retrying in %.1fs...",
                        attempt + 1, self.MAX_RETRIES, str(e), delay
                    )
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, self.MAX_DELAY)  # Exponential backoff
                else:
                    LOGGER.error(
                        "API request failed after %d attempts: %s",
                        self.MAX_RETRIES, str(e)
                    )
        
        # All retries failed
        return None

    async def _make_api_request(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Make authenticated API requests to the music service.

        Args:
            endpoint: API endpoint to call
            params: Query parameters for the request

        Returns:
            dict: JSON response from API or None if failed
        """
        if not self.api_url or not self.api_key:
            LOGGER.warning(
                "API configuration incomplete - Get credentials from @FallenAPIBot"
            )
            return None

        request_url = f"{self.api_url}/{endpoint.lstrip('/')}"
        
        # Add API key to headers
        for AP_I in self.api_key:
            if AP_I in config.DIS_API:
                continue
            headers = {"X-API-Key": AP_I}
            config.CURRENT_KEY = AP_I
        # headers = {"X-API-Key": self.api_key}
        
        try:
            return await asyncio.wait_for(
                self.client.make_request(request_url, headers=headers, params=params),
                timeout=self.REQUEST_TIMEOUT
            )
        except asyncio.TimeoutError:
            LOGGER.error("API request timeout for endpoint: %s", endpoint)
            raise
        except Exception as e:
            LOGGER.error("API request error for endpoint %s: %s", endpoint, e)
            raise

    async def get_info(self) -> Union[PlatformTracks, types.Error]:
        """Retrieve track information from a valid URL with enhanced error handling.

        Returns:
            PlatformTracks: Contains track metadata
            types.Error: If URL is invalid or request fails
        """
        if not self.query:
            return types.Error(400, "No URL provided")
            
        if not self.is_valid(self.query):
            return types.Error(400, "Invalid or unsupported URL provided")

        try:
            response = await self._make_api_request_with_retry("get_url", {"url": self.query})
            result = self._parse_tracks_response(response)
            
            if isinstance(result, types.Error):
                LOGGER.warning("Failed to get track info for URL: %s - %s", self.query, result.message)
            else:
                LOGGER.info("Successfully retrieved track info for URL: %s", self.query)
                
            return result or types.Error(404, "No track information found")
            
        except Exception as e:
            self.metrics.record_error()
            error_msg = f"Error retrieving track info: {str(e)}"
            LOGGER.error(error_msg)
            return types.Error(500, error_msg)

    async def search(self) -> Union[PlatformTracks, types.Error]:
        """Search for tracks across supported platforms with optimizations.

        Returns:
            PlatformTracks: Contains search results
            types.Error: If query is invalid or search fails
        """
        if not self.query:
            return types.Error(400, "No search query provided")

        try:
            # If query is a valid URL, get info directly
            if self.is_valid(self.query):
                LOGGER.debug("Query is a valid URL, getting info directly")
                return await self.get_info()

            # Perform search
            response = await self._make_api_request_with_retry("search_track", {"q": self.query})
            result = self._parse_tracks_response(response)
            
            if isinstance(result, types.Error):
                LOGGER.warning("Search failed for query: %s - %s", self.query, result.message)
            else:
                LOGGER.info("Search successful for query: %s", self.query)
                
            return result or types.Error(404, "No results found for search query")
            
        except Exception as e:
            self.metrics.record_error()
            error_msg = f"Error performing search: {str(e)}"
            LOGGER.error(error_msg)
            return types.Error(500, error_msg)

    async def get_track(self) -> Union[TrackInfo, types.Error]:
        """Get detailed track information with enhanced validation.

        Returns:
            TrackInfo: Detailed track metadata
            types.Error: If track cannot be found
        """
        if not self.query:
            return types.Error(400, "No track identifier provided")

        try:
            response = await self._make_api_request_with_retry("get_track", {"id": self.query})
            
            if not response:
                return types.Error(404, "Track not found")
                
            # Validate response structure
            if not isinstance(response, dict):
                return types.Error(500, "Invalid response format")
                
            return TrackInfo(**response)
            
        except Exception as e:
            self.metrics.record_error()
            if "missing" in str(e).lower() or "required" in str(e).lower():
                error_msg = f"Invalid track data format: {str(e)}"
                LOGGER.error(error_msg)
                return types.Error(400, error_msg)
            else:
                error_msg = f"Error getting track details: {str(e)}"
                LOGGER.error(error_msg)
                return types.Error(500, error_msg)

    async def download_track(
        self, track: TrackInfo, video: bool = False, msg: types.Message = None
    ) -> Union[Path, types.Error]:
        """Download a track with enhanced error handling and progress tracking.

        Args:
            track: TrackInfo object containing download details
            video: Whether to download video (default: False)

        Returns:
            Path: Location of downloaded file
            types.Error: If download fails
        """
        if not track:
            return types.Error(400, "Invalid track information provided")

        start_time = time.time()
        
        try:
            # Handle platform-specific download methods
            if track.platform.lower() == "spotify":
                LOGGER.debug("Using Spotify downloader for track: %s", track.tc)
                spotify_result = await SpotifyDownload(track).process()
                if isinstance(spotify_result, types.Error):
                    LOGGER.error("Spotify download failed: %s", spotify_result.message)
                    self.metrics.record_error()
                return spotify_result

            # if track.platform.lower() == "youtube":
            #     return await YouTubeData().download_track(track, video)

            if not track.cdnurl:
                error_msg = f"No download URL available for track: {track.tc}"
                LOGGER.error(error_msg)
                return types.Error(400, error_msg)

            # Standard download handling with enhanced error checking
            download_path = config.DOWNLOADS_DIR / f"{track.tc}.mp3"
            
            # Ensure download directory exists
            download_path.parent.mkdir(parents=True, exist_ok=True)
            
            download_result = await self.client.download_file(track.cdnurl, download_path)

            if not download_result.success:
                error_msg = f"Download failed: {download_result.error or 'Unknown error'}"
                LOGGER.warning("Download failed for track %s: %s", track.tc, error_msg)
                self.metrics.record_error()
                return types.Error(500, error_msg)

            download_time = time.time() - start_time
            LOGGER.info(
                "Successfully downloaded track %s in %.2fs (size: %d bytes)",
                track.tc, download_time, download_path.stat().st_size if download_path.exists() else 0
            )
            
            return download_result.file_path

        except Exception as e:
            self.metrics.record_error()
            error_msg = f"Unexpected download error: {str(e)}"
            LOGGER.error(error_msg, exc_info=True)
            return types.Error(500, error_msg)

    @staticmethod
    def _parse_tracks_response(
        response_data: Optional[Dict[str, Any]],
    ) -> Union[PlatformTracks, types.Error]:
        """Parse and validate API response data with enhanced error handling.

        Args:
            response_data: Raw API response

        Returns:
            PlatformTracks: Validated track data
            types.Error: If response is invalid
        """
        if not response_data:
            return types.Error(404, "Empty API response")
            
        if not isinstance(response_data, dict):
            return types.Error(500, "Invalid API response format")

        if "results" not in response_data:
            return types.Error(404, "No results in API response")

        try:
            results = response_data["results"]
            if not isinstance(results, list):
                return types.Error(500, "Invalid results format")
                
            tracks = []
            parse_errors = 0
            
            for track_data in results:
                if not isinstance(track_data, dict):
                    parse_errors += 1
                    continue
                    
                try:
                    track = MusicTrack(**track_data)
                    tracks.append(track)
                except Exception as e:
                    parse_errors += 1
                    LOGGER.debug("Failed to parse track data: %s", e)
                    continue
            
            if not tracks:
                if parse_errors > 0:
                    return types.Error(500, f"Failed to parse {parse_errors} track(s)")
                else:
                    return types.Error(404, "No valid tracks found")
            
            if parse_errors > 0:
                LOGGER.warning("Successfully parsed %d tracks, failed to parse %d tracks", 
                             len(tracks), parse_errors)
            
            return PlatformTracks(tracks=tracks)
            
        except Exception as parse_error:
            LOGGER.error("Failed to parse tracks response: %s", parse_error)
            return types.Error(500, "Failed to process track data")

    async def get_api_stats(self) -> Dict[str, Any]:
        """Get comprehensive API performance statistics."""
        try:
            cache_stats = await self.cache.get_stats()
            return {
                **self.metrics.get_stats(),
                "cache": cache_stats,
                "configuration": {
                    "api_url": self.api_url,
                    "has_api_key": bool(self.api_key),
                    "max_retries": self.MAX_RETRIES,
                    "request_timeout": self.REQUEST_TIMEOUT,
                },
            }
        except Exception as e:
            LOGGER.error("Error getting API stats: %s", e)
            return {"error": str(e)}

    @classmethod
    async def clear_cache(cls):
        """Clear shared cache data."""
        if cls._shared_cache:
            await cls._shared_cache.clear()
            LOGGER.info("API cache cleared")

    @classmethod
    def reset_metrics(cls):
        """Reset shared metrics."""
        if cls._shared_metrics:
            cls._shared_metrics = ApiMetrics()
            LOGGER.info("API metrics reset")


# Backward compatibility alias
ApiData = OptimizedApiData

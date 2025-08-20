# Copyright (c) 2025 AshokShau
# Licensed under the GNU AGPL v3.0: https://www.gnu.org/licenses/agpl-3.0.html
# Part of the TgMusicBot project. All rights reserved where applicable.

import asyncio
import os
import random
import re
import aiohttp
import subprocess
from pathlib import Path
from typing import Any, Optional, Dict, Union
from urllib.parse import urlparse, parse_qs
from swiftshadow import QuickProxy
from swiftshadow.classes import ProxyInterface

from py_yt import Playlist, VideosSearch
from pytdbot import types

from TgMusic.logger import LOGGER


from ._config import config
from ._dataclass import MusicTrack, PlatformTracks, TrackInfo
from ._downloader import MusicService
from ._httpx import HttpxClient

COOKIES_DIR = "TgMusic/cookies"

INVIDIOUS_INSTANCES = [
    "http://yt.hybtids.xyz",
    "https://vid.puffyan.us",
    "https://inv.nadeko.net",
    "https://iv.ggtyler.dev",
    "https://yewtu.be",
    "https://id.420129.xyz",
    "https://invidious.nerdvpn.de"
]

swift = ProxyInterface(protocol="https", autoUpdate=False, autoRotate=True)

async def _get_proxy_async():
    # Refresh proxies safely inside event loop
    await swift.async_update()
    proxy = swift.get().as_string()
    LOGGER.info(f"Proxy found: {proxy}")
    return proxy

def get_proxy():
    try:
        # If there’s already a running event loop, schedule the coroutine
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No event loop → normal blocking run
        return asyncio.run(_get_proxy_async())
    else:
        # Inside a running loop → run coroutine in that loop
        return loop.run_until_complete(_get_proxy_async())

class YouTubeUtils:
    """Utility class for YouTube-related operations."""

    # Compile regex patterns once at class level
    YOUTUBE_VIDEO_PATTERN = re.compile(
        r"^(?:https?://)?(?:www\.)?(?:youtube\.com|music\.youtube\.com|youtu\.be)/"
        r"(?:watch\?v=|embed/|v/|shorts/)?([\w-]{11})(?:\?|&|$)",
        re.IGNORECASE,
    )
    YOUTUBE_PLAYLIST_PATTERN = re.compile(
        r"^(?:https?://)?(?:www\.)?(?:youtube\.com|music\.youtube\.com)/"
        r"(?:playlist|watch)\?.*\blist=([\w-]+)",
        re.IGNORECASE,
    )
    YOUTUBE_SHORTS_PATTERN = re.compile(
        r"^(?:https?://)?(?:www\.)?youtube\.com/shorts/([\w-]+)",
        re.IGNORECASE,
    )

    @staticmethod
    def clean_query(query: str) -> str:
        """Clean the query by removing unnecessary parameters."""
        return query.split("&")[0].split("#")[0].strip()

    @staticmethod
    def is_valid_url(url: Optional[str]) -> bool:
        if not url:
            return False
        return any(
            pattern.match(url)
            for pattern in (
                YouTubeUtils.YOUTUBE_VIDEO_PATTERN,
                YouTubeUtils.YOUTUBE_PLAYLIST_PATTERN,
                YouTubeUtils.YOUTUBE_SHORTS_PATTERN,
            )
        )

    @staticmethod
    def _extract_video_id(url: str) -> Optional[str]:
        """Extract video ID from various YouTube URL formats."""
        for pattern in (
            YouTubeUtils.YOUTUBE_VIDEO_PATTERN,
            YouTubeUtils.YOUTUBE_SHORTS_PATTERN,
        ):
            if match := pattern.match(url):
                return match.group(1)
        return None

    @staticmethod
    async def normalize_youtube_url(url: str) -> Optional[str]:
        """Normalize different YouTube URL formats to standard watch URL."""
        if not url:
            return None

        # Handle youtu.be short links
        if "youtu.be/" in url:
            video_id = url.split("youtu.be/")[1].partition("?")[0].partition("#")[0]
            return f"https://www.youtube.com/watch?v={video_id}"

        # Handle YouTube shorts
        if "youtube.com/shorts/" in url:
            video_id = url.split("youtube.com/shorts/")[1].split("?")[0]
            return f"https://www.youtube.com/watch?v={video_id}"

        return url

    @staticmethod
    def create_platform_tracks(data: Dict[str, Any]) -> PlatformTracks:
        """Create PlatformTracks object from data."""
        if not data or not data.get("results"):
            return PlatformTracks(tracks=[])

        valid_tracks = [
            MusicTrack(**track)
            for track in data["results"]
            if track and track.get("id")
        ]
        return PlatformTracks(tracks=valid_tracks)

    @staticmethod
    def format_track(track_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format track data into a consistent structure."""
        duration = track_data.get("duration", "0:00")
        if isinstance(duration, dict):
            duration = duration.get("secondsText", "0:00")

        # Get the highest quality thumbnail
        cover_url = ""
        if thumbnails := track_data.get("thumbnails"):
            for thumb in reversed(thumbnails):
                if url := thumb.get("url"):
                    cover_url = url
                    break

        return {
            "id": track_data.get("id", ""),
            "name": track_data.get("title", "Unknown Title"),
            "duration": YouTubeUtils.duration_to_seconds(duration),
            "artist": track_data.get("channel", {}).get("name", "Unknown Artist"),
            "cover": cover_url,
            "year": 0,
            "url": f"https://www.youtube.com/watch?v={track_data.get('id', '')}",
            "platform": "youtube",
        }

    @staticmethod
    async def create_track_info(track_data: dict[str, Any]) -> TrackInfo:
        """Create TrackInfo from formatted track data."""
        return TrackInfo(
            cdnurl="None",
            key="None",
            name=track_data.get("name", "Unknown Title"),
            artist=track_data.get("artist", "Unknown Artist"),
            tc=track_data.get("id", ""),
            album="YouTube",
            cover=track_data.get("cover", ""),
            lyrics="None",
            duration=track_data.get("duration", 0),
            platform="youtube",
            url=f"https://youtube.com/watch?v={track_data.get('id', '')}",
            year=track_data.get("year", 0),
        )

    @staticmethod
    def duration_to_seconds(duration: str) -> int:
        """
        Convert duration string (HH:MM:SS or MM:SS) to seconds.

        Args:
            duration: Time string to convert

        Returns:
            int: Duration in seconds
        """
        if not duration:
            return 0

        try:
            parts = list(map(int, duration.split(":")))
            if len(parts) == 3:  # HH:MM:SS
                return parts[0] * 3600 + parts[1] * 60 + parts[2]
            return parts[0] * 60 + parts[1] if len(parts) == 2 else parts[0]
        except (ValueError, AttributeError):
            return 0

    @staticmethod
    async def get_cookie_file() -> Optional[str]:
        """Get cookie file from configured path or fallback to default locations."""
        from TgMusic.core import config
        
        # First check for configured cookies path
        if config.COOKIES_PATH and os.path.exists(config.COOKIES_PATH):
            LOGGER.info("Using configured cookie file: %s", config.COOKIES_PATH)
            return config.COOKIES_PATH
        
        # Fallback to local cookies in project root
        local_cookies = ["cookies.txt", "cookies"]
        for cookie_file in local_cookies:
            if os.path.exists(cookie_file):
                LOGGER.info("Using local cookie file: %s", cookie_file)
                return cookie_file
        
        # Final fallback to TgMusic/cookies directory
        cookie_dir = "TgMusic/cookies"
        try:
            if not os.path.exists(cookie_dir):
                LOGGER.warning("Cookie directory '%s' does not exist.", cookie_dir)
                return None

            files = await asyncio.to_thread(os.listdir, cookie_dir)
            cookies_files = [f for f in files if f.endswith(".txt")]

            if not cookies_files:
                LOGGER.warning("No cookie files found in '%s'.", cookie_dir)
                return None

            # random_file = random.choice(cookies_files)
            # cookie_path = os.path.join(cookie_dir, random_file)
            cookie_path = [os.path.join(cookie_dir, f) for f in cookies_files]
            LOGGER.info("Using cookie file from directory: %s", cookie_path)
            return cookie_path
        except Exception as e:
            LOGGER.warning("Error accessing cookie directory: %s", e)
            return None

    @staticmethod
    async def fetch_oembed_data(url: str) -> Optional[dict[str, Any]]:
        oembed_url = f"https://www.youtube.com/oembed?url={url}&format=json"
        data = await HttpxClient().make_request(oembed_url, max_retries=1)
        if data:
            video_id = url.split("v=")[1]
            return {
                "results": [
                    {
                        "id": video_id,
                        "name": data.get("title"),
                        "duration": 0,
                        "artist": data.get("author_name", ""),
                        "cover": data.get("thumbnail_url", ""),
                        "year": 0,
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                        "platform": "youtube",
                    }
                ]
            }
        return None

    @staticmethod
    async def download_with_api(
        video_id: str, is_video: bool = False
    ) -> Union[None, Path]:
        """
        Download audio using the API.
        """
        from TgMusic import client

        httpx = HttpxClient()
        if public_url := await httpx.make_request(
            f"{config.API_URL}/yt?id={video_id}&video={is_video}"
        ):
            dl_url = public_url.get("results")
            if not dl_url:
                LOGGER.error("Response from API is empty")
                return None

            if not re.fullmatch(r"https:\/\/t\.me\/([a-zA-Z0-9_]{5,})\/(\d+)", dl_url):
                dl = await httpx.download_file(dl_url)
                return dl.file_path if dl.success else None

            info = await client.getMessageLinkInfo(dl_url)
            if isinstance(info, types.Error) or info.message is None:
                LOGGER.error(
                    f"❌ Could not resolve message from link: {dl_url}; {info}"
                )
                return None

            msg = await client.getMessage(info.chat_id, info.message.id)
            if isinstance(msg, types.Error):
                LOGGER.error(
                    f"❌ Failed to fetch message with ID {info.message.id}; {msg}"
                )
                return None

            file = await msg.download()
            if isinstance(file, types.Error):
                LOGGER.error(
                    f"❌ Failed to download message with ID {info.message.id}; {file}"
                )
                return None
            return Path(file.path)
        return None

    @staticmethod
    def _build_ytdlp_params(
        video_id: str, video: bool, cookie_file: Optional[str]
    ) -> list[str]:
        """Construct yt-dlp parameters based on video/audio requirements."""
        output_template = str(config.DOWNLOADS_DIR / "%(id)s.%(ext)s")

        format_selector = (
            "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4][height<=1080]"
            if video
            else "bestaudio[ext=m4a]/bestaudio[ext=mp4]/bestaudio[ext=webm]/bestaudio/best"
        )

        ytdlp_params = [
            "yt-dlp",
            "--no-warnings",
            "--quiet",
            "--geo-bypass",
            "--retries",
            "2",
            "--continue",
            "--no-part",
            "--concurrent-fragments",
            "3",
            "--socket-timeout",
            "10",
            "--throttled-rate",
            "100K",
            "--retry-sleep",
            "1",
            "--no-write-thumbnail",
            "--no-write-info-json",
            "--no-embed-metadata",
            "--no-embed-chapters",
            "--no-embed-subs",
            "-o",
            output_template,
            "-f",
            format_selector,
        ]

        if video:
            ytdlp_params += ["--merge-output-format", "mp4"]

        # if config.PROXY:
        #     ytdlp_params += ["--proxy", config.PROXY]
        # elif cookie_file:
        #     ytdlp_params += ["--cookies", cookie_file]

        PR_OXY = get_proxy()
        if PR_OXY:
            ytdlp_params += ["--proxy", PR_OXY]

        if cookie_file:
            ytdlp_params += ["--cookies", cookie_file]

        video_url = f"https://www.youtube.com/watch?v={video_id}"
        ytdlp_params += [video_url, "--print", "after_move:filepath"]

        return ytdlp_params

    @staticmethod
    async def download_with_yt_dlp(video_id: str, video: bool) -> Optional[Path]:

        cookie_files = await YouTubeUtils.get_cookie_file()
        success_path = None  # Store successful path

        if not cookie_files or all(not c for c in cookie_files):
            LOGGER.warning("No cookie files found, skipping yt-dlp download.")
            return None

        for cookie in cookie_files:
            if not cookie:
                LOGGER.debug("Skipping empty cookie file entry.")
                continue

            ytdlp_params = YouTubeUtils._build_ytdlp_params(video_id, video, cookie)

            try:
                LOGGER.debug("Starting yt-dlp download for video ID: %s with cookie: %s", video_id, cookie)

                proc = await asyncio.create_subprocess_exec(
                    *ytdlp_params,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=600)

                if proc.returncode != 0:
                    LOGGER.error(
                        "yt-dlp failed for %s (code %d) with cookie %s: %s",
                        video_id,
                        proc.returncode,
                        cookie,
                        stderr.decode().strip(),
                    )
                    continue

                downloaded_path_str = stdout.decode().strip()
                if not downloaded_path_str:
                    LOGGER.error(
                        "yt-dlp finished but no output path returned for %s with cookie %s",
                        video_id, cookie
                    )
                    continue

                downloaded_path = Path(downloaded_path_str)
                if not downloaded_path.exists():
                    LOGGER.error(
                        "yt-dlp reported path but file not found: %s", downloaded_path
                    )
                    continue

                LOGGER.info("Successfully downloaded %s to %s using cookie %s", video_id, downloaded_path, cookie)
                success_path = downloaded_path
                break  # Stop trying cookies after first success

            except asyncio.TimeoutError:
                LOGGER.error("yt-dlp timed out for video ID: %s with cookie %s", video_id, cookie)
                continue
            except Exception as e:
                LOGGER.error(
                    "Unexpected error downloading %s with cookie %s: %r", video_id, cookie, e, exc_info=True
                )
                continue

        return success_path

async def search_video(session: aiohttp.ClientSession, keyword: str) -> tuple:
    for instance in INVIDIOUS_INSTANCES:
        try:
            search_url = f"{instance}/api/v1/search?q={keyword}&type=video"
            async with session.get(search_url, timeout=10) as resp:
                if resp.status == 200:
                    results = await resp.json()
                    if results:
                        return results[0], instance
                else:
                    print(f"[WARN] {instance} returned status {resp.status}")
        except Exception as e:
            print(f"[WARN] Error with {instance}: {e}")
    raise RuntimeError(f"No search results found for '{keyword}'")

def resolution_value(ql):
    if not ql:
        return 0
    try:
        return int(ql.replace("p", "").strip())
    except:
        return 0

async def get_best_streams(session: aiohttp.ClientSession, instance: str, video_id: str, video: bool):
    details_url = f"{instance}/api/v1/videos/{video_id}"
    async with session.get(details_url, timeout=10) as resp:
        resp.raise_for_status()
        data = await resp.json()

    adaptive = data.get("adaptiveFormats", [])

    if video:
        # Highest quality video stream
        video_streams = [s for s in adaptive if "video" in s.get("type", "")]
        best_video = max(video_streams, key=lambda s: resolution_value(s.get("qualityLabel")), default=None)

        # Highest quality audio stream
        audio_streams = [s for s in adaptive if "audio" in s.get("type", "")]
        best_audio = max(audio_streams, key=lambda s: s.get("bitrate", 0), default=None)

        if not best_video or not best_audio:
            raise RuntimeError("Could not find both video and audio streams.")
        return data.get("title", video_id), best_video["url"], best_audio["url"], "mp4"
    else:
        # Audio only mode
        audio_streams = [s for s in adaptive if "audio" in s.get("type", "")]
        best_audio = max(audio_streams, key=lambda s: s.get("bitrate", 0), default=None)
        if not best_audio:
            raise RuntimeError("No audio streams found.")
        return data.get("title", video_id), best_audio["url"], None, "m4a"

def get_ext_from_url(url: str, default: str = "webm") -> str:
    """Extract file extension from YouTube stream URL, fallback to default."""
    try:
        qs = parse_qs(urlparse(url).query)
        if "mime" in qs:
            mime = qs["mime"][0]  # e.g., 'audio/webm'
            ext = mime.split("/")[1]
            return ext
    except Exception:
        pass
    return default

async def download_stream(url: str, output_path: str):
    """Download a single stream (video or audio) with proper headers."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.youtube.com/",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9"
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise Exception(f"Failed to download stream: HTTP {resp.status}")
            with open(output_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(8192):
                    f.write(chunk)

async def safe_download_stream(session, url, output_path, retries=2):
    """Download stream with retry on HTTP 403."""
    for attempt in range(retries):
        try:
            await download_stream(url, output_path)
            return
        except Exception as e:
            if "HTTP 403" in str(e):
                print(f"[WARN] 403 Forbidden, retrying ({attempt + 1}/{retries})...")
                await asyncio.sleep(1)
            else:
                raise
    raise RuntimeError(f"Failed to download stream after {retries} retries: {url}")

async def search_and_download(keyword: str, vid_id=False, output_dir="/app/database/music/", video=True) -> str:
    os.makedirs(output_dir, exist_ok=True)
    temp_dir = Path(output_dir) / "tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    async with aiohttp.ClientSession() as session:
        for instance in INVIDIOUS_INSTANCES:
            try:
                video_data, _ = await search_video(session, keyword)
                video_id = video_data.get("videoId")
                title, primary_url, secondary_url, ext = await get_best_streams(session, instance, video_id, video)
                safe_title = video_id
                output_path = os.path.join(output_dir, f"{safe_title}.{ext}")

                primary_ext = get_ext_from_url(primary_url, default=ext)
                secondary_ext = get_ext_from_url(secondary_url, default="webm") if video else None

                primary_file = temp_dir / f"{safe_title}_video.{primary_ext}" if video else temp_dir / f"{safe_title}_audio.{primary_ext}"
                secondary_file = temp_dir / f"{safe_title}_audio.{secondary_ext}" if video and secondary_url else None

                print(f"[INFO] Downloading streams from {instance}...")
                await safe_download_stream(session, primary_url, str(primary_file))
                if video and secondary_url:
                    await safe_download_stream(session, secondary_url, str(secondary_file))

                print("[INFO] Merging with ffmpeg...")
                if video and secondary_url:
                    subprocess.run([
                        "ffmpeg", "-y",
                        "-i", str(primary_file),
                        "-i", str(secondary_file),
                        "-c", "copy",
                        "-movflags", "+faststart",
                        output_path
                    ], check=True)
                else:
                    subprocess.run([
                        "ffmpeg", "-y",
                        "-i", str(primary_file),
                        "-vn",
                        "-c:a", "aac",
                        "-b:a", "192k",
                        "-movflags", "+faststart",
                        output_path
                    ], check=True)

                # Cleanup
                for f in [primary_file, secondary_file]:
                    if f and f.exists():
                        f.unlink()

                print(f"[DONE] Saved at: {output_path}")
                return output_path
            except Exception as e:
                print(f"[WARN] Instance {instance} failed: {e}, trying next...")
        raise RuntimeError(f"All Invidious instances failed for '{keyword}'")

class YouTubeData(MusicService):
    """Handles YouTube music data operations including:
    - URL validation
    - Track information retrieval
    - Search functionality
    - Audio/video downloads

    Uses both direct API calls and YouTube Data API for comprehensive coverage.
    """

    def __init__(self, query: Optional[str] = None) -> None:
        """Initialize with optional query (URL or search term).

        Args:
            query: YouTube URL or search term to process
        """
        self.query = YouTubeUtils.clean_query(query) if query else None

    def is_valid(self, url: Optional[str]) -> bool:
        """Validate YouTube URL format.

        Args:
            url: URL to validate

        Returns:
            bool: True if URL matches YouTube patterns
        """
        return YouTubeUtils.is_valid_url(url)

    async def get_info(self) -> Union[PlatformTracks, types.Error]:
        """Retrieve track information from YouTube URL.

        Returns:
            PlatformTracks: Contains track metadata
            types.Error: If URL is invalid or request fails
        """
        if not self.query or not self.is_valid(self.query):
            return types.Error(code=400, message="Invalid YouTube URL provided")

        data = await self._fetch_data(self.query)
        if not data:
            return types.Error(code=404, message="Could not retrieve track information")

        return YouTubeUtils.create_platform_tracks(data)

    async def search(self) -> Union[PlatformTracks, types.Error]:
        """Search YouTube for tracks matching the query.

        Returns:
            PlatformTracks: Contains search results
            types.Error: If query is invalid or search fails
        """
        if not self.query:
            return types.Error(code=400, message="No search query provided")

        # Handle direct URL searches
        if self.is_valid(self.query):
            return await self.get_info()

        try:
            search = VideosSearch(self.query, limit=5)
            results = await search.next()

            if not results or not results.get("result"):
                return types.Error(
                    code=404, message=f"No results found for: {self.query}"
                )

            tracks = [
                MusicTrack(**YouTubeUtils.format_track(video))
                for video in results["result"]
            ]
            return PlatformTracks(tracks=tracks)

        except Exception as error:
            LOGGER.error(f"YouTube search failed for '{self.query}': {error}")
            return types.Error(code=500, message=f"Search failed: {str(error)}")

    async def get_track(self) -> Union[TrackInfo, types.Error]:
        """Get detailed track information.

        Returns:
            TrackInfo: Detailed track metadata
            types.Error: If track cannot be found
        """
        if not self.query:
            return types.Error(code=400, message="No track identifier provided")

        # Normalize URL/ID format
        url = (
            self.query
            if re.match("^https?://", self.query)
            else f"https://youtube.com/watch?v={self.query}"
        )

        data = await self._fetch_data(url)
        if not data or not data.get("results"):
            return types.Error(code=404, message="Could not retrieve track details")

        return await YouTubeUtils.create_track_info(data["results"][0])

    async def download_track(
        self, track: TrackInfo, video: bool = False
    ) -> Union[Path, types.Error]:
        """Download audio/video track from YouTube.

        Args:
            track: TrackInfo containing download details
            video: Whether to download video (default: False)

        Returns:
            Path: Location of downloaded file
            types.Error: If download fails
        """
        if not track:
            return types.Error(code=400, message="Invalid track information provided")

        # Try API download first if configured
        if config.API_URL and config.API_KEY:
            if api_result := await YouTubeUtils.download_with_api(track.tc, video):
                return api_result

        # custom download
        try:
            dl_path = await search_and_download(track.tc, video=video)
            if not dl_path:
                pass
            return dl_path
        except Exception as e:
            print(e)
            pass

        # Fall back to yt-dlp if API fails or not configured
        dl_path = await YouTubeUtils.download_with_yt_dlp(track.tc, video)
        if not dl_path:
            return types.Error(
                code=500, message="Failed to download track from YouTube"
            )

        return dl_path

    async def _fetch_data(self, url: str) -> Optional[Dict[str, Any]]:
        """Internal method to fetch YouTube data.

        Handles both videos and playlists.
        """
        try:
            if YouTubeUtils.YOUTUBE_PLAYLIST_PATTERN.match(url):
                LOGGER.debug(f"Processing YouTube playlist: {url}")
                return await self._get_playlist_data(url)

            LOGGER.debug(f"Processing YouTube video: {url}")
            return await self._get_video_data(url)
        except Exception as error:
            LOGGER.error(f"Data fetch failed for {url}: {error}")
            return None

    @staticmethod
    async def _get_video_data(url: str) -> Optional[Dict[str, Any]]:
        """Retrieve metadata for a single YouTube video."""
        normalized_url = await YouTubeUtils.normalize_youtube_url(url)
        if not normalized_url:
            return None

        # Try oEmbed first
        if oembed_data := await YouTubeUtils.fetch_oembed_data(normalized_url):
            return oembed_data

        # Fall back to search API
        try:
            search = VideosSearch(normalized_url, limit=1)
            results = await search.next()

            if not results or not results.get("result"):
                return None

            return {"results": [YouTubeUtils.format_track(results["result"][0])]}
        except Exception as error:
            LOGGER.error(f"Video data fetch failed: {error}")
            return None

    @staticmethod
    async def _get_playlist_data(url: str) -> Optional[Dict[str, Any]]:
        """Retrieve metadata for a YouTube playlist."""
        try:
            playlist = await Playlist.getVideos(url)
            if not playlist or not playlist.get("videos"):
                return None

            return {
                "results": [
                    YouTubeUtils.format_track(track)
                    for track in playlist["videos"]
                    if track.get("id")  # Filter valid tracks
                ]
            }
        except Exception as error:
            LOGGER.error(f"Playlist data fetch failed: {error}")
            return None

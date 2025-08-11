#  Copyright (c) 2025 AshokShau
#  Licensed under the GNU AGPL v3.0: https://www.gnu.org/licenses/agpl-3.0.html
#  Part of the TgMusicBot project. All rights reserved where applicable.
#  Modified by Devin - Major modifications and improvements

import re

from pytdbot import Client, types

from TgMusic.core import YouTubeData, DownloaderWrapper, db, call, tg
from TgMusic.core import (
    CachedTrack,
    MusicTrack,
    PlatformTracks,
    chat_cache,
)
from TgMusic.logger import LOGGER
from TgMusic.core import (
    Filter,
    SupportButton,
    control_buttons,
    language_manager,
)
from TgMusic.core.admins import is_admin, load_admin_cache
from TgMusic.core.error_handler import error_handler_decorator, ErrorSeverity, ErrorResponse
from TgMusic.core.metrics import metrics_manager, performance_monitor
from TgMusic.modules.utils import sec_to_min, get_audio_duration
from TgMusic.modules.utils.play_helpers import (
    del_msg,
    edit_text,
    extract_argument,
    get_url,
    reply_auto_delete_message,
)
from TgMusic.core.thumbnails import gen_thumb


def _get_jiosaavn_url(track_id: str) -> str:
    """Generate JioSaavn URL from track ID."""
    try:
        title, song_id = track_id.rsplit("/", 1)
    except ValueError:
        return ""
    title = re.sub(r'[\(\)"\',]', "", title.lower()).replace(" ", "-")
    return f"https://www.jiosaavn.com/song/{title}/{song_id}"


def _get_platform_url(platform: str, track_id: str) -> str:
    """Generate platform URL from track ID based on platform."""
    platform = platform.lower()
    if not track_id:
        return ""

    platform_urls = {
        "youtube": f"https://youtube.com/watch?v={track_id}",
        "spotify": f"https://open.spotify.com/track/{track_id}",
        "jiosaavn": _get_jiosaavn_url(track_id),
    }
    return platform_urls.get(platform, "")


def build_song_selection_message(
    user_by: str, tracks: list[MusicTrack]
) -> tuple[str, types.ReplyMarkupInlineKeyboard]:
    """Build interactive song selection message with inline keyboard."""
    greeting = f"{user_by}, select a track:" if user_by else "Select a track:"
    buttons = [
        [
            types.InlineKeyboardButton(
                text=f"{track.name[:18]} - {track.artist}",
                type=types.InlineKeyboardButtonTypeCallback(
                    f"play_{track.platform.lower()}_{track.id}".encode()
                ),
            )
        ]
        for track in tracks[:4]  # Show first 4 results
    ]
    return greeting, types.ReplyMarkupInlineKeyboard(buttons)


async def _update_msg_with_thumb(
    c: Client,
    msg: types.Message,
    text: str,
    thumb: str,
    button: types.ReplyMarkupInlineKeyboard,
):
    """Update message with thumbnail if available."""
    if not thumb:
        return await edit_text(
            msg, text=text, reply_markup=button, disable_web_page_preview=True
        )

    parsed_text = await c.parseTextEntities(text, types.TextParseModeHTML())
    if isinstance(parsed_text, types.Error):
        return await edit_text(msg, text=parsed_text.message, reply_markup=button)

    input_content = types.InputMessagePhoto(
        types.InputFileLocal(thumb), caption=parsed_text
    )
    edit_result = await c.editMessageMedia(
        chat_id=msg.chat_id,
        message_id=msg.id,
        input_message_content=input_content,
        reply_markup=button,
    )

    return edit_result


async def _handle_single_track(
    c: Client,
    msg: types.Message,
    track: MusicTrack,
    user_by: str,
    file_path: str = None,
    is_video: bool = False,
):
    chat_id = msg.chat_id
    song = CachedTrack(
        name=track.name,
        artist=track.artist,
        track_id=track.id,
        loop=0,
        duration=track.duration,
        file_path=file_path or "",
        thumbnail=track.cover,
        user=user_by,
        platform=track.platform,
        is_video=is_video,
        url=track.url,
    )

    # Download track if not already cached
    if not song.file_path:
        download_result = await call.song_download(song)
        user_lang = await language_manager.get_language(msg.from_id, msg.chat_id)
        if isinstance(download_result, types.Error):
            return await edit_text(
                msg, language_manager.get_text("playback_download_failed", user_lang, error=download_result.message)
            )

        song.file_path = download_result
        if not download_result:
            return await edit_text(msg, language_manager.get_text("playback_failed", user_lang))

    # Get duration if not provided
    song.duration = song.duration or await get_audio_duration(song.file_path)

    if chat_cache.is_active(chat_id):
        # Add to queue if playback is active
        queue = chat_cache.get_queue(chat_id)
        chat_cache.add_song(chat_id, song)

        queue_info = (
            f"<b>🎧 Added to Queue (#{len(queue)})</b>\n\n"
            f"▫ <b>Track:</b> <a href='{song.url}'>{song.name}</a>\n"
            f"▫ <b>Duration:</b> {sec_to_min(song.duration)}\n"
            f"▫ <b>Requested by:</b> {song.user}"
        )

        thumb = await gen_thumb(song) if await db.get_thumbnail_status(chat_id) else ""
        return await _update_msg_with_thumb(
            c,
            msg,
            queue_info,
            thumb,
            control_buttons("play") if await db.get_buttons_status(chat_id) else None,
        )

    # Start new playback session
    chat_cache.set_active(chat_id, True)
    chat_cache.add_song(chat_id, song)

    play_result = await call.play_media(chat_id, song.file_path, video=is_video)
    if isinstance(play_result, types.Error):
        user_lang = await language_manager.get_language(msg.from_id, msg.chat_id)
        return await edit_text(msg, text=language_manager.get_text("playback_error", user_lang, error=play_result.message))

    # Prepare now playing message
    thumb = await gen_thumb(song) if await db.get_thumbnail_status(chat_id) else ""
    user_lang = await language_manager.get_language(msg.from_id, msg.chat_id)
    bot_name = c.me.first_name
    now_playing = (f"""<blockquote>🎵 <b>Now Playing</b>
🎼 <b>Title:</b> <code>{song.name}</code>

🕒 <b>Duration:</b> {sec_to_min(song.duration)}
🙋 <b>Requested by:</b> {song.user}</blockquote>

-▸ Powered by {bot_name} ⚡"""
    )

    update_result = await _update_msg_with_thumb(
        c,
        msg,
        now_playing,
        thumb,
        control_buttons("play") if await db.get_buttons_status(chat_id) else None,
    )

    if isinstance(update_result, types.Error):
        LOGGER.warning("Message update failed: %s", update_result)
    return None


async def _handle_multiple_tracks(
    msg: types.Message, tracks: list[MusicTrack], user_by: str
):
    """Process and queue multiple tracks (playlist/album)."""
    chat_id = msg.chat_id
    is_active = chat_cache.is_active(chat_id)
    queue = chat_cache.get_queue(chat_id)

    queue_header = "╭─────────────⭓\n📥 <b>Added to Queue</b>\n"
    queue_items = []

    for index, track in enumerate(tracks):
        position = len(queue) + index
        chat_cache.add_song(
            chat_id,
            CachedTrack(
                name=track.name,
                artist=track.artist,
                track_id=track.id,
                loop=1 if not is_active and index == 0 else 0,
                duration=track.duration,
                thumbnail=track.cover,
                user=user_by,
                file_path="",
                platform=track.platform,
                is_video=False,
                url=track.url,
            ),
        )
        queue_items.append(
            f"┣▹ 🎼 <b>{position}.</b> <code>{track.name}</code>\n┣▹ 🕒 <b>Duration:</b> {sec_to_min(track.duration)}"
        )

    queue_summary = (
        f"╰▹ 📊 <b>Total in Queue:</b> {len(chat_cache.get_queue(chat_id))}\n"
        f"╰▹ ⏱ <b>Total Duration:</b> {sec_to_min(sum(t.duration for t in tracks))}\n"
        f"╰▹ 🙋 <b>Requested by:</b> {user_by}"
    )

    full_message = queue_header + "\n".join(queue_items) + queue_summary

    # Handle message length limit
    if len(full_message) > 4096:
        full_message = queue_summary

    if not is_active:
        await call.play_next(chat_id)

    await edit_text(msg, full_message, reply_markup=control_buttons("play"))


async def play_music(
    c: Client,
    msg: types.Message,
    url_data: PlatformTracks,
    user_by: str,
    tg_file_path: str = None,
    is_video: bool = False,
):
    """Main music playback handler for both single tracks and playlists."""
    if not url_data or not url_data.tracks:
        user_lang = await language_manager.get_language(msg.from_id, msg.chat_id)
        return await edit_text(msg, language_manager.get_text("playback_no_tracks", user_lang))

    await edit_text(msg, text="🔍")

    if len(url_data.tracks) == 1:
        return await _handle_single_track(
            c, msg, url_data.tracks[0], user_by, tg_file_path, is_video
        )
    return await _handle_multiple_tracks(msg, url_data.tracks, user_by)


async def _handle_telegram_file(
    c: Client, reply: types.Message, reply_message: types.Message, user_by: str
):
    """Process Telegram audio/video file attachments."""
    content = reply.content
    is_video = isinstance(content, (types.MessageVideo, types.Video)) or (
        isinstance(content, (types.MessageDocument, types.Document))
        and getattr(content, "mime_type", "").startswith("video/")
    )

    # Download the attached file
    file_path, file_name = await tg.download_msg(reply, reply_message)
    if isinstance(file_path, types.Error):
        return await edit_text(
            reply_message,
            text=(
                "<b>⚠️ Download Failed</b>\n\n"
                f"▫ <b>File:</b> <code>{file_name}</code>\n"
                f"▫ <b>Error:</b> <code>{file_path.message}</code>"
            ),
        )

    duration = await get_audio_duration(file_path.path)
    track_data = PlatformTracks(
        tracks=[
            MusicTrack(
                name=file_name,
                artist="Ashok-Shau",
                id=reply.remote_unique_file_id,
                year=0,
                cover="",
                duration=duration,
                url="",
                platform="telegram",
            )
        ]
    )

    await play_music(c, reply_message, track_data, user_by, file_path.path, is_video)
    return None


async def _handle_text_search(
    c: Client,
    msg: types.Message,
    wrapper,
    user_by: str,
):
    """Handle text-based music searches."""
    chat_id = msg.chat_id
    play_type = await db.get_play_type(chat_id)

    search_result = await wrapper.search()
    if isinstance(search_result, types.Error):
        return await edit_text(
            msg,
            text=f"🔍 Search failed: {search_result.message}",
            reply_markup=SupportButton,
        )

    if not search_result or not search_result.tracks:
        return await edit_text(
            msg,
            text="🔍 No results found. Try different keywords.",
            reply_markup=SupportButton,
        )

    # Direct play if configured
    if play_type == 0:
        track_url = search_result.tracks[0].url
        # Use appropriate wrapper based on URL
        if "youtube.com" in track_url or "youtu.be" in track_url:
            track_info = await YouTubeData(track_url).get_info()
        else:
            track_info = await DownloaderWrapper(track_url).get_info()
        if isinstance(track_info, types.Error):
            return await edit_text(
                msg,
                text=f"⚠️ Track info error: {track_info.message}",
                reply_markup=SupportButton,
            )
        return await play_music(c, msg, track_info, user_by)

    # Show selection menu
    selection_text, selection_keyboard = build_song_selection_message(
        user_by, search_result.tracks
    )
    await edit_text(
        msg,
        text=selection_text,
        reply_markup=selection_keyboard,
        disable_web_page_preview=True,
    )
    return None


@performance_monitor("play_command")
@error_handler_decorator("play_command", ErrorSeverity.MEDIUM)
async def handle_play_command(c: Client, msg: types.Message, is_video: bool = False):
    """Main handler for /play and /vplay commands with enhanced error handling."""
    chat_id = msg.chat_id
    user_id = msg.from_id

    # Record command execution
    metrics_manager.bot_metrics.record_command("play", success=True)
    metrics_manager.bot_metrics.active_chats.add(chat_id)

    try:
        user_lang = await language_manager.get_language(msg.from_id, msg.chat_id)
        
        # Validate chat type
        if chat_id > 0:
            metrics_manager.bot_metrics.record_command("play", success=False, error="private_chat")
            return await msg.reply_text(language_manager.get_text("playback_groups_only", user_lang))

        # Track activity for this chat
        await db.update_chat_activity(chat_id)
        chat_cache.update_activity(chat_id)

        # Check queue limit with better error handling
        queue = chat_cache.get_queue(chat_id)
        if len(queue) > 10:
            metrics_manager.bot_metrics.record_command("play", success=False, error="queue_limit")
            return await msg.reply_text(
                language_manager.get_text("playback_queue_limit", user_lang)
            )

        # Verify bot admin status
        await load_admin_cache(c, chat_id)
        if not await is_admin(chat_id, c.me.id):
            metrics_manager.bot_metrics.record_command("play", success=False, error="admin_required")
            return await msg.reply_text(
                language_manager.get_text("playback_admin_required", user_lang)
            )

        # Get message context with error handling
        try:
            reply = await msg.getRepliedMessage() if msg.reply_to_message_id else None
            url = await get_url(msg, reply)
            args = extract_argument(msg.text)
        except Exception as e:
            LOGGER.error(f"Error getting message context: {e}")
            metrics_manager.bot_metrics.record_command("play", success=False, error="context_error")
            return await msg.reply_text("❌ Error processing message context")

        # Send initial response with error handling
        try:
            status_msg = await msg.reply_text(language_manager.get_text("playback_processing", user_lang))
            if isinstance(status_msg, types.Error):
                LOGGER.error("Failed to send status message: %s", status_msg)
                metrics_manager.bot_metrics.record_command("play", success=False, error="status_msg_failed")
                return None
        except Exception as e:
            LOGGER.error(f"Error sending status message: {e}")
            return None

        await del_msg(msg)  # Clean up command message

        # Initialize appropriate downloader with error handling
        try:
            # For video, always use YouTubeData for search
            if is_video:
                wrapper = YouTubeData(url or args)
            else:
                # For audio, use YouTubeData for YouTube URLs, DownloaderWrapper for others
                if url and ("youtube.com" in url or "youtu.be" in url):
                    wrapper = YouTubeData(url)
                else:
                    wrapper = DownloaderWrapper(url or args)
        except Exception as e:
            LOGGER.error(f"Error initializing downloader: {e}")
            metrics_manager.bot_metrics.record_command("play", success=False, error="downloader_init")
            return await edit_text(status_msg, text="❌ Error initializing downloader")

        # Validate input
        if not args and not url and (not reply or not tg.is_valid(reply)):
            usage_text = (
                language_manager.get_text("playback_usage", user_lang) +
                f"/{'vplay' if is_video else 'play'} [song_name|URL]\n\n"
                "Supported platforms:\n"
                "▫ YouTube\n▫ Spotify\n▫ JioSaavn\n▫ SoundCloud\n▫ Apple Music"
            )
            return await edit_text(status_msg, text=usage_text, reply_markup=SupportButton)

        requester = await msg.mention()

        # Handle Telegram file attachments
        if reply and tg.is_valid(reply):
            return await _handle_telegram_file(c, reply, status_msg, requester)

        # Handle URL playback with enhanced error handling
        if url:
            if not wrapper.is_valid(url):
                metrics_manager.bot_metrics.record_command("play", success=False, error="unsupported_url")
                return await edit_text(
                    status_msg,
                    text=(
                        language_manager.get_text("playback_unsupported_url", user_lang) +
                        "Supported platforms:\n"
                        "▫ YouTube\n▫ Spotify\n▫ JioSaavn\n▫ SoundCloud\n▫ Apple Music"
                    ),
                    reply_markup=SupportButton,
                )

            try:
                track_info = await wrapper.get_info()
                if isinstance(track_info, types.Error):
                    metrics_manager.bot_metrics.record_command("play", success=False, error="track_info_error")
                    return await edit_text(
                        status_msg,
                        text=language_manager.get_text("playback_track_info_error_retrieve", user_lang, error=track_info.message),
                        reply_markup=SupportButton,
                    )
            except Exception as e:
                LOGGER.error(f"Error getting track info: {e}")
                metrics_manager.bot_metrics.record_command("play", success=False, error="track_info_exception")
                return await edit_text(status_msg, text="❌ Error retrieving track information")

            return await play_music(c, status_msg, track_info, requester, is_video=is_video)

        # Handle text search for audio only
        if not is_video:
            return await _handle_text_search(c, status_msg, wrapper, requester)

        # Handle video search with error handling
        try:
            search_result = await wrapper.search()
            if isinstance(search_result, types.Error):
                metrics_manager.bot_metrics.record_command("play", success=False, error="search_failed")
                return await edit_text(
                    status_msg,
                    text=language_manager.get_text("playback_search_failed", user_lang, error=search_result.message),
                    reply_markup=SupportButton,
                )

            if not search_result or not search_result.tracks:
                metrics_manager.bot_metrics.record_command("play", success=False, error="no_results")
                return await edit_text(
                    status_msg,
                    text=language_manager.get_text("playback_no_results", user_lang),
                    reply_markup=SupportButton,
                )

            # Play first video result
            video_info = await YouTubeData(search_result.tracks[0].url).get_info()
            if isinstance(video_info, types.Error):
                return await edit_text(
                    status_msg,
                    text=f"⚠️ Video error: {video_info.message}",
                    reply_markup=SupportButton,
                )

            return await play_music(c, status_msg, video_info, requester, is_video=True)
            
        except Exception as e:
            LOGGER.error(f"Error in video search: {e}")
            metrics_manager.bot_metrics.record_command("play", success=False, error="video_search_exception")
            return await edit_text(status_msg, text="❌ Error during video search")
            
    except Exception as e:
        metrics_manager.bot_metrics.record_command("play", success=False, error=str(e))
        LOGGER.error(f"Error in play command for chat {chat_id}: {e}", exc_info=True)
        
        # Send user-friendly error message
        user_lang = await language_manager.get_language(msg.from_id, chat_id)
        error_response = ErrorResponse.from_exception(e, user_friendly=True)
        await reply_auto_delete_message(
            c, msg,
            f"❌ {error_response.message}",
            delay=10
        )
        raise


@Client.on_message(filters=Filter.command("play"))
async def play_audio(c: Client, msg: types.Message) -> None:
    """Audio playback command handler."""
    await handle_play_command(c, msg, False)


@Client.on_message(filters=Filter.command("vplay"))
async def play_video(c: Client, msg: types.Message) -> None:
    """Video playback command handler."""
    await handle_play_command(c, msg, True)

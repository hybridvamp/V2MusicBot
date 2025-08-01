# Copyright (c) 2025 AshokShau
# Licensed under the GNU AGPL v3.0: https://www.gnu.org/licenses/agpl-3.0.html
# Part of the TgMusicBot project. All rights reserved where applicable.


from pytdbot import Client, types

from TgMusic.core import Filter, language_manager, chat_cache, call
from TgMusic.core.admins import is_admin
from .utils import sec_to_min
from .utils.play_helpers import extract_argument


@Client.on_message(filters=Filter.command("seek"))
async def seek_song(_: Client, msg: types.Message) -> None:
    """Seek to a specific position in the currently playing track."""
    chat_id = msg.chat_id

    if chat_id > 0:
        return

    if not await is_admin(chat_id, msg.from_id):
        await msg.reply_text("⛔ Administrator privileges required.")
        return

    curr_song = chat_cache.get_playing_track(chat_id)
    if not curr_song:
        await msg.reply_text("⏸ No track is currently playing.")
        return

    args = extract_argument(msg.text, enforce_digit=True)
    if not args:
        await msg.reply_text(
            "ℹ️ <b>Usage:</b> <code>/seek [seconds]</code>\n"
            "Example: <code>/seek 30</code> to jump 30 seconds forward"
        )
        return

    try:
        seek_time = int(args)
    except ValueError:
        user_lang = await language_manager.get_language(msg.from_id, msg.chat_id)
        await msg.reply_text(language_manager.get_text("seek_invalid_number", user_lang))
        return

    if seek_time < 0:
        user_lang = await language_manager.get_language(msg.from_id, msg.chat_id)
        await msg.reply_text(language_manager.get_text("seek_positive_number", user_lang))
        return

    if seek_time < 20:
        user_lang = await language_manager.get_language(msg.from_id, msg.chat_id)
        await msg.reply_text(language_manager.get_text("seek_minimum_time", user_lang))
        return

    curr_dur = await call.played_time(chat_id)
    if isinstance(curr_dur, types.Error):
        user_lang = await language_manager.get_language(msg.from_id, msg.chat_id)
        await msg.reply_text(language_manager.get_text("seek_duration_error", user_lang, error=curr_dur.message))
        return

    seek_to = curr_dur + seek_time
    if seek_to >= curr_song.duration:
        max_duration = sec_to_min(curr_song.duration)
        user_lang = await language_manager.get_language(msg.from_id, msg.chat_id)
        await msg.reply_text(language_manager.get_text("seek_beyond_duration", user_lang, duration=max_duration))
        return

    _seek = await call.seek_stream(
        chat_id,
        curr_song.file_path,
        seek_to,
        curr_song.duration,
        curr_song.is_video,
    )
    if isinstance(_seek, types.Error):
        user_lang = await language_manager.get_language(msg.from_id, msg.chat_id)
        await msg.reply_text(language_manager.get_text("seek_error", user_lang, error=_seek.message))
        return

    user_lang = await language_manager.get_language(msg.from_id, msg.chat_id)
    await msg.reply_text(
        language_manager.get_text("seek_success", user_lang, seconds=seek_time, user=await msg.mention()) +
        f"\n{language_manager.get_text('seek_now_at', user_lang)} {sec_to_min(seek_to)}/{sec_to_min(curr_song.duration)}"
    )

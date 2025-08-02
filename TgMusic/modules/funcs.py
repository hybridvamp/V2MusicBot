#  Copyright (c) 2025 AshokShau
#  Licensed under the GNU AGPL v3.0: https://www.gnu.org/licenses/agpl-3.0.html
#  Part of the TgMusicBot project. All rights reserved where applicable.
#  Modified by Devin - Major modifications and improvements

from typing import Union
from pytdbot import Client, types

from TgMusic.core import Filter, language_manager, chat_cache, call, db
from TgMusic.core.admins import is_admin
from TgMusic.modules.utils.play_helpers import extract_argument


@Client.on_message(filters=Filter.command(["playtype", "setPlayType"]))
async def set_play_type(_: Client, msg: types.Message) -> None:
    """Configure playback mode."""
    chat_id = msg.chat_id
    if chat_id > 0:
        return

    if not await is_admin(chat_id, msg.from_id):
        await msg.reply_text("⛔ Administrator privileges required")
        return

    # Track activity for group chats
    await db.update_chat_activity(chat_id)
    chat_cache.update_activity(chat_id)

    play_type = extract_argument(msg.text, enforce_digit=True)
    if not play_type:
        text = "Usage: /setPlayType 0/1\n\n0 = Directly play the first search result.\n1 = Show a list of songs to choose from."
        await msg.reply_text(text)
        return

    play_type = int(play_type)
    if play_type not in (0, 1):
        user_lang = await language_manager.get_language(msg.from_id, msg.chat_id)
        await msg.reply_text(language_manager.get_text("func_invalid_mode", user_lang))
        return

    await db.set_play_type(chat_id, play_type)
    await msg.reply_text(f"🔀 Playback mode set to: <b>{play_type}</b>")


async def is_admin_or_reply(
    msg: types.Message,
) -> Union[int, types.Message, types.Error]:
    """Verify admin status and active playback session."""
    chat_id = msg.chat_id

    if not chat_cache.is_active(chat_id):
        return await msg.reply_text("⏸ No active playback session")

    if not await is_admin(chat_id, msg.from_id):
        return await msg.reply_text("⛔ Administrator privileges required")

    return chat_id


async def handle_playback_action(
    c: Client, msg: types.Message, action, success_msg: str, fail_msg: str
) -> None:
    """Handle common playback control operations."""
    _chat_id = await is_admin_or_reply(msg)
    if isinstance(_chat_id, types.Error):
        user_lang = await language_manager.get_language(msg.from_id, msg.chat_id)
        c.logger.warning(language_manager.get_text("func_admin_check_failed", user_lang, error=_chat_id.message))
        return

    if isinstance(_chat_id, types.Message):
        return

    # Track activity for group chats
    if _chat_id < 0:
        await db.update_chat_activity(_chat_id)
        chat_cache.update_activity(_chat_id)

    result = await action(_chat_id)
    if isinstance(result, types.Error):
        user_lang = await language_manager.get_language(msg.from_id, msg.chat_id)
        await msg.reply_text(language_manager.get_text("func_error", user_lang, message=fail_msg, error=result.message))
        return

    await msg.reply_text(f"{success_msg}\n" f"└ Requested by: {await msg.mention()}")


@Client.on_message(filters=Filter.command("pause"))
async def pause_song(c: Client, msg: types.Message) -> None:
    """Pause current playback."""
    await handle_playback_action(
        c, msg, call.pause, "⏸ Playback paused", "Failed to pause playback"
    )


@Client.on_message(filters=Filter.command("resume"))
async def resume(c: Client, msg: types.Message) -> None:
    """Resume paused playback."""
    await handle_playback_action(
        c, msg, call.resume, "▶️ Playback resumed", "Failed to resume playback"
    )


@Client.on_message(filters=Filter.command("mute"))
async def mute_song(c: Client, msg: types.Message) -> None:
    """Mute audio playback."""
    await handle_playback_action(
        c, msg, call.mute, "🔇 Audio muted", "Failed to mute audio"
    )


@Client.on_message(filters=Filter.command("unmute"))
async def unmute_song(c: Client, msg: types.Message) -> None:
    """Unmute audio playback."""
    await handle_playback_action(
        c, msg, call.unmute, "🔊 Audio unmuted", "Failed to unmute audio"
    )

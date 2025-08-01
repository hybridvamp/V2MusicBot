#  Copyright (c) 2025 AshokShau
#  Licensed under the GNU AGPL v3.0: https://www.gnu.org/licenses/agpl-3.0.html
#  Part of the TgMusicBot project. All rights reserved where applicable.
#  Modified by Devin - Major modifications and improvements


import re

from pytdbot import Client, types

from TgMusic.core import Filter, language_manager, chat_cache, call
from TgMusic.core.admins import is_admin


def extract_number(text: str) -> float | None:
    """Extract a numerical value from text."""
    match = re.search(r"[-+]?\d*\.?\d+", text)
    return float(match.group()) if match else None


@Client.on_message(filters=Filter.command(["speed", "cspeed"]))
async def change_speed(_: Client, msg: types.Message) -> None:
    """Adjust the playback speed of the current track."""
    chat_id = msg.chat_id
    if chat_id > 0:
        return

    if not await is_admin(chat_id, msg.from_id):
        await msg.reply_text("⛔ Administrator privileges required.")
        return

    args = extract_number(msg.text)
    if args is None:
        await msg.reply_text(
            "ℹ️ <b>Usage:</b> <code>/speed [value]</code>\n"
            "Example: <code>/speed 1.5</code> for 1.5x speed\n"
            "Range: 0.5x to 4.0x"
        )
        return

    if not chat_cache.is_active(chat_id):
        await msg.reply_text("⏸ No track is currently playing.")
        return

    speed = round(float(args), 2)
    if speed < 0.5 or speed > 4.0:
        user_lang = await language_manager.get_language(msg.from_id, msg.chat_id)
        await msg.reply_text(language_manager.get_text("speed_range_error", user_lang))
        return

    _change_speed = await call.speed_change(chat_id, speed)
    if isinstance(_change_speed, types.Error):
        user_lang = await language_manager.get_language(msg.from_id, msg.chat_id)
        await msg.reply_text(language_manager.get_text("speed_error", user_lang, error=_change_speed.message))
        return

    await msg.reply_text(
        f"🎚️ Playback speed set to <b>{speed}x</b> by {await msg.mention()}"
    )

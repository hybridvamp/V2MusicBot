#  Copyright (c) 2025 AshokShau
#  Licensed under the GNU AGPL v3.0: https://www.gnu.org/licenses/agpl-3.0.html
#  Part of the TgMusicBot project. All rights reserved where applicable.
#  Modified by Devin - Major modifications and improvements

from pytdbot import Client, types

from TgMusic.core import Filter, language_manager, call
from .funcs import is_admin_or_reply
from .utils.play_helpers import extract_argument


@Client.on_message(filters=Filter.command(["volume", "cvolume"]))
async def volume(c: Client, msg: types.Message) -> None:
    """Adjust the playback volume (1-200%)."""
    chat_id = await is_admin_or_reply(msg)
    if isinstance(chat_id, types.Error):
        user_lang = await language_manager.get_language(msg.from_id, msg.chat_id)
        c.logger.warning(language_manager.get_text("func_admin_check_failed", user_lang, error=chat_id.message))
        return None

    if isinstance(chat_id, types.Message):
        return None

    args = extract_argument(msg.text, enforce_digit=True)
    if not args:
        await msg.reply_text(
            "🔊 <b>Volume Control</b>\n\n"
            "Usage: <code>/volume [1-200]</code>\n"
            "Example: <code>/volume 80</code> for 80% volume\n"
            "Use <code>/volume 0</code> to mute"
        )
        return None

    try:
        vol_int = int(args)
    except ValueError:
        user_lang = await language_manager.get_language(msg.from_id, msg.chat_id)
        await msg.reply_text(language_manager.get_text("volume_invalid_number", user_lang))
        return None

    if vol_int == 0:
        await msg.reply_text(f"🔇 Playback muted by {await msg.mention()}")
        return None

    if not 1 <= vol_int <= 200:
        user_lang = await language_manager.get_language(msg.from_id, msg.chat_id)
        await msg.reply_text(language_manager.get_text("volume_range_error", user_lang))
        return None

    done = await call.change_volume(chat_id, vol_int)
    if isinstance(done, types.Error):
        user_lang = await language_manager.get_language(msg.from_id, msg.chat_id)
        await msg.reply_text(language_manager.get_text("volume_error", user_lang, error=done.message))
        return None

    await msg.reply_text(f"🔊 Volume set to <b>{vol_int}%</b> by {await msg.mention()}")
    return None

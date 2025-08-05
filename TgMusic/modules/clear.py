#  Copyright (c) 2025 AshokShau
#  Licensed under the GNU AGPL v3.0: https://www.gnu.org/licenses/agpl-3.0.html
#  Part of the TgMusicBot project. All rights reserved where applicable.
#  Modified by Devin - Major modifications and improvements

from pytdbot import Client, types

from TgMusic.core import Filter, language_manager, chat_cache
from TgMusic.core.admins import is_admin
from .utils.play_helpers import reply_auto_delete_message


@Client.on_message(filters=Filter.command("clear"))
async def clear_queue(c: Client, msg: types.Message) -> None:
    """Clear the current playback queue."""
    chat_id = msg.chat_id

    if chat_id > 0:
        return None

    if not await is_admin(chat_id, msg.from_id):
        await reply_auto_delete_message(c, msg, "⛔ Administrator privileges required.", delay=10)
        return None

    if not chat_cache.is_active(chat_id):
        await reply_auto_delete_message(c, msg, "ℹ️ No active playback session found.", delay=10)
        return None

    if not chat_cache.get_queue(chat_id):
        await reply_auto_delete_message(c, msg, "ℹ️ The queue is already empty.", delay=10)
        return None

    chat_cache.clear_chat(chat_id)
    user_lang = await language_manager.get_language(msg.from_id, msg.chat_id)
    reply = await reply_auto_delete_message(
        c, msg, 
        language_manager.get_text("clear_success", user_lang, user=await msg.mention()),
        delay=10
    )
    if isinstance(reply, types.Error):
        c.logger.warning(f"Error sending reply: {reply}")
    return None

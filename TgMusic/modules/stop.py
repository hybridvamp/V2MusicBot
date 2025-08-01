#  Copyright (c) 2025 AshokShau
#  Licensed under the GNU AGPL v3.0: https://www.gnu.org/licenses/agpl-3.0.html
#  Part of the TgMusicBot project. All rights reserved where applicable.
#  Modified by Devin - Major modifications and improvements

from pytdbot import Client, types

from TgMusic.core import Filter, call, language_manager
from .funcs import is_admin_or_reply


@Client.on_message(filters=Filter.command(["stop", "end"]))
async def stop_song(c: Client, msg: types.Message) -> None:
    """Stop the current playback and clear the queue."""
    chat_id = await is_admin_or_reply(msg)
    if isinstance(chat_id, types.Error):
        user_lang = await language_manager.get_language(msg.from_id, msg.chat_id)
        c.logger.warning(language_manager.get_text("stop_admin_check_error", user_lang, error=chat_id.message))
        return None

    if isinstance(chat_id, types.Message):
        return None

    _end = await call.end(chat_id)
    if isinstance(_end, types.Error):
        user_lang = await language_manager.get_language(msg.from_id, msg.chat_id)
        await msg.reply_text(language_manager.get_text("stop_error", user_lang, error=_end.message))
        return None

    user_lang = await language_manager.get_language(msg.from_id, msg.chat_id)
    await msg.reply_text(
        language_manager.get_text("stop_success", user_lang, user=await msg.mention())
    )
    return None

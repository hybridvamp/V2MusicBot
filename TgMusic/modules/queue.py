#  Copyright (c) 2025 AshokShau
#  Licensed under the GNU AGPL v3.0: https://www.gnu.org/licenses/agpl-3.0.html
#  Part of the TgMusicBot project. All rights reserved where applicable.
#  Modified by Devin - Major modifications and improvements

from pytdbot import Client, types

from TgMusic.core import Filter, language_manager, chat_cache, call
from TgMusic.modules.utils import sec_to_min


@Client.on_message(filters=Filter.command("queue"))
async def queue_info(_: Client, msg: types.Message) -> None:
    """Display the current playback queue with detailed information."""
    if msg.chat_id > 0:
        return

    chat_id = msg.chat_id
    _queue = chat_cache.get_queue(chat_id)

    if not _queue:
        await msg.reply_text("📭 The queue is currently empty.")
        return

    if not chat_cache.is_active(chat_id):
        await msg.reply_text("⏸ No active playback session.")
        return

    chat = await msg.getChat()
    if isinstance(chat, types.Error):
        user_lang = await language_manager.get_language(msg.from_id, msg.chat_id)
        await msg.reply_text(
            language_manager.get_text("queue_chat_error", user_lang, error=chat.message)
        )
        return

    current_song = _queue[0]
    text = [
        f"<b>🎧 Queue for {chat.title}</b>",
        "",
        "╭─────────────⭓",
        "🎶 <b>Now Playing </b>",
        f"┣▹ 🎼 Title: `{current_song.name[:45]}`",
        "",
        f"┣▹ 🕒 <b>Duration:</b> {sec_to_min(current_song.duration)}",
        f"┣▹ 🔁 <b>Loop:</b> {'On' if current_song.loop else 'Off'}",
        f"┣▹ ⏱ <b>Progress:</b> {sec_to_min(await call.played_time(chat.id))}",
        f"╰▹ 🙋 <b>Requested by:</b> {current_song.user}",
    ]

    if len(_queue) > 1:
        text.extend(["", f"<b>⏭ Next Up ({len(_queue) - 1}):</b>"])
        text.extend(
            f"{i}. <code>{song.name[:45]}</code> | {sec_to_min(song.duration)} min"
            for i, song in enumerate(_queue[1:11], 1)
        )
        if len(_queue) > 11:
            text.append(f"...and {len(_queue) - 11} more")

    text.append(f"\n<b>📊 Total:</b> {len(_queue)} track(s) in queue")

    # Handle message length limit
    formatted_text = "\n".join(text)
    if len(formatted_text) > 4096:
        formatted_text = "\n".join(
            [
                f"<b>🎧 Queue for {chat.title}</b>",
                "",
                "╭─────────────⭓",
                "🎶 <b>Now Playing </b>",
                f"┣▹ 🎼 Title: `{current_song.name[:45]}`",
                f"┣▹ ⏱ <b>Progress:</b> {sec_to_min(await call.played_time(chat.id))}/{sec_to_min(current_song.duration)}",
                f"╰▹ 🙋 <b>Requested by:</b> {current_song.user}",
                "",
                f"<b>📊 Total:</b> {len(_queue)} track(s) in queue",
            ]
        )

    await msg.reply_text(text=formatted_text, disable_web_page_preview=True)

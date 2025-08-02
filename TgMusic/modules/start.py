#  Copyright (c) 2025 AshokShau
#  Licensed under the GNU AGPL v3.0: https://www.gnu.org/licenses/agpl-3.0.html
#  Part of the TgMusicBot project. All rights reserved where applicable.
#  Modified by Devin - Major modifications and improvements

from pytdbot import Client, types

from TgMusic import __version__
from TgMusic.core import (
    config,
    Filter,
    SupportButton,
    language_manager,
    db,
    chat_cache,
)
from TgMusic.core.buttons import add_me_markup, HelpMenu, BackHelpMenu

startText = """
ʜᴇʏ {};

◎ ᴛʜɪꜱ ɪꜱ {}!
➻ ᴀ ꜰᴀꜱᴛ & ᴘᴏᴡᴇʀꜰᴜʟ ᴛᴇʟᴇɢʀᴀᴍ ᴍᴜꜱɪᴄ ᴘʟᴀʏᴇʀ ʙᴏᴛ ᴡɪᴛʜ ꜱᴏᴍᴇ ᴀᴡᴇꜱᴏᴍᴇ ꜰᴇᴀᴛᴜʀᴇꜱ.

ꜱᴜᴘᴘᴏʀᴛᴇᴅ ᴘʟᴀᴛꜰᴏʀᴍꜱ: ʏᴏᴜᴛᴜʙᴇ, ꜱᴘᴏᴛɪꜰʏ, ᴊɪᴏꜱᴀᴀᴠɴ, ᴀᴘᴘʟᴇ ᴍᴜꜱɪᴄ ᴀɴᴅ ꜱᴏᴜɴᴅᴄʟᴏᴜᴅ.

---
◎ ᴄʟɪᴄᴋ ᴏɴ ᴛʜᴇ ʜᴇʟᴘ ʙᴜᴛᴛᴏɴ ᴛᴏ ɢᴇᴛ ɪɴꜰᴏʀᴍᴀᴛɪᴏɴ ᴀʙᴏᴜᴛ ᴍʏ ᴍᴏᴅᴜʟᴇꜱ ᴀɴᴅ ᴄᴏᴍᴍᴀɴᴅꜱ.
"""

@Client.on_message(filters=Filter.command(["start", "help"]))
async def start_cmd(c: Client, message: types.Message):
    chat_id = message.chat_id
    bot_name = c.me.first_name
    mention = await message.mention()

    if chat_id < 0:  # Group
        # Track activity for group chats
        await db.update_chat_activity(chat_id)
        chat_cache.update_activity(chat_id)
        
        welcome_text = (
            f"🎵 <b>Hello {mention}!</b>\n\n"
            f"<b>{bot_name}</b> is now active in this group.\n"
            "Here's what I can do:\n"
            "• High-quality music streaming\n"
            "• Supports YouTube, Spotify, and more\n"
            "• Powerful controls for seamless playback\n\n"
            f"💬 <a href='{config.SUPPORT_GROUP}'>Need help? Join our Support Chat</a>"
        )
        reply = await message.reply_text(
            text=welcome_text,
            disable_web_page_preview=True,
            reply_markup=SupportButton,
        )

    else:  # Private chat
        bot_username = c.me.usernames.editable_username
        reply = await message.reply_photo(
            photo=config.START_IMG,
            caption=startText.format(mention, bot_name),
            reply_markup=add_me_markup(bot_username),
        )

    if isinstance(reply, types.Error):
        c.logger.warning(reply.message)


@Client.on_updateNewCallbackQuery(filters=Filter.regex(r"help_\w+"))
async def callback_query_help(c: Client, message: types.UpdateNewCallbackQuery) -> None:
    data = message.payload.data.decode()

    # Get user ID from the message (needed for all cases)
    get_msg = await message.getMessage()
    if isinstance(get_msg, types.Error):
        c.logger.warning(f"Failed to get message: {get_msg.message}")
        return None
    if isinstance(get_msg.sender_id, types.MessageSenderUser):
        user_id = get_msg.sender_id.user_id
    else:
        c.logger.warning("Invalid sender type for callback query")
        return None

    if data == "help_all":
        user = await c.getUser(user_id)
        chat_id = message.chat_id
        user_lang = await language_manager.get_language(user_id, chat_id)
        
        await message.answer(language_manager.get_text("help_button", user_lang))
        welcome_text = language_manager.get_text(
            "start_welcome", 
            user_lang, 
            user_name=user.first_name, 
            bot_name=c.me.first_name, 
            version=__version__
        )
        edit = await message.edit_message_caption(welcome_text, reply_markup=HelpMenu)
        if isinstance(edit, types.Error):
            if edit.message == "MESSAGE_NOT_MODIFIED":
                # This is not a real error - the message content is the same
                c.logger.debug("Message not modified (content unchanged)")
            else:
                c.logger.error(f"Failed to edit message: {edit}")
        return

    if data == "help_back":
        await message.answer("HOME ..")
        user = await c.getUser(user_id)
        await message.edit_message_caption(
            caption=startText.format(user.first_name, c.me.first_name),
            reply_markup=add_me_markup(c.me.usernames.editable_username),
        )
        return

    # Get user language for help categories
    chat_id = message.chat_id
    user_lang = await language_manager.get_language(user_id, chat_id)
    
    help_categories = {
        "help_user": {
            "title": language_manager.get_text("help_user_title", user_lang),
            "content": language_manager.get_text("help_user_content", user_lang),
            "markup": BackHelpMenu,
        },
        "help_admin": {
            "title": language_manager.get_text("help_admin_title", user_lang),
            "content": language_manager.get_text("help_admin_content", user_lang),
            "markup": BackHelpMenu,
        },
        "help_owner": {
            "title": language_manager.get_text("help_owner_title", user_lang),
            "content": language_manager.get_text("help_owner_content", user_lang),
            "markup": BackHelpMenu,
        },
        "help_devs": {
            "title": language_manager.get_text("help_devs_title", user_lang),
            "content": language_manager.get_text("help_devs_content", user_lang),
            "markup": BackHelpMenu,
        },
    }

    if category := help_categories.get(data):
        await message.answer(f"📖 {category['title']}")
        formatted_text = (
            f"<b>{category['title']}</b>\n\n"
            f"{category['content']}\n\n"
            "🔙 <i>Use the buttons below to go back.</i>"
        )
        edit = await message.edit_message_caption(formatted_text, reply_markup=category["markup"])
        if isinstance(edit, types.Error):
            if edit.message == "MESSAGE_NOT_MODIFIED":
                # This is not a real error - the message content is the same
                c.logger.debug("Message not modified (content unchanged)")
            else:
                c.logger.error(f"Failed to edit message: {edit}")
        return

    await message.answer("⚠️ Unknown command category.")

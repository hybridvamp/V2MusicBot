#  Copyright (c) 2025 AshokShau
#  Licensed under the GNU AGPL v3.0: https://www.gnu.org/licenses/agpl-3.0.html
#  Part of the TgMusicBot project. All rights reserved where applicable.
#  Modified by Devin - Major modifications and improvements

from pytdbot import Client, types
from TgMusic.core import Filter, language_manager
from TgMusic.core._database import db


@Client.on_message(filters=Filter.command("language"))
async def language_cmd(c: Client, message: types.Message) -> None:
    """Handle /language command to change bot language."""
    user_id = message.from_id
    chat_id = message.chat_id
    
    # Get current language (prioritize chat language for groups)
    current_lang = await language_manager.get_language(user_id, chat_id)
    current_lang_name = language_manager.get_supported_languages()[current_lang]
    
    # Create language selection keyboard
    keyboard = []
    supported_langs = language_manager.get_supported_languages()
    
    for lang_code, lang_name in supported_langs.items():
        # Add checkmark for current language
        prefix = "✅ " if lang_code == current_lang else "🌐 "
        keyboard.append([{
            "text": f"{prefix}{lang_name}",
            "callback_data": f"lang_{lang_code}"
        }])
    
    # Add back button
    keyboard.append([{
        "text": language_manager.get_text("back_button", language=current_lang),
        "callback_data": "lang_back"
    }])
    
    reply_markup = types.ReplyMarkupInlineKeyboard(keyboard)
    
    # Send language selection message
    title = language_manager.get_text("language_title", language=current_lang)
    current_text = language_manager.get_text("language_current", language=current_lang, lang_name=current_lang_name)
    select_text = language_manager.get_text("language_select", language=current_lang)
    
    text = f"{title}\n\n{current_text}\n\n{select_text}"
    
    await message.reply_text(text, reply_markup=reply_markup)


@Client.on_updateNewCallbackQuery(filters=Filter.regex(r"lang_\w+"))
async def language_callback(c: Client, message: types.UpdateNewCallbackQuery) -> None:
    """Handle language selection callback queries."""
    data = message.payload.data.decode()
    user_id = message.sender_user_id
    chat_id = message.chat_id
    
    if data == "lang_back":
        # Go back to start menu
        await message.answer(language_manager.get_text("back_button", language=await language_manager.get_language(user_id, chat_id)))
        # Get user info for proper welcome message
        user = await c.getUser(user_id)
        welcome_text = language_manager.get_text("start_welcome", language=await language_manager.get_language(user_id, chat_id), 
                                               user_name=user.first_name, bot_name=c.me.first_name, version="1.0")
        await message.edit_message_caption(welcome_text, reply_markup=None)
        return
    
    # Extract language code
    lang_code = data.replace("lang_", "")
    
    if not language_manager.is_supported_language(lang_code):
        await message.answer(language_manager.get_text("error_invalid_request", language=await language_manager.get_language(user_id, chat_id)))
        return
    
    try:
        # Set language preference (chat language for groups, user language for private)
        success = await language_manager.set_language(user_id, lang_code, chat_id)
        
        if success:
            lang_name = language_manager.get_supported_languages()[lang_code]
            success_msg = language_manager.get_text("language_changed", language=lang_code, lang_name=lang_name)
            await message.answer(success_msg, show_alert=True)
            
            # Update the language selection message
            keyboard = []
            supported_langs = language_manager.get_supported_languages()
            
            for code, name in supported_langs.items():
                prefix = "✅ " if code == lang_code else "🌐 "
                keyboard.append([{
                    "text": f"{prefix}{name}",
                    "callback_data": f"lang_{code}"
                }])
            
            keyboard.append([{
                "text": language_manager.get_text("back_button", language=lang_code),
                "callback_data": "lang_back"
            }])
            
            reply_markup = types.ReplyMarkupInlineKeyboard(keyboard)
            
            title = language_manager.get_text("language_title", language=lang_code)
            current_text = language_manager.get_text("language_current", language=lang_code, lang_name=lang_name)
            select_text = language_manager.get_text("language_select", language=lang_code)
            
            text = f"{title}\n\n{current_text}\n\n{select_text}"
            
            await message.edit_message_caption(text, reply_markup=reply_markup)
            
        else:
            error_msg = language_manager.get_text("language_error", language=await language_manager.get_language(user_id, chat_id))
            await message.answer(error_msg, show_alert=True)
            
    except Exception as e:
        c.logger.error(f"Error changing language for user {user_id}: {e}")
        error_msg = language_manager.get_text("language_error", language=await language_manager.get_language(user_id, chat_id))
        await message.answer(error_msg, show_alert=True) 
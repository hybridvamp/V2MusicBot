#  Copyright (c) 2025 AshokShau
#  Licensed under the GNU AGPL v3.0: https://www.gnu.org/licenses/agpl-3.0.html
#  Part of the TgMusicBot project. All rights reserved where applicable.

import asyncio
from typing import Any, Union, TYPE_CHECKING

from pytdbot import types

from TgMusic.logger import LOGGER

if TYPE_CHECKING:
    from pytdbot import Client


async def get_url(
    msg: types.Message, reply: Union[types.Message, None]
) -> Union[str, None]:
    """
    Extracts a URL from the given message or its reply.

    Args:
    msg: The message object to extract the URL from.
    reply: The reply message objects to extract the URL from, if any.

    Returns:
    The extracted URL string, or `None` if no URL was found.
    """
    if reply:
        text_content = reply.text or ""
        entities = reply.entities or []
    else:
        text_content = msg.text or ""
        entities = msg.entities or []

    for entity in entities:
        if entity.type and entity.type["@type"] == "textEntityTypeUrl":
            offset = entity.offset
            length = entity.length
            return text_content[offset : offset + length]
    return None


def extract_argument(text: str, enforce_digit: bool = False) -> Union[str, None]:
    """
    Extracts the argument from the command text.

    Args:
        text (str): The full command text.
        enforce_digit (bool): Whether to enforce that the argument is a digit.

    Returns:
        str | None: The extracted argument or None if invalid.
    """
    args = text.strip().split(maxsplit=1)

    if len(args) < 2:
        return None

    argument = args[1].strip()
    return None if enforce_digit and not argument.isdigit() else argument


async def del_msg(msg: types.Message) -> None:
    """
    Deletes the given message.

    Args:
        msg (types.Message): The message to delete.

    Returns:
        None
    """
    delete = await msg.delete()
    if isinstance(delete, types.Error):
        if delete.code == 400:
            return
        LOGGER.warning("Error deleting message: %s", delete)
    return


async def edit_text(
    reply_message: types.Message, *args: Any, **kwargs: Any
) -> Union["types.Error", "types.Message"]:
    """
    Edits the given message and returns the result.

    If the given message is an Error, logs the error and returns it.
    If an exception occurs while editing the message, logs the exception and
    returns the original message.

    Args:
        reply_message (types.Message): The message to edit.
        *args: Passed to `Message.edit_text`.
        **kwargs: Passed to `Message.edit_text`.

    Returns:
        Union["types.Error", "types.Message"]: The edited message, or the
        original message if an exception occurred.
    """
    if isinstance(reply_message, types.Error):
        LOGGER.warning("Error getting message: %s", reply_message)
        return reply_message

    reply = await reply_message.edit_text(*args, **kwargs)
    if isinstance(reply, types.Error):
        if reply.code == 429:
            retry_after = (
                int(reply.message.split("retry after ")[1])
                if "retry after" in reply.message
                else 2
            )
            LOGGER.warning("Rate limited, retrying in %s seconds", retry_after)
            if retry_after > 20:
                return reply

            await asyncio.sleep(retry_after)
            return await edit_text(reply_message, *args, **kwargs)
        LOGGER.warning("Error editing message: %s", reply)
    return reply


async def auto_delete_message(msg: types.Message, delay: int = 10) -> None:
    """
    Automatically deletes a message after a specified delay.
    
    Args:
        msg (types.Message): The message to delete.
        delay (int): Delay in seconds before deletion (default: 10).
    """
    try:
        await asyncio.sleep(delay)
        await del_msg(msg)
    except Exception as e:
        LOGGER.warning("Error in auto_delete_message: %s", e)


async def send_auto_delete_message(
    client: "Client", 
    chat_id: int, 
    text: str, 
    delay: int = 10,
    **kwargs
) -> Union[types.Message, types.Error]:
    """
    Sends a message that will be automatically deleted after a specified delay.
    
    Args:
        client: The Telegram client.
        chat_id (int): The chat ID to send the message to.
        text (str): The message text.
        delay (int): Delay in seconds before deletion (default: 10).
        **kwargs: Additional arguments for sendTextMessage.
    
    Returns:
        Union[types.Message, types.Error]: The sent message or error.
    """
    try:
        msg = await client.sendTextMessage(
            chat_id=chat_id,
            text=text,
            **kwargs
        )
        
        if not isinstance(msg, types.Error):
            # Start auto-delete task
            asyncio.create_task(auto_delete_message(msg, delay))
        
        return msg
    except Exception as e:
        LOGGER.error("Error sending auto-delete message: %s", e)
        return types.Error(code=500, message=str(e))


async def reply_auto_delete_message(
    client: "Client", 
    message: types.Message, 
    text: str, 
    delay: int = 10,
    **kwargs
) -> Union[types.Message, types.Error]:
    """
    Replies to a message with auto-delete functionality.
    
    Args:
        client: The Telegram client.
        message (types.Message): The message to reply to.
        text (str): The reply text.
        delay (int): Delay in seconds before deletion (default: 10).
        **kwargs: Additional arguments for replyTextMessage.
    
    Returns:
        Union[types.Message, types.Error]: The sent message or error.
    """
    try:
        msg = await client.replyTextMessage(
            chat_id=message.chat_id,
            message_id=message.id,
            text=text,
            **kwargs
        )
        
        if not isinstance(msg, types.Error):
            # Start auto-delete task
            asyncio.create_task(auto_delete_message(msg, delay))
        
        return msg
    except Exception as e:
        LOGGER.error("Error sending auto-delete reply: %s", e)
        return types.Error(code=500, message=str(e))

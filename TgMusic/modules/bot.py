import time
from datetime import datetime

from cachetools import TTLCache
from pytdbot import Client, types

from TgMusic import StartTime
from TgMusic.core import (
    chat_invite_cache,
    user_status_cache,
    chat_cache,
    call,
    Filter,
    config,
    db,
    language_manager,
)
from TgMusic.core.admins import load_admin_cache
from TgMusic.modules.utils import sec_to_min
from TgMusic.modules.utils.play_helpers import (
    extract_argument,
)


@Client.on_message(filters=Filter.command("privacy"))
async def privacy_handler(c: Client, message: types.Message):
    """
    Handle the /privacy command to display privacy policy.
    """
    user_id = message.from_id
    chat_id = message.chat_id
    user_lang = await language_manager.get_language(user_id, chat_id)
    
    privacy_title = language_manager.get_text("privacy_title", user_lang)
    privacy_content = language_manager.get_text("privacy_content", user_lang)
    
    text = f"{privacy_title}\n\n{privacy_content}"

    reply = await message.reply_text(text)
    if isinstance(reply, types.Error):
        c.logger.warning(f"Error sending privacy policy message:{reply.message}")
    return


rate_limit_cache = TTLCache(maxsize=100, ttl=180)


@Client.on_message(filters=Filter.command(["reload"]))
async def reload_cmd(c: Client, message: types.Message) -> None:
    """Handle the /reload command to reload the bot."""
    user_id = message.from_id
    chat_id = message.chat_id
    user_lang = await language_manager.get_language(user_id, chat_id)
    
    if chat_id > 0:
        reply = await message.reply_text(
            language_manager.get_text("error_admin_required", user_lang)
        )
        if isinstance(reply, types.Error):
            c.logger.warning(f"Error sending message: {reply} for chat {chat_id}")
        return None

    if user_id in rate_limit_cache:
        last_used_time = rate_limit_cache[user_id]
        time_remaining = 180 - (datetime.now() - last_used_time).total_seconds()
        reply = await message.reply_text(
            language_manager.get_text("error_generic", user_lang) + f" ({sec_to_min(time_remaining)} Min)"
        )
        if isinstance(reply, types.Error):
            c.logger.warning(f"Error sending message: {reply} for chat {chat_id}")
        return None

    rate_limit_cache[user_id] = datetime.now()
    reply = await message.reply_text(language_manager.get_text("system_starting", user_lang))
    if isinstance(reply, types.Error):
        c.logger.warning(f"Error sending message: {reply} for chat {chat_id}")
        return None

    ub = await call.get_client(chat_id)
    if isinstance(ub, types.Error):
        await reply.edit_text(ub.message)
        return None

    await chat_invite_cache.delete(chat_id)
    user_key = f"{chat_id}:{ub.me.id}"
    await user_status_cache.delete(user_key)

    if not chat_cache.is_active(chat_id):
        chat_cache.clear_chat(chat_id)

    load_admins, _ = await load_admin_cache(c, chat_id, True)
    ub_stats = await call.check_user_status(chat_id)
    if isinstance(ub_stats, types.Error):
        ub_stats = ub_stats.message

    loaded = "✅" if load_admins else "❌"
    text = (
        f"<b>Assistant Status:</b> {ub_stats.getType()}\n"
        f"<b>Admins Loaded:</b> {loaded}\n"
        f"<b>» Reloaded by:</b> {await message.mention()}"
    )

    reply = await reply.edit_text(text)
    if isinstance(reply, types.Error):
        c.logger.warning(f"Error sending message: {reply} for chat {chat_id}")
    return None


@Client.on_message(filters=Filter.command("ping"))
async def ping_cmd(client: Client, message: types.Message) -> None:
    """
    Handle the /ping command to check bot performance metrics.
    """
    response = await call.stats_call(message.chat_id if message.chat_id < 0 else 1)
    if isinstance(response, types.Error):
        call_ping = response.message
        cpu_usage = "Unavailable"
    else:
        call_ping, cpu_usage = response
    call_ping_info = f"{call_ping:.2f} ms"
    cpu_info = f"{cpu_usage:.2f}%"
    uptime = datetime.now() - StartTime
    uptime_str = str(uptime).split(".")[0]
    user_lang = await language_manager.get_language(message.from_id, message.chat_id)
    start_time = time.monotonic()
    reply_msg = await message.reply_text(language_manager.get_text("btn_play", user_lang) + "...")
    latency = (time.monotonic() - start_time) * 1000  # ms
    response = (
        "📊 <b>System Performance Metrics</b>\n\n"
        f"⏱️ <b>Bot Latency:</b> <code>{latency:.2f} ms</code>\n"
        f"🕒 <b>Uptime:</b> <code>{uptime_str}</code>\n"
        f"🧠 <b>CPU Usage:</b> <code>{cpu_info}</code>\n"
        f"📞 <b>NTgCalls Ping:</b> <code>{call_ping_info}</code>\n"
    )
    done = await reply_msg.edit_text(response, disable_web_page_preview=True)
    if isinstance(done, types.Error):
        client.logger.warning(f"Error sending message: {done}")
    return None


@Client.on_message(filters=Filter.command("performance"))
async def performance_cmd(client: Client, message: types.Message) -> None:
    """
    Handle the /performance command to show comprehensive system performance.
    """
    if message.from_id not in config.DEVS:
        return
    
    user_lang = await language_manager.get_language(message.from_id, message.chat_id)
    reply_msg = await message.reply_text(language_manager.get_text("performance_title", user_lang))
    
    try:
        # Database statistics
        db_stats = await db.get_database_stats()
        
        # Cache statistics
        cache_stats = chat_cache.get_cache_stats()
        
        # API statistics (if available)
        from TgMusic.core._api import OptimizedApiData
        try:
            api_instance = OptimizedApiData()
            api_stats = await api_instance.get_api_stats()
        except Exception:
            api_stats = {"error": "API stats unavailable"}
        
        # System info
        import psutil
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Uptime
        uptime = datetime.now() - StartTime
        uptime_str = str(uptime).split(".")[0]
        
        # Get call ping info
        try:
            call_ping = await call.ping()
            call_ping_info = f"{call_ping:.2f} ms" if isinstance(call_ping, (int, float)) else "N/A"
        except Exception:
            call_ping_info = "N/A"
        
        response = f"""
🔥 <b>TgMusicBot Performance Dashboard</b>

⏱️ <b>System Info:</b>
• Uptime: <code>{uptime_str}</code>
• CPU Usage: <code>{cpu_percent:.1f}%</code>
• Memory: <code>{memory.percent:.1f}%</code> (<code>{memory.used // (1024**3):.1f}GB / {memory.total // (1024**3):.1f}GB</code>)
• Disk: <code>{disk.percent:.1f}%</code> (<code>{disk.used // (1024**3):.1f}GB / {disk.total // (1024**3):.1f}GB</code>)

💾 <b>Database Performance:</b>
• Connection: <code>{'✅ Healthy' if db_stats.get('connection_healthy') else '❌ Issues'}</code>
• Cache Hit Rate: <code>{db_stats.get('cache_hit_rate', 'N/A')}</code>
• Total Queries: <code>{db_stats.get('total_queries', 0)}</code>
• Avg Query Time: <code>{db_stats.get('avg_query_time', 'N/A')}</code>

🎵 <b>Music Cache:</b>
• Total Chats: <code>{cache_stats.get('total_chats', 0)}</code>
• Active Chats: <code>{cache_stats.get('active_chats', 0)}</code>
• Cache Hit Rate: <code>{cache_stats.get('hit_rate', 'N/A')}</code>
• Avg Queue Length: <code>{cache_stats.get('average_queue_length', 0):.1f}</code>

🌐 <b>API Performance:</b>
• Requests Made: <code>{api_stats.get('requests_made', 0)}</code>
• Cache Hit Rate: <code>{api_stats.get('cache_hit_rate', 'N/A')}</code>
• Avg Response Time: <code>{api_stats.get('avg_response_time', 'N/A')}</code>
• Errors: <code>{api_stats.get('errors', 0)}</code>

📊 <b>Call Stats:</b>
• Call Ping: <code>{call_ping_info}</code>
• Active VCs: <code>{len(chat_cache.get_active_chats())}</code>
"""
        
        done = await reply_msg.edit_text(response, disable_web_page_preview=True)
        if isinstance(done, types.Error):
            client.logger.warning(f"Error sending performance stats: {done}")
            
    except Exception as e:
        error_msg = f"❌ Error gathering performance metrics: {str(e)}"
        await reply_msg.edit_text(error_msg)
        client.logger.error("Performance command error: %s", e)

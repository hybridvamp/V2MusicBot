# Copyright (c) 2025 Devin
# Licensed under the GNU AGPL v3.0: https://www.gnu.org/licenses/agpl-3.0.html
# Part of the TgMusicBotFork project. All rights reserved where applicable.

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Any

from pytdbot import Client, types

from TgMusic.core import Filter, language_manager, db, call
from TgMusic.core.error_handler import error_handler
from TgMusic.core.metrics import metrics_manager
from TgMusic.logger import LOGGER
from .utils.play_helpers import reply_auto_delete_message


@Client.on_message(filters=Filter.command("health"))
async def health_check(c: Client, msg: types.Message) -> None:
    """Comprehensive health check for the bot."""
    if msg.chat_id > 0:
        return

    user_lang = await language_manager.get_language(msg.from_id, msg.chat_id)
    
    # Check if user is authorized
    from TgMusic.core.admins import is_admin
    if not await is_admin(msg.chat_id, msg.from_id):
        await reply_auto_delete_message(
            c, msg,
            language_manager.get_text("not_authorized", user_lang),
            delay=10
        )
        return

    try:
        # Get comprehensive health status
        health_status = await get_health_status()
        
        # Format health report
        report = format_health_report(health_status, user_lang)
        
        await reply_auto_delete_message(
            c, msg,
            text=report,
            delay=30,
            disable_web_page_preview=True
        )
        
    except Exception as e:
        LOGGER.error(f"Error in health check: {e}", exc_info=True)
        await reply_auto_delete_message(
            c, msg,
            "❌ Error generating health report",
            delay=10
        )


async def get_health_status() -> Dict[str, Any]:
    """Get comprehensive health status of the bot."""
    status = {
        "timestamp": datetime.now(),
        "bot": {},
        "system": {},
        "database": {},
        "voice_calls": {},
        "errors": {},
        "performance": {}
    }
    
    try:
        # Bot metrics
        bot_stats = metrics_manager.bot_metrics.get_stats()
        status["bot"] = {
            "uptime": bot_stats["uptime_formatted"],
            "total_commands": bot_stats["total_commands"],
            "total_errors": bot_stats["total_errors"],
            "active_chats": bot_stats["active_chats"],
            "success_rates": bot_stats["success_rates"],
            "avg_response_times": bot_stats["avg_response_times"]
        }
        
        # System metrics
        system_stats = metrics_manager.system_metrics.get_current_stats()
        status["system"] = {
            "cpu_percent": system_stats.get("cpu_percent", 0),
            "memory_percent": system_stats.get("memory_percent", 0),
            "disk_percent": system_stats.get("disk_percent", 0),
            "memory_available": system_stats.get("memory_available", 0),
            "disk_free": system_stats.get("disk_free", 0)
        }
        
        # Database health
        try:
            await db.ping()
            db_stats = await db.get_database_stats()
            status["database"] = {
                "status": "healthy",
                "connection": "active",
                "stats": db_stats
            }
        except Exception as e:
            status["database"] = {
                "status": "unhealthy",
                "connection": "failed",
                "error": str(e)
            }
        
        # Voice calls status
        try:
            active_calls = call.get_active_calls()
            status["voice_calls"] = {
                "active_calls": len(active_calls),
                "call_details": active_calls
            }
        except Exception as e:
            status["voice_calls"] = {
                "status": "error",
                "error": str(e)
            }
        
        # Error statistics
        error_stats = error_handler.get_error_stats()
        status["errors"] = error_stats
        
        # Performance metrics
        health_status = metrics_manager.get_health_status()
        status["performance"] = {
            "overall_health": health_status["healthy"],
            "health_checks": health_status["checks"],
            "issues": health_status["issues"]
        }
        
    except Exception as e:
        LOGGER.error(f"Error getting health status: {e}", exc_info=True)
        status["error"] = str(e)
    
    return status


def format_health_report(status: Dict[str, Any], user_lang: str) -> str:
    """Format health status into a readable report."""
    lines = ["🏥 <b>Bot Health Report</b>", ""]
    
    # Overall status
    overall_healthy = status.get("performance", {}).get("overall_health", False)
    status_emoji = "✅" if overall_healthy else "❌"
    lines.append(f"{status_emoji} <b>Overall Status:</b> {'Healthy' if overall_healthy else 'Unhealthy'}")
    lines.append("")
    
    # Bot statistics
    bot = status.get("bot", {})
    if bot:
        lines.append("🤖 <b>Bot Statistics:</b>")
        lines.append(f"⏱ <b>Uptime:</b> {bot.get('uptime', 'Unknown')}")
        lines.append(f"📊 <b>Total Commands:</b> {bot.get('total_commands', 0)}")
        lines.append(f"❌ <b>Total Errors:</b> {bot.get('total_errors', 0)}")
        lines.append(f"💬 <b>Active Chats:</b> {bot.get('active_chats', 0)}")
        
        # Success rates
        success_rates = bot.get('success_rates', {})
        if success_rates:
            lines.append("📈 <b>Success Rates:</b>")
            for operation, rate in success_rates.items():
                if rate > 0:
                    lines.append(f"  • {operation}: {rate:.1f}%")
        lines.append("")
    
    # System resources
    system = status.get("system", {})
    if system:
        lines.append("💻 <b>System Resources:</b>")
        cpu = system.get('cpu_percent', 0)
        memory = system.get('memory_percent', 0)
        disk = system.get('disk_percent', 0)
        
        cpu_emoji = "🟢" if cpu < 70 else "🟡" if cpu < 90 else "🔴"
        memory_emoji = "🟢" if memory < 70 else "🟡" if memory < 90 else "🔴"
        disk_emoji = "🟢" if disk < 70 else "🟡" if disk < 90 else "🔴"
        
        lines.append(f"{cpu_emoji} <b>CPU:</b> {cpu:.1f}%")
        lines.append(f"{memory_emoji} <b>Memory:</b> {memory:.1f}%")
        lines.append(f"{disk_emoji} <b>Disk:</b> {disk:.1f}%")
        lines.append("")
    
    # Database status
    db_status = status.get("database", {})
    if db_status:
        lines.append("🗄️ <b>Database:</b>")
        if db_status.get("status") == "healthy":
            lines.append("✅ <b>Status:</b> Healthy")
            db_stats = db_status.get("stats", {})
            if db_stats:
                lines.append(f"📊 <b>Collections:</b> {db_stats.get('collections', 0)}")
                lines.append(f"📝 <b>Total Documents:</b> {db_stats.get('total_documents', 0)}")
        else:
            lines.append("❌ <b>Status:</b> Unhealthy")
            lines.append(f"⚠️ <b>Error:</b> {db_status.get('error', 'Unknown error')}")
        lines.append("")
    
    # Voice calls
    voice_calls = status.get("voice_calls", {})
    if voice_calls:
        lines.append("🎵 <b>Voice Calls:</b>")
        active_calls = voice_calls.get("active_calls", 0)
        lines.append(f"📞 <b>Active Calls:</b> {active_calls}")
        if active_calls > 0:
            call_details = voice_calls.get("call_details", [])
            for i, call_info in enumerate(call_details[:3], 1):
                lines.append(f"  {i}. Chat ID: {call_info.get('chat_id', 'Unknown')}")
        lines.append("")
    
    # Error statistics
    errors = status.get("errors", {})
    if errors:
        lines.append("⚠️ <b>Error Statistics:</b>")
        total_errors = errors.get("total_errors", 0)
        error_types = errors.get("error_types", 0)
        lines.append(f"📊 <b>Total Errors:</b> {total_errors}")
        lines.append(f"🔢 <b>Error Types:</b> {error_types}")
        
        most_frequent = errors.get("most_frequent")
        if most_frequent:
            error_name, count = most_frequent
            lines.append(f"🔥 <b>Most Frequent:</b> {error_name} ({count} times)")
        lines.append("")
    
    # Performance issues
    performance = status.get("performance", {})
    if performance:
        issues = performance.get("issues", [])
        if issues:
            lines.append("🚨 <b>Issues Detected:</b>")
            for issue in issues:
                lines.append(f"• {issue}")
            lines.append("")
    
    # Response times
    avg_times = bot.get('avg_response_times', {})
    if avg_times:
        lines.append("⏱️ <b>Average Response Times:</b>")
        for command, avg_time in avg_times.items():
            if avg_time > 0:
                lines.append(f"  • {command}: {avg_time:.2f}s")
        lines.append("")
    
    # Footer
    lines.append("📅 <b>Report Generated:</b> " + status.get("timestamp", datetime.now()).strftime("%Y-%m-%d %H:%M:%S"))
    
    return "\n".join(lines)


 
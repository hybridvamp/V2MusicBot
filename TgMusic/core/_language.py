#  Copyright (c) 2025 AshokShau
#  Licensed under the GNU AGPL v3.0: https://www.gnu.org/licenses/agpl-3.0.html
#  Part of the TgMusicBot project. All rights reserved where applicable.
#  Modified by Devin - Major modifications and improvements

from typing import Dict, Any
from TgMusic.core._database import db


class LanguageManager:
    """Multi-language support system for TgMusicBot."""
    
    # Available languages
    SUPPORTED_LANGUAGES = {
        "en-US": "English (US)",
        "id-ID": "Bahasa Indonesia"
    }
    
    # Default language
    DEFAULT_LANGUAGE = "en-US"
    
    # Language strings
    TRANSLATIONS = {
        "en-US": {
            # Start and Help
            "start_welcome": "👋 <b>Hello {user_name}!</b>\n\nWelcome to <b>{bot_name}</b> — your ultimate music bot.\n<code>Version: v{version}</code>\n\n💡 <b>What makes me special?</b>\n• YouTube, Spotify, Apple Music, SoundCloud support\n• Advanced queue and playback controls\n• Private and group usage\n\n🔍 <i>Select a help category below to continue.</i>",
            "start_home": "👋 <b>Hello {user_name}!</b>\n\nWelcome to <b>{bot_name}</b> — your ultimate music bot.\n<code>Version: v{version}</code>\n\n🎵 <b>Quick Start:</b>\n• <code>/play [song]</code> — Play music in voice chat\n• <code>/help</code> — Show help menu\n\n🌐 <b>Language:</b> {current_lang}\n\n<i>Use the buttons below to get started!</i>",
            
            # Help Categories
            "help_user_title": "🎧 User Commands",
            "help_user_content": "<b>▶️ Playback:</b>\n• <code>/play [song]</code> — Play audio in VC\n• <code>/vplay [video]</code> — Play video in VC\n<b>🛠 Utilities:</b>\n• <code>/start</code> — Intro message\n• <code>/privacy</code> — Privacy policy\n• <code>/queue</code> — View track queue\n• <code>/language</code> — Change bot language",
            
            "help_admin_title": "⚙️ Admin Commands",
            "help_admin_content": "<b>🎛 Playback Controls:</b>\n• <code>/skip</code> — Skip current track\n• <code>/pause</code> — Pause playback\n• <code>/resume</code> — Resume playback\n• <code>/seek [sec]</code> — Jump to a position\n• <code>/volume [1-200]</code> — Set playback volume\n\n<b>📋 Queue Management:</b>\n• <code>/remove [x]</code> — Remove track number x\n• <code>/clear</code> — Clear the entire queue\n• <code>/loop [0-10]</code> — Repeat queue x times\n\n<b>👑 Permissions:</b>\n• <code>/auth [reply]</code> — Grant admin access\n• <code>/unauth [reply]</code> — Revoke admin access\n• <code>/authlist</code> — View authorized users",
            
            "help_owner_title": "🔐 Owner Commands",
            "help_owner_content": "<b>⚙️ Settings:</b>\n• <code>/buttons</code> — Toggle control buttons\n• <code>/thumb</code> — Toggle thumbnail mode",
            
            "help_devs_title": "🛠 Developer Tools",
            "help_devs_content": "<b>📊 System Tools:</b>\n• <code>/stats</code> — Show usage stats\n• <code>/logger</code> — Toggle log mode\n• <code>/broadcast</code> — Send a message to all\n• <code>/performance</code> — Show performance metrics\n\n<b>🧹 Maintenance:</b>\n• <code>/activevc</code> — Show active voice chats\n• <code>/clearallassistants</code> — Remove all assistants data from DB\n• <code>/autoend</code> — Enable auto-leave when VC is empty",
            
            # Language System
            "language_title": "🌐 Language Settings",
            "language_current": "Current Language: <b>{language}</b>",
            "language_select": "Select your preferred language:",
            "language_changed": "✅ Language changed to <b>{language}</b>",
            "language_error": "❌ Error changing language",
            
            # Common Messages
            "back_button": "🔙 Back",
            "home_button": "🏠 Home",
            "help_button": "❓ Help",
            "language_button": "🌐 Language",
            
            # Error Messages
            "error_generic": "❌ An error occurred",
            "error_permission": "⛔ You don't have permission to use this command",
            "error_admin_required": "⛔ Administrator privileges required for this action",
            "error_invalid_request": "⚠️ Invalid request format",
            "error_not_found": "⚠️ Requested content not found",
            
            # Success Messages
            "success_operation": "✅ Operation completed successfully",
            "success_language_changed": "✅ Language changed successfully",
            
            # Performance Dashboard
            "performance_title": "🔥 <b>TgMusicBot Performance Dashboard</b>",
            "performance_system_info": "⏱️ <b>System Info:</b>",
            "performance_database": "💾 <b>Database Performance:</b>",
            "performance_music_cache": "🎵 <b>Music Cache:</b>",
            "performance_api": "🌐 <b>API Performance:</b>",
            "performance_call_stats": "📊 <b>Call Stats:</b>",
            
            # Button Labels
            "btn_play": "▶️ Play",
            "btn_pause": "⏸️ Pause",
            "btn_resume": "▶️ Resume",
            "btn_skip": "⏭️ Skip",
            "btn_stop": "⏹️ Stop",
            "btn_close": "❌ Close",
            "btn_volume_up": "🔊 Volume +",
            "btn_volume_down": "🔉 Volume -",
            "btn_loop": "🔁 Loop",
            "btn_shuffle": "🔀 Shuffle",
            
            # Queue Messages
            "queue_empty": "📭 Queue is empty",
            "queue_current": "🎵 <b>Now Playing:</b>\n{current_track}\n\n📋 <b>Queue:</b>\n{queue_list}",
            "queue_added": "✅ Added to queue: <b>{track_name}</b>",
            "queue_removed": "✅ Removed from queue: <b>{track_name}</b>",
            "queue_cleared": "🗑️ Queue cleared",
            
            # Playback Messages
            "playback_started": "🎵 Started playing: <b>{track_name}</b>",
            "playback_paused": "⏸️ Playback paused",
            "playback_resumed": "▶️ Playback resumed",
            "playback_skipped": "⏭️ Track skipped",
            "playback_stopped": "⏹️ Playback stopped",
            "playback_volume": "🔊 Volume set to: <b>{volume}%</b>",
            
            # Search Messages
            "search_started": "🔍 Searching for: <b>{query}</b>",
            "search_found": "✅ Found: <b>{track_name}</b>",
            "search_not_found": "❌ No results found for: <b>{query}</b>",
            "search_error": "⚠️ Search error: {error}",
            
            # Admin Messages
            "admin_auth_granted": "✅ User granted authorization permissions",
            "admin_auth_revoked": "✅ User's authorization permissions have been revoked",
            "admin_auth_already": "ℹ️ User already has authorization permissions",
            "admin_auth_not_found": "ℹ️ User doesn't have authorization permissions",
            "admin_list": "🔐 <b>Authorized Users:</b>\n{user_list}",
            "admin_no_users": "ℹ️ No authorized users found",
            
            # System Messages
            "system_starting": "🚀 Starting TgMusicBot...",
            "system_ready": "✅ TgMusicBot is ready!",
            "system_shutdown": "🛑 Shutting down TgMusicBot...",
            "system_error": "❌ System error: {error}",
            
            # Privacy Policy
            "privacy_title": "🔒 Privacy Policy",
            "privacy_content": "<b>Privacy Policy for TgMusicBot</b>\n\n<b>1. Information We Collect:</b>\n• Chat IDs and User IDs for bot functionality\n• Message content for music playback\n• Usage statistics for performance monitoring\n\n<b>2. How We Use Information:</b>\n• Provide music streaming services\n• Manage user permissions and settings\n• Improve bot performance and features\n\n<b>3. Data Storage:</b>\n• Data is stored securely in MongoDB\n• We do not share your data with third parties\n• You can request data deletion\n\n<b>4. Contact:</b>\nFor questions about this policy, contact us at <a href='https://t.me/+zFIaHmyIfwMzZjBl'>Support Group</a>",
            
            # Stats Messages
            "stats_title": "📊 <b>Bot Statistics</b>",
            "stats_uptime": "⏱️ <b>Uptime:</b> <code>{uptime}</code>",
            "stats_users": "👥 <b>Total Users:</b> <code>{users}</code>",
            "stats_chats": "💬 <b>Total Chats:</b> <code>{chats}</code>",
            "stats_cpu": "🧠 <b>CPU Usage:</b> <code>{cpu}%</code>",
            "stats_memory": "💾 <b>Memory Usage:</b> <code>{memory}%</code>",
            
            # Broadcast Messages
            "broadcast_start": "📢 Starting broadcast...",
            "broadcast_success": "✅ Broadcast completed successfully",
            "broadcast_error": "❌ Broadcast failed: {error}",
            
            # Maintenance Messages
            "maintenance_active_vc": "📞 <b>Active Voice Chats:</b>\n{vc_list}",
            "maintenance_no_vc": "📞 No active voice chats",
            "maintenance_cleared": "🧹 All assistants data cleared",
            "maintenance_autoend": "🔄 Auto-end setting updated",
            
            # Playback Messages
            "playback_now_playing": "🎵 <b>Now Playing:</b>\n\n",
            "playback_download_failed": "❌ Download failed: {error}",
            "playback_failed": "❌ Failed to download track",
            "playback_error": "⚠️ Playback error: {error}",
            "playback_no_tracks": "❌ No tracks found in the provided source.",
            "playback_download_failed_title": "<b>⚠️ Download Failed</b>\n\n",
            "playback_search_failed": "🔍 Search failed: {error}",
            "playback_no_results": "🔍 No results found. Try different keywords.",
            "playback_track_info_error": "⚠️ Track info error: {error}",
            "playback_groups_only": "❌ This command only works in groups/channels.",
            "playback_queue_limit": "⚠️ Queue limit reached (10 tracks max). Use /end to clear queue.",
            "playback_admin_required": "⚠️ I need admin privileges with 'Invite Users' permission ",
            "playback_processing": "🔍 Processing request...",
            "playback_usage": "🎵 <b>Usage:</b>\n",
            "playback_unsupported_url": "⚠️ Unsupported URL\n\n",
            "playback_track_info_error_retrieve": "⚠️ Couldn't retrieve track info:\n{error}",
            "playback_video_error": "⚠️ Video error: {error}",
            
            # Queue Messages
            "queue_chat_error": "⚠️ <b>Error:</b> Could not fetch chat details\n<code>{error}</code>",
            "queue_total_tracks": "\n<b>📊 Total:</b> {count} track(s) in queue",
            
            # Volume Messages
            "volume_admin_check_failed": "⚠️ Admin check failed: {error}",
            "volume_invalid_number": "⚠️ Please enter a valid number between 1 and 200",
            "volume_range_error": "⚠️ Volume must be between 1% and 200%",
            "volume_error": "⚠️ <b>Error:</b> {error}",
            
            # Speed Messages
            "speed_range_error": "⚠️ Speed must be between 0.5x and 4.0x",
            "speed_error": "⚠️ <b>Error:</b> {error}",
            
            # Seek Messages
            "seek_invalid_number": "⚠️ Please enter a valid number of seconds.",
            "seek_positive_number": "⚠️ Please enter a positive number of seconds.",
            "seek_minimum_time": "⚠️ Minimum seek time is 20 seconds.",
            "seek_duration_error": "⚠️ <b>Error:</b> {error}",
            "seek_beyond_duration": "⚠️ Cannot seek beyond track duration ({duration}).",
            "seek_error": "⚠️ <b>Error:</b> {error}",
            "seek_now_at": "🎵 Now at: {current}/{total}",
            
            # Clear Messages
            "clear_success": "✅ Queue cleared by {user}",
            
            # Remove Messages
            "remove_invalid_number": "⚠️ Please enter a valid track number.",
            "remove_range_error": "⚠️ Invalid track number. Please choose between 1 and {max}.",
            "remove_success": "✅ Track <b>{track}</b> removed by {user}",
            
            # Loop Messages
            "loop_range_error": "⚠️ Loop count must be between 0 and 10",
            "loop_error": "⚠️ Failed to send reply: {error}",
            
            # Auth Messages
            "auth_reply_required": "🔍 Please reply to a user to manage their permissions.",
            "auth_error": "⚠️ Error: {error}",
            "auth_self_modify": "❌ You cannot modify your own permissions.",
            "auth_channel_error": "❌ Channels cannot be granted user permissions.",
            "auth_granted": "✅ User successfully granted authorization permissions.",
            "auth_revoked": "✅ User's authorization permissions have been revoked.",
            "auth_groups_only": "❌ This command is only available in groups.",
            
            # Owner Messages
            "owner_groups_only": "❌ This command is only available in groups.",
            "owner_buttons_enabled": "enabled ✅",
            "owner_buttons_disabled": "disabled ❌",
            "owner_buttons_success_enabled": "✅ Button controls enabled.",
            "owner_buttons_success_disabled": "❌ Button controls disabled.",
            "owner_invalid_usage": "⚠️ Invalid command usage.\n",
            "owner_thumb_enabled": "enabled ✅",
            "owner_thumb_disabled": "disabled ❌",
            "owner_thumb_success_enabled": "✅ Thumbnails enabled.",
            "owner_thumb_success_disabled": "❌ Thumbnails disabled.",
            
            # Update Messages
            "update_no_git": "⚠️ This instance does not support updates (no .git directory).",
            "update_git_not_found": "❌ Git not found on system.",
            "update_private_repo": "❌ Update failed: Private repo access denied. Please check your credentials or use SSH.",
            "update_git_pull_failed": "⚠️ Git pull failed:\n<pre>{output}</pre>",
            "update_already_updated": "✅ Bot is already up to date.",
            "update_success": "✅ Bot updated successfully. Restarting...\n<b>Update Output:</b>\n<pre>{output}</pre>",
            "update_error": "⚠️ Update error: {error}",
            "update_path_error": "❌ Unable to find 'tgmusic' in PATH.",
            
            # Shell Messages
            "shell_dangerous_blocked": "⚠️ Dangerous command blocked!",
            "shell_error": "<b>❌ Error:</b>\n<pre>{error}</pre>",
            "shell_execution_error": "⚠️ <b>Error:</b>\n<pre>{error}</pre>",
            
            # Function Messages
            "func_invalid_mode": "⚠️ Invalid mode. Use 0  or 1",
            "func_admin_check_failed": "⚠️ Admin check failed: {error}",
            "func_error": "⚠️ {message}\n<code>{error}</code>",
            
            # Progress Messages
            "progress_progress": "📊 <b>Progress:</b> {percentage}% {bar}\n",
            "progress_complete": "✅ <b>Download Complete:</b> <code>{filename}</code>\n",
            "progress_admin_required": "⚠️ You must be an admin to use this command.",
            
            # Watcher Messages
            "watcher_supergroup_required": "<b>⚠️ Please convert this chat to a supergroup and add me as admin.</b>\n\n",
            "watcher_member_count": "⚠️ This group has too few members ({count}).\n\n",
            
            # Jobs Messages
            "jobs_no_listeners": "⚠️ No active listeners. Leaving voice chat...",
            
            # Callback Messages
            "callback_playback_error": "⚠️ Playback error\nDetails: {error}",
            "callback_stop_failed": "⚠️ Failed to stop playback\n{error}",
            "callback_pause_failed": "⚠️ Pause failed\n{error}",
            "callback_resume_failed": "⚠️ Resume failed\n{error}",
            "callback_interface_failed": "⚠️ Interface closure failed\n{error}",
            "callback_interface_success": "✅ Interface closed successfully",
            "callback_invalid_request": "⚠️ Invalid request format",
            "callback_preparing": "🔍 Preparing playback for {user}",
            "callback_searching": "🔍 Searching...\nRequested by: {user}",
            "callback_unsupported_platform": "⚠️ Unsupported platform: {platform}",
            "callback_retrieval_error": "⚠️ Retrieval error\n{error}",
            "callback_content_not_found": "⚠️ Requested content not found",
        },
        
        "id-ID": {
            # Start and Help
            "start_welcome": "👋 <b>Halo {user_name}!</b>\n\nSelamat datang di <b>{bot_name}</b> — bot musik terbaik Anda.\n<code>Versi: v{version}</code>\n\n💡 <b>Apa yang membuat saya istimewa?</b>\n• Dukungan YouTube, Spotify, Apple Music, SoundCloud\n• Kontrol antrian dan pemutaran canggih\n• Penggunaan pribadi dan grup\n\n🔍 <i>Pilih kategori bantuan di bawah untuk melanjutkan.</i>",
            "start_home": "👋 <b>Halo {user_name}!</b>\n\nSelamat datang di <b>{bot_name}</b> — bot musik terbaik Anda.\n<code>Versi: v{version}</code>\n\n🎵 <b>Mulai Cepat:</b>\n• <code>/play [lagu]</code> — Putar musik di voice chat\n• <code>/help</code> — Tampilkan menu bantuan\n\n🌐 <b>Bahasa:</b> {current_lang}\n\n<i>Gunakan tombol di bawah untuk memulai!</i>",
            
            # Help Categories
            "help_user_title": "🎧 Perintah Pengguna",
            "help_user_content": "<b>▶️ Pemutaran:</b>\n• <code>/play [lagu]</code> — Putar audio di VC\n• <code>/vplay [video]</code> — Putar video di VC\n<b>🛠 Utilitas:</b>\n• <code>/start</code> — Pesan intro\n• <code>/privacy</code> — Kebijakan privasi\n• <code>/queue</code> — Lihat antrian lagu\n• <code>/language</code> — Ganti bahasa bot",
            
            "help_admin_title": "⚙️ Perintah Admin",
            "help_admin_content": "<b>🎛 Kontrol Pemutaran:</b>\n• <code>/skip</code> — Lewati lagu saat ini\n• <code>/pause</code> — Jeda pemutaran\n• <code>/resume</code> — Lanjutkan pemutaran\n• <code>/seek [detik]</code> — Lompat ke posisi\n• <code>/volume [1-200]</code> — Atur volume pemutaran\n\n<b>📋 Manajemen Antrian:</b>\n• <code>/remove [x]</code> — Hapus lagu nomor x\n• <code>/clear</code> — Bersihkan seluruh antrian\n• <code>/loop [0-10]</code> — Ulangi antrian x kali\n\n<b>👑 Izin:</b>\n• <code>/auth [reply]</code> — Berikan akses admin\n• <code>/unauth [reply]</code> — Cabut akses admin\n• <code>/authlist</code> — Lihat pengguna yang diizinkan",
            
            "help_owner_title": "🔐 Perintah Owner",
            "help_owner_content": "<b>⚙️ Pengaturan:</b>\n• <code>/buttons</code> — Toggle tombol kontrol\n• <code>/thumb</code> — Toggle mode thumbnail",
            
            "help_devs_title": "🛠 Alat Developer",
            "help_devs_content": "<b>📊 Alat Sistem:</b>\n• <code>/stats</code> — Tampilkan statistik penggunaan\n• <code>/logger</code> — Toggle mode log\n• <code>/broadcast</code> — Kirim pesan ke semua\n• <code>/performance</code> — Tampilkan metrik performa\n\n<b>🧹 Pemeliharaan:</b>\n• <code>/activevc</code> — Tampilkan voice chat aktif\n• <code>/clearallassistants</code> — Hapus semua data asisten dari DB\n• <code>/autoend</code> — Aktifkan auto-leave saat VC kosong",
            
            # Language System
            "language_title": "🌐 Pengaturan Bahasa",
            "language_current": "Bahasa Saat Ini: <b>{language}</b>",
            "language_select": "Pilih bahasa yang Anda inginkan:",
            "language_changed": "✅ Bahasa diubah ke <b>{language}</b>",
            "language_error": "❌ Error mengubah bahasa",
            
            # Common Messages
            "back_button": "🔙 Kembali",
            "home_button": "🏠 Beranda",
            "help_button": "❓ Bantuan",
            "language_button": "🌐 Bahasa",
            
            # Error Messages
            "error_generic": "❌ Terjadi kesalahan",
            "error_permission": "⛔ Anda tidak memiliki izin untuk menggunakan perintah ini",
            "error_admin_required": "⛔ Diperlukan hak istimewa Administrator untuk tindakan ini",
            "error_invalid_request": "⚠️ Format permintaan tidak valid",
            "error_not_found": "⚠️ Konten yang diminta tidak ditemukan",
            
            # Success Messages
            "success_operation": "✅ Operasi berhasil diselesaikan",
            "success_language_changed": "✅ Bahasa berhasil diubah",
            
            # Performance Dashboard
            "performance_title": "🔥 <b>Dashboard Performa TgMusicBot</b>",
            "performance_system_info": "⏱️ <b>Info Sistem:</b>",
            "performance_database": "💾 <b>Performa Database:</b>",
            "performance_music_cache": "🎵 <b>Cache Musik:</b>",
            "performance_api": "🌐 <b>Performa API:</b>",
            "performance_call_stats": "📊 <b>Statistik Panggilan:</b>",
            
            # Button Labels
            "btn_play": "▶️ Putar",
            "btn_pause": "⏸️ Jeda",
            "btn_resume": "▶️ Lanjutkan",
            "btn_skip": "⏭️ Lewati",
            "btn_stop": "⏹️ Berhenti",
            "btn_close": "❌ Tutup",
            "btn_volume_up": "🔊 Volume +",
            "btn_volume_down": "🔉 Volume -",
            "btn_loop": "🔁 Ulang",
            "btn_shuffle": "🔀 Acak",
            
            # Queue Messages
            "queue_empty": "📭 Antrian kosong",
            "queue_current": "🎵 <b>Sedang Diputar:</b>\n{current_track}\n\n📋 <b>Antrian:</b>\n{queue_list}",
            "queue_added": "✅ Ditambahkan ke antrian: <b>{track_name}</b>",
            "queue_removed": "✅ Dihapus dari antrian: <b>{track_name}</b>",
            "queue_cleared": "🗑️ Antrian dibersihkan",
            
            # Playback Messages
            "playback_started": "🎵 Mulai memutar: <b>{track_name}</b>",
            "playback_paused": "⏸️ Pemutaran dijeda",
            "playback_resumed": "▶️ Pemutaran dilanjutkan",
            "playback_skipped": "⏭️ Lagu dilewati",
            "playback_stopped": "⏹️ Pemutaran dihentikan",
            "playback_volume": "🔊 Volume diatur ke: <b>{volume}%</b>",
            
            # Search Messages
            "search_started": "🔍 Mencari: <b>{query}</b>",
            "search_found": "✅ Ditemukan: <b>{track_name}</b>",
            "search_not_found": "❌ Tidak ada hasil untuk: <b>{query}</b>",
            "search_error": "⚠️ Error pencarian: {error}",
            
            # Admin Messages
            "admin_auth_granted": "✅ Pengguna diberikan izin otorisasi",
            "admin_auth_revoked": "✅ Izin otorisasi pengguna telah dicabut",
            "admin_auth_already": "ℹ️ Pengguna sudah memiliki izin otorisasi",
            "admin_auth_not_found": "ℹ️ Pengguna tidak memiliki izin otorisasi",
            "admin_list": "🔐 <b>Pengguna yang Diizinkan:</b>\n{user_list}",
            "admin_no_users": "ℹ️ Tidak ada pengguna yang diizinkan",
            
            # System Messages
            "system_starting": "🚀 Memulai TgMusicBot...",
            "system_ready": "✅ TgMusicBot siap!",
            "system_shutdown": "🛑 Mematikan TgMusicBot...",
            "system_error": "❌ Error sistem: {error}",
            
            # Privacy Policy
            "privacy_title": "🔒 Kebijakan Privasi",
            "privacy_content": "<b>Kebijakan Privasi untuk TgMusicBot</b>\n\n<b>1. Informasi yang Kami Kumpulkan:</b>\n• Chat ID dan User ID untuk fungsi bot\n• Konten pesan untuk pemutaran musik\n• Statistik penggunaan untuk pemantauan performa\n\n<b>2. Bagaimana Kami Menggunakan Informasi:</b>\n• Menyediakan layanan streaming musik\n• Mengelola izin dan pengaturan pengguna\n• Meningkatkan performa dan fitur bot\n\n<b>3. Penyimpanan Data:</b>\n• Data disimpan dengan aman di MongoDB\n• Kami tidak membagikan data Anda dengan pihak ketiga\n• Anda dapat meminta penghapusan data\n\n<b>4. Kontak:</b>\nUntuk pertanyaan tentang kebijakan ini, hubungi kami di <a href='https://t.me/+zFIaHmyIfwMzZjBl'>Grup Dukungan</a>",
            
            # Stats Messages
            "stats_title": "📊 <b>Statistik Bot</b>",
            "stats_uptime": "⏱️ <b>Waktu Aktif:</b> <code>{uptime}</code>",
            "stats_users": "👥 <b>Total Pengguna:</b> <code>{users}</code>",
            "stats_chats": "💬 <b>Total Chat:</b> <code>{chats}</code>",
            "stats_cpu": "🧠 <b>Penggunaan CPU:</b> <code>{cpu}%</code>",
            "stats_memory": "💾 <b>Penggunaan Memori:</b> <code>{memory}%</code>",
            
            # Broadcast Messages
            "broadcast_start": "📢 Memulai broadcast...",
            "broadcast_success": "✅ Broadcast berhasil diselesaikan",
            "broadcast_error": "❌ Broadcast gagal: {error}",
            
            # Maintenance Messages
            "maintenance_active_vc": "📞 <b>Voice Chat Aktif:</b>\n{vc_list}",
            "maintenance_no_vc": "📞 Tidak ada voice chat aktif",
            "maintenance_cleared": "🧹 Semua data asisten dibersihkan",
            "maintenance_autoend": "🔄 Pengaturan auto-end diperbarui",
            
            # Playback Messages
            "playback_now_playing": "🎵 <b>Sedang Diputar:</b>\n\n",
            "playback_download_failed": "❌ Download gagal: {error}",
            "playback_failed": "❌ Gagal mengunduh lagu",
            "playback_error": "⚠️ Error pemutaran: {error}",
            "playback_no_tracks": "❌ Tidak ada lagu ditemukan dalam sumber yang diberikan.",
            "playback_download_failed_title": "<b>⚠️ Download Gagal</b>\n\n",
            "playback_search_failed": "🔍 Pencarian gagal: {error}",
            "playback_no_results": "🔍 Tidak ada hasil ditemukan. Coba kata kunci yang berbeda.",
            "playback_track_info_error": "⚠️ Error info lagu: {error}",
            "playback_groups_only": "❌ Perintah ini hanya berfungsi di grup/saluran.",
            "playback_queue_limit": "⚠️ Batas antrian tercapai (maksimal 10 lagu). Gunakan /end untuk membersihkan antrian.",
            "playback_admin_required": "⚠️ Saya memerlukan hak istimewa admin dengan izin 'Undang Pengguna' ",
            "playback_processing": "🔍 Memproses permintaan...",
            "playback_usage": "🎵 <b>Cara Penggunaan:</b>\n",
            "playback_unsupported_url": "⚠️ URL tidak didukung\n\n",
            "playback_track_info_error_retrieve": "⚠️ Tidak dapat mengambil info lagu:\n{error}",
            "playback_video_error": "⚠️ Error video: {error}",
            
            # Queue Messages
            "queue_chat_error": "⚠️ <b>Error:</b> Tidak dapat mengambil detail chat\n<code>{error}</code>",
            "queue_total_tracks": "\n<b>📊 Total:</b> {count} lagu dalam antrian",
            
            # Volume Messages
            "volume_admin_check_failed": "⚠️ Pemeriksaan admin gagal: {error}",
            "volume_invalid_number": "⚠️ Silakan masukkan angka yang valid antara 1 dan 200",
            "volume_range_error": "⚠️ Volume harus antara 1% dan 200%",
            "volume_error": "⚠️ <b>Error:</b> {error}",
            
            # Speed Messages
            "speed_range_error": "⚠️ Kecepatan harus antara 0.5x dan 4.0x",
            "speed_error": "⚠️ <b>Error:</b> {error}",
            
            # Seek Messages
            "seek_invalid_number": "⚠️ Silakan masukkan angka detik yang valid.",
            "seek_positive_number": "⚠️ Silakan masukkan angka positif.",
            "seek_minimum_time": "⚠️ Waktu seek minimum adalah 20 detik.",
            "seek_duration_error": "⚠️ <b>Error:</b> {error}",
            "seek_beyond_duration": "⚠️ Tidak dapat seek melebihi durasi lagu ({duration}).",
            "seek_error": "⚠️ <b>Error:</b> {error}",
            "seek_now_at": "🎵 Sekarang di: {current}/{total}",
            
            # Clear Messages
            "clear_success": "✅ Antrian dibersihkan oleh {user}",
            
            # Remove Messages
            "remove_invalid_number": "⚠️ Silakan masukkan nomor lagu yang valid.",
            "remove_range_error": "⚠️ Nomor lagu tidak valid. Silakan pilih antara 1 dan {max}.",
            "remove_success": "✅ Lagu <b>{track}</b> dihapus oleh {user}",
            
            # Loop Messages
            "loop_range_error": "⚠️ Jumlah loop harus antara 0 dan 10",
            "loop_error": "⚠️ Gagal mengirim balasan: {error}",
            
            # Auth Messages
            "auth_reply_required": "🔍 Silakan balas ke pengguna untuk mengelola izin mereka.",
            "auth_error": "⚠️ Error: {error}",
            "auth_self_modify": "❌ Anda tidak dapat mengubah izin Anda sendiri.",
            "auth_channel_error": "❌ Saluran tidak dapat diberikan izin pengguna.",
            "auth_granted": "✅ Pengguna berhasil diberikan izin otorisasi.",
            "auth_revoked": "✅ Izin otorisasi pengguna telah dicabut.",
            "auth_groups_only": "❌ Perintah ini hanya tersedia di grup.",
            
            # Owner Messages
            "owner_groups_only": "❌ Perintah ini hanya tersedia di grup.",
            "owner_buttons_enabled": "diaktifkan ✅",
            "owner_buttons_disabled": "dinonaktifkan ❌",
            "owner_buttons_success_enabled": "✅ Kontrol tombol diaktifkan.",
            "owner_buttons_success_disabled": "❌ Kontrol tombol dinonaktifkan.",
            "owner_invalid_usage": "⚠️ Penggunaan perintah tidak valid.\n",
            "owner_thumb_enabled": "diaktifkan ✅",
            "owner_thumb_disabled": "dinonaktifkan ❌",
            "owner_thumb_success_enabled": "✅ Thumbnail diaktifkan.",
            "owner_thumb_success_disabled": "❌ Thumbnail dinonaktifkan.",
            
            # Update Messages
            "update_no_git": "⚠️ Instance ini tidak mendukung pembaruan (tidak ada direktori .git).",
            "update_git_not_found": "❌ Git tidak ditemukan di sistem.",
            "update_private_repo": "❌ Pembaruan gagal: Akses repo pribadi ditolak. Silakan periksa kredensial Anda atau gunakan SSH.",
            "update_git_pull_failed": "⚠️ Git pull gagal:\n<pre>{output}</pre>",
            "update_already_updated": "✅ Bot sudah diperbarui.",
            "update_success": "✅ Bot berhasil diperbarui. Memulai ulang...\n<b>Output Pembaruan:</b>\n<pre>{output}</pre>",
            "update_error": "⚠️ Error pembaruan: {error}",
            "update_path_error": "❌ Tidak dapat menemukan 'tgmusic' di PATH.",
            
            # Shell Messages
            "shell_dangerous_blocked": "⚠️ Perintah berbahaya diblokir!",
            "shell_error": "<b>❌ Error:</b>\n<pre>{error}</pre>",
            "shell_execution_error": "⚠️ <b>Error:</b>\n<pre>{error}</pre>",
            
            # Function Messages
            "func_invalid_mode": "⚠️ Mode tidak valid. Gunakan 0 atau 1",
            "func_admin_check_failed": "⚠️ Pemeriksaan admin gagal: {error}",
            "func_error": "⚠️ {message}\n<code>{error}</code>",
            
            # Progress Messages
            "progress_progress": "📊 <b>Progress:</b> {percentage}% {bar}\n",
            "progress_complete": "✅ <b>Download Selesai:</b> <code>{filename}</code>\n",
            "progress_admin_required": "⚠️ Anda harus menjadi admin untuk menggunakan perintah ini.",
            
            # Watcher Messages
            "watcher_supergroup_required": "<b>⚠️ Silakan ubah chat ini menjadi supergroup dan tambahkan saya sebagai admin.</b>\n\n",
            "watcher_member_count": "⚠️ Grup ini memiliki terlalu sedikit anggota ({count}).\n\n",
            
            # Jobs Messages
            "jobs_no_listeners": "⚠️ Tidak ada pendengar aktif. Meninggalkan voice chat...",
            
            # Callback Messages
            "callback_playback_error": "⚠️ Error pemutaran\nDetail: {error}",
            "callback_stop_failed": "⚠️ Gagal menghentikan pemutaran\n{error}",
            "callback_pause_failed": "⚠️ Jeda gagal\n{error}",
            "callback_resume_failed": "⚠️ Lanjutkan gagal\n{error}",
            "callback_interface_failed": "⚠️ Penutupan antarmuka gagal\n{error}",
            "callback_interface_success": "✅ Antarmuka berhasil ditutup",
            "callback_invalid_request": "⚠️ Format permintaan tidak valid",
            "callback_preparing": "🔍 Mempersiapkan pemutaran untuk {user}",
            "callback_searching": "🔍 Mencari...\nDiminta oleh: {user}",
            "callback_unsupported_platform": "⚠️ Platform tidak didukung: {platform}",
            "callback_retrieval_error": "⚠️ Error pengambilan\n{error}",
            "callback_content_not_found": "⚠️ Konten yang diminta tidak ditemukan",
        }
    }
    
    def __init__(self):
        self.current_language = self.DEFAULT_LANGUAGE
    
    async def get_language(self, user_id: int, chat_id: int = None) -> str:
        """Get user's or chat's preferred language from database."""
        try:
            # If chat_id is provided, get chat language first
            if chat_id and chat_id < 0:  # Group chat
                chat_lang = await db.get_chat_language(chat_id)
                if chat_lang != self.DEFAULT_LANGUAGE:
                    return chat_lang
            
            # Fallback to user language
            user_data = await db.get_user_language(user_id)
            return user_data.get("language", self.DEFAULT_LANGUAGE) if user_data else self.DEFAULT_LANGUAGE
        except Exception:
            return self.DEFAULT_LANGUAGE
    
    async def set_language(self, user_id: int, language: str, chat_id: int = None) -> bool:
        """Set user's or chat's preferred language in database."""
        try:
            if language not in self.SUPPORTED_LANGUAGES:
                return False
            
            # If chat_id is provided, set chat language
            if chat_id and chat_id < 0:  # Group chat
                await db.set_chat_language(chat_id, language)
            else:
                # Set user language
                await db.set_user_language(user_id, language)
            
            return True
        except Exception:
            return False
    
    def get_text(self, key: str, language: str = None, **kwargs) -> str:
        """Get translated text for given key and language."""
        if language is None:
            language = self.current_language
        
        if language not in self.TRANSLATIONS:
            language = self.DEFAULT_LANGUAGE
        
        text = self.TRANSLATIONS[language].get(key, f"[{key}]")
        
        # Format with kwargs if provided
        if kwargs:
            try:
                text = text.format(**kwargs)
            except KeyError:
                pass
        
        return text
    
    def get_supported_languages(self) -> Dict[str, str]:
        """Get list of supported languages."""
        return self.SUPPORTED_LANGUAGES.copy()
    
    def is_supported_language(self, language: str) -> bool:
        """Check if language is supported."""
        return language in self.SUPPORTED_LANGUAGES


# Global language manager instance
language_manager = LanguageManager() 
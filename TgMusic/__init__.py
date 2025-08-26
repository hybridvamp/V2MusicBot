# Copyright (c) 2025 AshokShau
# Licensed under the GNU AGPL v3.0: https://www.gnu.org/licenses/agpl-3.0.html
# Part of the TgMusicBot project. All rights reserved where applicable.
#  Modified by Devin - Major modifications and improvements


import asyncio
from datetime import datetime

from pytdbot import types, Client

__version__ = "1.2.2"
StartTime = datetime.now()


from TgMusic.core import call, tg, db, config

class Bot(Client):
    """Main bot class handling initialization and lifecycle management."""

    def __init__(self) -> None:
        """Initialize the bot with configuration and services."""
        super().__init__(
            token=config.TOKEN,
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            default_parse_mode="html",
            td_verbosity=2,
            td_log=types.LogStreamEmpty(),
            plugins=types.plugins.Plugins(folder="TgMusic/modules"),
            files_directory="",
            database_encryption_key="",
            options={"ignore_background_updates": config.IGNORE_BACKGROUND_UPDATES},
        )

        self._initialize_services()

    def _initialize_services(self) -> None:
        """Initialize all service dependencies."""
        from TgMusic.modules.jobs import InactiveCallManager
        self.config = config
        self.db = db
        self.call = call
        self.tg = tg
        self.call_manager = InactiveCallManager(self)
        self._start_time = StartTime
        self._version = __version__

    async def start(self) -> None:
        """Start the bot and all associated services with proper error handling."""
        try:
            # Start metrics monitoring
            from TgMusic.core.metrics import metrics_manager
            metrics_manager.start_monitoring()
            
            await self._initialize_components()
            uptime = self._get_uptime()
            self.logger.info(f"Bot started successfully in {uptime:.2f} seconds")
            self.logger.info(f"Version: {self._version}")
            
            # Log startup statistics
            self.logger.info("=" * 60)
            self.logger.info("Bot initialization completed successfully")
            self.logger.info(f"Session strings configured: {len(self.config.SESSION_STRINGS)}")
            self.logger.info(f"Default service: {self.config.DEFAULT_SERVICE}")
            self.logger.info(f"Auto leave enabled: {self.config.AUTO_LEAVE}")
            self.logger.info("=" * 60)
            self.logger.info("=" * 60)
            # self.logger.info("Starting proxy updater")
            # asyncio.create_task(proxy_updater())
            # self.logger.info("Proxy updater Started******")
            
        except Exception as e:
            self.logger.critical(f"Failed to start bot: {e}", exc_info=True)
            raise

    async def start_clients(self) -> None:
        """Initialize all client sessions."""
        try:
            await asyncio.gather(
                *[
                    self.call.start_client(config.API_ID, config.API_HASH, session_str)
                    for session_str in config.SESSION_STRINGS
                ]
            )
        except Exception as exc:
            raise SystemExit(1) from exc

    async def _initialize_components(self) -> None:
        from TgMusic.core import save_all_cookies

        # Save cookies from URLs only
        await save_all_cookies(config.COOKIES_URL)
        await self.db.ping()
        await self.start_clients()
        await self.call.add_bot(self)
        await self.call.register_decorators()
        await super().start()
        await self.call_manager.start()

    async def stop(self, graceful: bool = True) -> None:
        try:
            # Stop metrics monitoring
            from TgMusic.core.metrics import metrics_manager
            metrics_manager.stop_monitoring()
            
            # Log final statistics
            stats = metrics_manager.get_comprehensive_stats()
            self.logger.info("=" * 60)
            self.logger.info("Bot shutdown initiated")
            self.logger.info(f"Total commands executed: {stats['bot']['total_commands']}")
            self.logger.info(f"Total errors encountered: {stats['bot']['total_errors']}")
            self.logger.info(f"Active chats: {stats['bot']['active_chats']}")
            self.logger.info("=" * 60)
            
            shutdown_tasks = [
                self.db.close(),
                self.call_manager.stop(),
            ]

            if graceful:
                await asyncio.gather(*shutdown_tasks, super().stop())
            else:
                await super().stop()
                
            self.logger.info("Bot shutdown completed successfully")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}", exc_info=True)
            raise

    def _get_uptime(self) -> float:
        """Calculate bot uptime in seconds."""
        return (datetime.now() - self._start_time).total_seconds()


client: Client = Bot()

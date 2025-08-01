#  Copyright (c) 2025 AshokShau
#  Licensed under the GNU AGPL v3.0: https://www.gnu.org/licenses/agpl-3.0.html
#  Part of the TgMusicBot project. All rights reserved where applicable.
#  Modified by Devin - Major modifications and improvements

import asyncio
import signal
import sys
from TgMusic import client
from TgMusic.core import db


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    client.logger.info(f"Received signal {signum}, shutting down gracefully...")
    
    async def shutdown():
        try:
            # Close database connection
            await db.close()
            client.logger.info("Database connection closed.")
            
            # Stop the client
            await client.stop()
            client.logger.info("Client stopped.")
            
        except Exception as e:
            client.logger.error(f"Error during shutdown: {e}")
        finally:
            sys.exit(0)
    
    # Run shutdown in event loop
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(shutdown())
        else:
            loop.run_until_complete(shutdown())
    except Exception as e:
        client.logger.error(f"Error in shutdown handler: {e}")
        sys.exit(1)


def main() -> None:
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Termination signal
    
    client.logger.info("Starting TgMusicBot...")
    client.run()


if __name__ == "__main__":
    main()

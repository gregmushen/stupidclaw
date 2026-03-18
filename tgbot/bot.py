"""StupidClaw Telegram bot entry point.

Runs the Telegram polling loop and HTTP notification server concurrently.
"""

import asyncio
import logging
import sys

import aiohttp.web
from telegram.ext import Application, MessageHandler, filters

from tgbot.config import get_bot_token, get_chat_id, get_notify_port
from tgbot.handlers.inbound import handle_text, handle_photo
from tgbot.handlers.reply import handle_reply
from tgbot.server.notify import create_notify_app, set_bot


def setup_logging() -> logging.Logger:
    """Configure root logger. Returns the bot's named logger."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    return logging.getLogger("stupidclaw.telegram.bot")


async def main():
    """Main async entry point. Registers handlers and starts polling + HTTP server."""
    logger = setup_logging()
    logger.info("StupidClaw Telegram bot starting")

    # Validate config at startup (fail fast)
    get_bot_token()
    get_chat_id()
    port = get_notify_port()

    logger.info(f"Notify server will listen on port {port}")

    # Build the Telegram application
    app = Application.builder().token(get_bot_token()).build()

    # Register handlers (order matters — first match wins)
    app.add_handler(MessageHandler(filters.REPLY, handle_reply))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # Give the notify server access to the bot instance
    set_bot(app.bot)

    # Start HTTP notification server
    notify_app = create_notify_app()
    runner = aiohttp.web.AppRunner(notify_app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    logger.info(f"Notify server listening on 0.0.0.0:{port}")

    # Start Telegram polling
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    logger.info("Bot fully initialized — polling and HTTP server running")

    # Run forever
    try:
        await asyncio.Event().wait()
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())

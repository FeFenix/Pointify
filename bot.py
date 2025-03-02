import logging
import signal
import sys
from telegram.ext import (
    Application, 
    CommandHandler, 
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters
)
import config
import handlers

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info("Received shutdown signal. Cleaning up...")
    sys.exit(0)

async def error_handler(update, context):
    """Log errors caused by Updates."""
    logger.error(f"Update {update} caused error {context.error}")
    if "Conflict" in str(context.error):
        logger.error("Bot instance conflict detected. Please ensure only one instance is running.")
        sys.exit(1)

def main():
    """Start the bot"""
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Create the Application and pass it your bot's token
        application = Application.builder().token(config.BOT_TOKEN).build()

        # Register error handler
        application.add_error_handler(error_handler)

        # Add conversation handler for points management
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("a", handlers.admin_command)],
            states={
                handlers.CHOOSING_ACTION: [
                    CallbackQueryHandler(handlers.button_callback)
                ],
                handlers.CHOOSING_USER: [
                    CallbackQueryHandler(handlers.user_callback)
                ],
                handlers.ENTERING_POINTS: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.points_entered)
                ]
            },
            fallbacks=[CommandHandler("cancel", handlers.cancel)],
            per_chat=False,
            name="admin_conversation"
        )

        # Add handlers
        application.add_handler(conv_handler)
        application.add_handler(CommandHandler("help", handlers.help_command))
        application.add_handler(CommandHandler("top", handlers.show_top))
        application.add_handler(CommandHandler("ac", handlers.clear_all_points))

        # Add message handler to track users (outside of conversation)
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handlers.handle_user_message
        ))

        # Start the bot
        logger.info("Bot started successfully")
        application.run_polling(drop_pending_updates=True)

    except Exception as e:
        logger.error(f"Critical error: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()

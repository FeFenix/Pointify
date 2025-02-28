import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)
import config
from database import Database

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Define states
CHOOSING_ACTION, CHOOSING_USER, ENTERING_POINTS = range(3)

# Initialize database
db = Database()

def is_admin(user_id: int) -> bool:
    """Check if user is admin dynamically from database"""
    return db.is_admin(user_id)

def is_user_registered(chat_id: int, user_id: int) -> bool:
    """Check if user is registered in the database"""
    return db.user_exists(chat_id, user_id)

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular messages to track users"""
    try:
        user = update.effective_user
        chat = update.effective_chat

        if user and chat and user.username:
            success = db.add_points(chat.id, user.id, 0, user.username)
            if success:
                logger.info(f"Successfully tracked user {user.username} with ID {user.id} in chat {chat.id}")
            else:
                logger.error(f"Failed to track user {user.username} in chat {chat.id}")
    except Exception as e:
        logger.error(f"Error handling user message: {str(e)}")

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /a command"""
    try:
        user = update.effective_user
        if not user:
            return ConversationHandler.END

        if not is_admin(user.id):
            await update.message.reply_text(config.NOT_ADMIN_MESSAGE)
            return ConversationHandler.END

        context.user_data['messages_to_delete'] = [update.message.message_id]

        keyboard = [
            [
                InlineKeyboardButton("Додати бали", callback_data='add'),
                InlineKeyboardButton("Забрати бали", callback_data='subtract')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        menu_message = await update.message.reply_text(
            text="Оберіть дію:",
            reply_markup=reply_markup
        )
        context.user_data['messages_to_delete'].append(menu_message.message_id)
        return CHOOSING_ACTION
    except Exception as e:
        logger.error(f"Error in admin_command: {str(e)}")
        return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /help command"""
    try:
        await update.message.reply_text(config.HELP_MESSAGE)
    except Exception as e:
        logger.error(f"Error in help_command: {str(e)}")

async def clear_all_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /allclear command"""
    try:
        if not is_admin(update.effective_user.id):
            await update.message.reply_text(config.NOT_ADMIN_MESSAGE)
            return

        chat_id = update.effective_chat.id
        db.clear_all_points(chat_id)
        await update.message.reply_text("Всі бали були успішно очищені!")
    except Exception as e:
        logger.error(f"Error in clear_all_points: {str(e)}")

async def show_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /top command"""
    try:
        chat_id = update.effective_chat.id
        top_users = db.get_top_users(chat_id, 10)

        if not top_users:
            await update.message.reply_text("В базі даних ще немає користувачів!")
            return

        message = "\U0001F4A1👑 ТОП 10 КОРИСТУВАЧІВ 👑\U0001F4A1\n\n"
        for i, (user_id, user_data) in enumerate(top_users, 1):
            username = user_data["username"] or f"User {user_id}"
            emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "⭐"
            message += f"{i}. {emoji} @{username}: {user_data['points']} балів\n"

        await update.message.reply_text(message)
    except Exception as e:
        logger.error(f"Error in show_top: {str(e)}")

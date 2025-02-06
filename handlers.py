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
    """Check if user is admin"""
    return user_id == config.ADMIN_USER_ID

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular messages to track users"""
    try:
        user = update.effective_user
        if user and user.username:
            db.add_points(user.id, 0, user.username)
            logger.info(f"Stored user {user.username} with ID {user.id}")
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

        keyboard = [
            [
                InlineKeyboardButton("Додати бали", callback_data='add'),
                InlineKeyboardButton("Забрати бали", callback_data='subtract')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            text="Оберіть дію:",
            reply_markup=reply_markup
        )
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

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    try:
        query = update.callback_query
        await query.answer()

        if not is_admin(update.effective_user.id):
            await query.message.edit_text(config.NOT_ADMIN_MESSAGE)
            return ConversationHandler.END

        action = query.data
        context.user_data['action'] = action

        users = db.get_all_users()
        keyboard = []
        for username in users:
            keyboard.append([InlineKeyboardButton(f"@{username}", callback_data=f"user_{username}")])

        if not keyboard:
            await query.message.edit_text("Наразі немає користувачів у базі даних.")
            return ConversationHandler.END

        reply_markup = InlineKeyboardMarkup(keyboard)
        text = "додати" if action == "add" else "забрати"
        await query.message.edit_text(
            f"Оберіть користувача, якому хочете {text} бали:",
            reply_markup=reply_markup
        )
        return CHOOSING_USER
    except Exception as e:
        logger.error(f"Error in button_callback: {str(e)}")
        return ConversationHandler.END

async def user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user selection"""
    try:
        query = update.callback_query
        await query.answer()

        username = query.data.replace("user_", "")
        context.user_data['username'] = username

        action = context.user_data.get('action')
        if not action:
            logger.error("No action found in context")
            return ConversationHandler.END

        text = "додати" if action == "add" else "забрати"
        await query.message.edit_text(
            f"Введіть кількість балів, які хочете {text} для користувача @{username}:"
        )
        return ENTERING_POINTS
    except Exception as e:
        logger.error(f"Error in user_callback: {str(e)}")
        return ConversationHandler.END

async def points_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle points entry"""
    try:
        points = int(update.message.text)

        if points <= 0:
            await update.message.reply_text("Кількість балів повинна бути додатньою!")
            return ENTERING_POINTS

        username = context.user_data.get('username')
        action = context.user_data.get('action')

        if not username or not action:
            logger.error("Missing username or action in context")
            return ConversationHandler.END

        user_id = db.get_user_id_by_username(username)
        if user_id is None:
            user_id = -abs(hash(username))
            logger.info(f"Creating temporary user ID {user_id} for username {username}")

        if action == 'add':
            db.add_points(user_id, points, username)
            message = f"{config.POINTS_UPDATED_MESSAGE} Користувач: @{username}, Бали: +{points}"
        else:
            db.subtract_points(user_id, points, username)
            message = f"{config.POINTS_UPDATED_MESSAGE} Користувач: @{username}, Бали: -{points}"

        context.user_data.clear()

        keyboard = [
            [
                InlineKeyboardButton("Додати бали", callback_data='add'),
                InlineKeyboardButton("Забрати бали", callback_data='subtract')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(message)
        await update.message.reply_text(
            text="Оберіть наступну дію:",
            reply_markup=reply_markup
        )
        return CHOOSING_ACTION
    except ValueError:
        await update.message.reply_text("Будь ласка, введіть числове значення!")
        return ENTERING_POINTS
    except Exception as e:
        logger.error(f"Error in points_entered: {str(e)}")
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the conversation"""
    try:
        context.user_data.clear()
        await update.message.reply_text("Операцію скасовано.")
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error in cancel: {str(e)}")
        return ConversationHandler.END

async def clear_all_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /allclear command"""
    try:
        if not is_admin(update.effective_user.id):
            await update.message.reply_text(config.NOT_ADMIN_MESSAGE)
            return

        db.clear_all_points()
        await update.message.reply_text("Всі бали були успішно очищені!")
    except Exception as e:
        logger.error(f"Error in clear_all_points: {str(e)}")

async def show_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /top command"""
    try:
        top_users = db.get_top_users(10)

        if not top_users:
            await update.message.reply_text("В базі даних ще немає користувачів!")
            return

        message = "🏆 Топ користувачів 🏆\n\n"
        for i, (user_id, user_data) in enumerate(top_users, 1):
            username = user_data["username"] or f"User {user_id}"
            message += f"{i}. @{username}: {user_data['points']} балів\n"

        await update.message.reply_text(message)
    except Exception as e:
        logger.error(f"Error in show_top: {str(e)}")
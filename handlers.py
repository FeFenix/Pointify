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
        chat = update.effective_chat

        if user and chat and user.username:
            # Add user to database with 0 points if they don't exist
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

        # Store the command message ID for later deletion
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
        # Store menu message ID
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

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    try:
        query = update.callback_query
        chat_id = query.message.chat_id
        await query.answer()

        if not is_admin(update.effective_user.id):
            await query.message.edit_text(config.NOT_ADMIN_MESSAGE)
            return ConversationHandler.END

        action = query.data

        # Handle finish action
        if action == 'finish':
            # Delete the original command message and all bot responses
            if 'messages_to_delete' in context.user_data:
                for message_id in context.user_data['messages_to_delete']:
                    try:
                        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
                    except Exception as e:
                        logger.error(f"Error deleting message {message_id}: {str(e)}")
                        continue

            # Delete the current menu message
            try:
                await query.message.delete()
            except Exception as e:
                logger.error(f"Error deleting menu message: {str(e)}")

            context.user_data.clear()
            return ConversationHandler.END

        context.user_data['action'] = action
        context.user_data['chat_id'] = chat_id

        users = db.get_all_users(chat_id)
        keyboard = []
        for username in users:
            keyboard.append([InlineKeyboardButton(f"@{username}", callback_data=f"user_{username}")])

        keyboard.append([InlineKeyboardButton("Завершити", callback_data='finish')])

        if not keyboard:
            message = await query.message.edit_text("Наразі немає користувачів у цьому чаті.")
            if 'messages_to_delete' not in context.user_data:
                context.user_data['messages_to_delete'] = []
            context.user_data['messages_to_delete'].append(message.message_id)
            return ConversationHandler.END

        reply_markup = InlineKeyboardMarkup(keyboard)
        text = "додати" if action == "add" else "забрати"

        # Store the current message for deletion
        try:
            menu_message = await query.message.edit_text(
                f"Оберіть користувача, якому хочете {text} бали:",
                reply_markup=reply_markup
            )
            if 'messages_to_delete' not in context.user_data:
                context.user_data['messages_to_delete'] = []
            context.user_data['messages_to_delete'].append(menu_message.message_id)
        except Exception as e:
            logger.error(f"Error updating menu message: {str(e)}")

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
        if 'messages_to_delete' not in context.user_data:
            context.user_data['messages_to_delete'] = []

        # Store user's points message for deletion
        context.user_data['messages_to_delete'].append(update.message.message_id)

        points = int(update.message.text)
        chat_id = context.user_data.get('chat_id')

        if points <= 0:
            message = await update.message.reply_text("Кількість балів повинна бути додатньою!")
            context.user_data['messages_to_delete'].append(message.message_id)
            return ENTERING_POINTS

        username = context.user_data.get('username')
        action = context.user_data.get('action')

        if not username or not action or not chat_id:
            logger.error("Missing username, action or chat_id in context")
            return ConversationHandler.END

        user_id = db.get_user_id_by_username(chat_id, username)
        if user_id is None:
            user_id = -abs(hash(username))
            logger.info(f"Creating temporary user ID {user_id} for username {username}")

        if action == 'add':
            db.add_points(chat_id, user_id, points, username)
            message = f"{config.POINTS_UPDATED_MESSAGE} Користувач: @{username}, Бали: +{points}"
        else:
            db.subtract_points(chat_id, user_id, points, username)
            message = f"{config.POINTS_UPDATED_MESSAGE} Користувач: @{username}, Бали: -{points}"

        keyboard = [
            [
                InlineKeyboardButton("Додати бали", callback_data='add'),
                InlineKeyboardButton("Забрати бали", callback_data='subtract')
            ],
            [InlineKeyboardButton("Завершити", callback_data='finish')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Store all bot responses for deletion
        result_message = await update.message.reply_text(message)
        menu_message = await update.message.reply_text(
            text="Оберіть наступну дію:",
            reply_markup=reply_markup
        )

        context.user_data['messages_to_delete'].extend([
            result_message.message_id,
            menu_message.message_id
        ])

        return CHOOSING_ACTION
    except ValueError:
        message = await update.message.reply_text("Будь ласка, введіть числове значення!")
        context.user_data['messages_to_delete'].append(message.message_id)
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

        message = "⚠️👀 Люди, Що Бачили Все! 👀⚠️\n\n"
        for i, (user_id, user_data) in enumerate(top_users, 1):
            username = user_data["username"] or f"User {user_id}"
            emoji = "👑" if i == 1 else "🏆" if i == 2 else "🐉" if i == 3 else "🚀"
            message += f"{i}. {emoji} @{username}: {user_data['points']} балів\n"

        await update.message.reply_text(message)
    except Exception as e:
        logger.error(f"Error in show_top: {str(e)}")

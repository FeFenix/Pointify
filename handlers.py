import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)
from telegram.constants import ChatMemberStatus
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

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    """Перевіряє чи є користувач адміністратором чату"""
    try:
        chat_id = update.effective_chat.id
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except Exception as e:
        logger.error(f"Помилка перевірки адміністратора: {e}")
        return False

async def track_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробляє подію додавання бота до чату"""
    try:
        for user in update.message.new_chat_members:
            if user.id == context.bot.id:
                await import_existing_members(update, context)
                return
    except Exception as e:
        logger.error(f"Помилка обробки нових учасників: {str(e)}")

async def import_existing_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Імпортує всіх існуючих користувачів чату"""
    try:
        chat_id = update.effective_chat.id
        members = await context.bot.get_chat_members(chat_id)
        
        for member in members:
            user = member.user
            if user.username:
                db.add_user(
                    chat_id=chat_id,
                    user_id=user.id,
                    username=user.username
                )
        logger.info(f"Імпортовано {len(members)} користувачів у чаті {chat_id}")
    except Exception as e:
        logger.error(f"Помилка імпорту користувачів: {str(e)}")

async def handle_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Оновлює дані користувача при будь-якому повідомленні"""
    try:
        user = update.effective_user
        chat = update.effective_chat
        if user and chat:
            db.add_user(chat.id, user.id, user.username)
    except Exception as e:
        logger.error(f"Помилка оновлення користувача: {str(e)}")  # Виправлено синтаксис

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /a command"""
    try:
        user = update.effective_user
        if not user:
            return ConversationHandler.END

        if not await is_admin(update, context, user.id):
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

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    try:
        query = update.callback_query
        chat_id = query.message.chat_id
        await query.answer()

        if not await is_admin(update, context, update.effective_user.id):
            await query.message.edit_text(config.NOT_ADMIN_MESSAGE)
            return ConversationHandler.END

        action = query.data

        if action == 'finish':
            if 'messages_to_delete' in context.user_data:
                for message_id in context.user_data['messages_to_delete']:
                    try:
                        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
                    except Exception as e:
                        logger.error(f"Error deleting message {message_id}: {str(e)}")
                        continue

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
        if not await is_admin(update, context, update.effective_user.id):
            await update.message

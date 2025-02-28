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
        logger.error(f"Помилка оновлення користувача: {str(e)}")

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

# Інші функції залишаються незмінними, тільки замінити всі виклики is_admin на нову перевірку
# ... (решта коду з попередньої версії handlers.py) ...

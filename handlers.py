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

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

CHOOSING_ACTION, CHOOSING_USER, ENTERING_POINTS = range(3)
db = Database()

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    try:
        chat_id = update.effective_chat.id
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except Exception as e:
        logger.error(f"Admin check error: {e}")
        return False

async def track_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        for user in update.message.new_chat_members:
            if user.id == context.bot.id:
                await import_existing_members(update, context)
                return
    except Exception as e:
        logger.error(f"New members error: {e}")

async def import_existing_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.effective_chat.id
        async for member in context.bot.get_chat_members(chat_id):
            user = member.user
            if user.username:
                db.add_user(chat_id, user.id, user.username)
        logger.info(f"Imported members in chat {chat_id}")
    except Exception as e:
        logger.error(f"Import members error: {e}")

async def handle_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        chat = update.effective_chat
        if user and chat:
            db.add_user(chat.id, user.id, user.username)
    except Exception as e:
        logger.error(f"Message handling error: {e}")

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        chat = update.effective_chat
        if user and chat and user.username:
            db.add_user(chat.id, user.id, user.username)
    except Exception as e:
        logger.error(f"User tracking error: {e}")

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        if not user or not await is_admin(update, context, user.id):
            await update.message.reply_text(config.NOT_ADMIN_MESSAGE)
            return ConversationHandler.END

        context.user_data['messages_to_delete'] = [update.message.message_id]

        keyboard = [
            [InlineKeyboardButton("Додати бали", callback_data='add'),
             InlineKeyboardButton("Забрати бали", callback_data='subtract')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        menu_message = await update.message.reply_text(
            "Оберіть дію:", reply_markup=reply_markup
        )
        context.user_data['messages_to_delete'].append(menu_message.message_id)
        return CHOOSING_ACTION
    except Exception as e:
        logger.error(f"Admin command error: {e}")
        return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(config.HELP_MESSAGE)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        
        if not await is_admin(update, context, query.from_user

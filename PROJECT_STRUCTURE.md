├── README.md           # Інструкції з встановлення
├── bot.py             # Головний файл бота
├── config.py          # Конфігурація та константи
├── database.py        # Робота з базою даних
└── handlers.py        # Обробники команд
```

## Налаштування проекту

### 1. Створення бота
1. Напишіть [@BotFather](https://t.me/BotFather) в Telegram
2. Створіть нового бота командою /newbot
3. Збережіть отриманий токен

### 2. Налаштування бази даних
1. Створіть базу даних PostgreSQL
2. Сформуйте URL підключення у форматі:
   ```
   postgresql://username:password@hostname:port/database_name?sslmode=require
   ```

### 3. Змінні середовища
Створіть наступні змінні середовища:
- `BOT_TOKEN` - токен вашого бота
- `DATABASE_URL` - URL підключення до бази даних

### 4. Встановлення залежностей
```bash
pip install python-telegram-bot sqlalchemy psycopg2-binary
```

## Код проекту

### bot.py
```python
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
        application.add_handler(CommandHandler("allclear", handlers.clear_all_points))

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
```

### config.py
```python
import os

# Telegram bot configuration
BOT_TOKEN = os.environ.get("BOT_TOKEN")  # Отримайте токен у @BotFather
ADMIN_USER_ID = None  # Замініть на ваш Telegram ID (можна дізнатись у @userinfobot)

# Messages
HELP_MESSAGE = """
Доступні команди:
/help - Показати це повідомлення
/top - Показати рейтинг по балам

Команди адміністратора:
/a - Меню адміністратора
/allclear - Очистити всі бали у всіх користувачів
"""

NOT_ADMIN_MESSAGE = "Вибачте, ця команда доступна тільки для адміністраторів."
INVALID_FORMAT_MESSAGE = "Неправильний формат команди. Використовуйте: /команда @username кількість_балів"
USER_NOT_FOUND_MESSAGE = "Користувача не знайдено."
POINTS_UPDATED_MESSAGE = "Бали успішно оновлено."
```

### database.py
```python
import os
from sqlalchemy import create_engine, Column, Integer, String, BigInteger, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
import logging
from sqlalchemy.exc import OperationalError
from time import sleep

# Configure logging with less verbose output
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.WARNING
)
logger = logging.getLogger(__name__)

# Get database URL from environment
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL is None:
    raise Exception("DATABASE_URL environment variable is not set")

def create_db_engine(retries=3, delay=1):
    """Create database engine with optimized connection pool"""
    for attempt in range(retries):
        try:
            engine = create_engine(
                DATABASE_URL,
                pool_size=10,
                max_overflow=20,
                pool_timeout=30,
                pool_recycle=1800,
                pool_pre_ping=True,
                connect_args={
                    'connect_timeout': 10,
                    'application_name': 'TelegramPointsBot',
                    'sslmode': 'require'
                }
            )

            # Test the connection
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return engine

        except OperationalError as e:
            if attempt == retries - 1:
                logger.error(f"Failed to connect to database after {retries} attempts")
                raise
            sleep(delay)
            delay *= 2

engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class UserPoints(Base):
    __tablename__ = "user_points"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(BigInteger, index=True)
    user_id = Column(BigInteger, index=True)
    username = Column(String)
    points = Column(Integer, default=0)

# Create tables
Base.metadata.create_all(bind=engine, checkfirst=True)

@contextmanager
def get_db():
    """Provide a transactional scope around a series of operations."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        logger.error(f"Database transaction failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()

class Database:
    def __init__(self):
        """Initialize database connection"""
        Base.metadata.create_all(bind=engine, checkfirst=True)

    def clear_all_points(self, chat_id: int):
        """Clear all points from the specific chat"""
        with get_db() as db:
            db.query(UserPoints).filter(UserPoints.chat_id == chat_id).update({"points": 0})

    def get_user_id_by_username(self, chat_id: int, username: str) -> int:
        """Get user_id by username for specific chat"""
        with get_db() as db:
            user = db.query(UserPoints.user_id).filter(
                UserPoints.chat_id == chat_id,
                UserPoints.username == username
            ).first()
            return user.user_id if user else None

    def get_all_users(self, chat_id: int) -> list:
        """Get list of all usernames in specific chat"""
        with get_db() as db:
            users = db.query(UserPoints.username).filter(
                UserPoints.chat_id == chat_id,
                UserPoints.username.isnot(None)
            ).all()
            return [user.username for user in users]

    def add_points(self, chat_id: int, user_id: int, points: int, username: str = None) -> bool:
        """Add points to a user in specific chat"""
        try:
            with get_db() as db:
                user = db.query(UserPoints).filter(
                    UserPoints.chat_id == chat_id,
                    UserPoints.user_id == user_id
                ).first()

                if not user:
                    user = UserPoints(
                        chat_id=chat_id,
                        user_id=user_id,
                        points=points,
                        username=username
                    )
                    db.add(user)
                else:
                    if username and user.username != username:
                        user.username = username
                    user.points += points

                return True
        except Exception as e:
            logger.error(f"Error in add_points: {e}")
            return False

    def subtract_points(self, chat_id: int, user_id: int, points: int, username: str = None) -> bool:
        """Subtract points from a user in specific chat"""
        try:
            with get_db() as db:
                user = db.query(UserPoints).filter(
                    UserPoints.chat_id == chat_id,
                    UserPoints.user_id == user_id
                ).first()

                if not user:
                    user = UserPoints(
                        chat_id=chat_id,
                        user_id=user_id,
                        points=0,
                        username=username
                    )
                    db.add(user)

                if username and user.username != username:
                    user.username = username
                user.points -= points

                return True
        except Exception as e:
            logger.error(f"Error in subtract_points: {e}")
            return False

    def get_user_points(self, chat_id: int, user_id: int) -> int:
        """Get points for a specific user in specific chat"""
        try:
            with get_db() as db:
                points = db.query(UserPoints.points).filter(
                    UserPoints.chat_id == chat_id,
                    UserPoints.user_id == user_id
                ).scalar()
                return points or 0
        except Exception as e:
            logger.error(f"Error in get_user_points: {e}")
            return 0

    def get_top_users(self, chat_id: int, limit: int = 10) -> list:
        """Get top users by points in specific chat"""
        try:
            with get_db() as db:
                users = db.query(
                    UserPoints.user_id,
                    UserPoints.points,
                    UserPoints.username
                ).filter(
                    UserPoints.chat_id == chat_id
                ).order_by(
                    UserPoints.points.desc()
                ).limit(limit).all()

                return [(user.user_id, {
                    "points": user.points,
                    "username": user.username
                }) for user in users]
        except Exception as e:
            logger.error(f"Error in get_top_users: {e}")
            return []
```

### handlers.py
```python
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
            # Delete all stored messages
            if 'messages_to_delete' in context.user_data:
                for message_id in context.user_data['messages_to_delete']:
                    try:
                        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
                    except Exception as e:
                        logger.error(f"Error deleting message {message_id}: {str(e)}")
                        continue  # Continue with other messages if one fails

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
        menu_message = await query.message.edit_text(
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
        # Store the points message for deletion
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

        # Store message IDs for later deletion
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

        message = "🏆 Топ користувачів 🏆\n\n"
        for i, (user_id, user_data) in enumerate(top_users, 1):
            username = user_data["username"] or f"User {user_id}"
            message += f"{i}. @{username}: {user_data['points']} балів\n"

        await update.message.reply_text(message)
    except Exception as e:
        logger.error(f"Error in show_top: {str(e)}")
import os

# Telegram bot configuration
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# Messages
HELP_MESSAGE = """
Доступні команди:
/help - Показати це повідомлення
/top - Показати рейтинг по балам

Команди адміністратора:
/a - Меню адміністратора
/ac - Очистити всі бали у всіх користувачів
"""

NOT_ADMIN_MESSAGE = "Вибачте, ця команда доступна тільки для адміністраторів."
USER_NOT_FOUND_MESSAGE = "Користувача не знайдено."
POINTS_UPDATED_MESSAGE = "Бали успішно оновлено."

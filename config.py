import os

# Telegram bot configuration
BOT_TOKEN = os.environ.get("BOT_TOKEN")  # Отримайте токен у @BotFather
ADMIN_USER_ID = int(os.environ.get("ADMIN_USER_ID", 0))  # ID адміністратора, отриманий через @userinfobot

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
INVALID_FORMAT_MESSAGE = "Неправильний формат команди. Використовуйте: /команда @username кількість_балів"
USER_NOT_FOUND_MESSAGE = "Користувача не знайдено."
POINTS_UPDATED_MESSAGE = "Бали успішно оновлено."

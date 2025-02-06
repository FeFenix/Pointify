# Telegram Points Bot

Telegram bot for managing the user points system with advanced administrative functions and statistical analysis.

## Functionality

- Manage user points through the admin panel
- View top users by the number of points
- Asynchronous processing of commands
- Fault-tolerant architecture

## Commands

- `/help` - Show a list of available commands
- `/top` - Show user rating by points
- `/a` - Administrator menu (for administrators only)
- `/allclear` - Clear all points (for administrators only)

## Settings.

1. Create a bot via @BotFather and get a token
2. Add the bot token to the `BOT_TOKEN` environment variable
3. Specify the administrator ID in `config.py`.
4. Run the bot with the command `python bot.py`

## Project structure

- `bot.py` - Main file with bot configuration
- `config.py` - Configuration and constants
- `database.py` - Working with the database
- `handlers.py` - Command handlers

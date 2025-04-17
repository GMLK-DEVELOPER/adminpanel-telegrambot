from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from config import Config
import logging

# Initialize bot
bot = Application.builder().token(Config.TELEGRAM_TOKEN).build()

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Привет! Я ваш Telegram бот. 👋')

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Список доступных команд:\n/start - Начать\n/help - Помощь')

# Message handler
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(update.message.text)

# Add handlers
bot.add_handler(CommandHandler("start", start))
bot.add_handler(CommandHandler("help", help))
bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

# Функция для запуска бота в режиме polling
def run_polling():
    try:
        print("Starting bot in polling mode...")
        # Удаляем webhook, если он был установлен ранее
        bot.bot.delete_webhook()
        # Запускаем бота с polling
        bot.run_polling(poll_interval=1.0, timeout=30)
    except Exception as e:
        logging.error(f"Error in polling: {e}")
        print(f"Error in polling: {e}") 
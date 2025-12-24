import os
import telebot
from flask import Flask
from threading import Thread

# Получаем токен из переменных окружения
TOKEN = os.getenv('TELEGRAM_TOKEN')
bot = telebot.TeleBot(TOKEN)

# Flask приложение для веб-сервера
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Telegram bot is running on Render!"

@app.route('/health')
def health():
    return "OK", 200

# Команда /start
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "🚀 Бот работает на Render 24/7!")

# Ответ на любое сообщение
@bot.message_handler(func=lambda message: True)
def echo(message):
    bot.reply_to(message, f"Вы написали: {message.text}")

# Запуск бота в отдельном потоке
bot_thread = Thread(target=lambda: bot.polling(none_stop=True, timeout=60))
bot_thread.daemon = True
bot_thread.start()

# Запуск веб-сервера
if __name__ == "__main__":
    print("Starting bot and web server...")
    app.run(host='0.0.0.0', port=8080)

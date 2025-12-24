import telebot
from telebot import types
import sqlite3
import logging
from datetime import datetime
import os

# =========== ДОБАВЛЕНО ДЛЯ RENDER ===========
from flask import Flask
from threading import Thread
# ============================================

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =========== ИЗМЕНЕНО ДЛЯ RENDER ===========
# Получаем токен из переменных окружения
TOKEN = os.getenv('TELEGRAM_TOKEN')
# Если нет переменной окружения, используем ваш токен
if not TOKEN:
    TOKEN = "8218620233:AAExWSft_fYpbtOtjacBMGpMnexpowU6l7s"  # Вставьте сюда токен бота
# ===========================================

ADMIN_ID = 2012242099  # Вставьте ваш ID (можно узнать через @userinfobot)

# Инициализация бота
bot = telebot.TeleBot(TOKEN)

# =========== ДОБАВЛЕНО ДЛЯ RENDER ===========
# Создаем Flask приложение для веб-сервера
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Медицинский бот работает на Render!"

@app.route('/health')
def health():
    return "OK", 200
# ============================================

# Подключение к базе данных
def init_db():
    conn = sqlite3.connect('hospital_bot.db', check_same_thread=False)
    cursor = conn.cursor()

    # Таблица пользователей
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE,
        username TEXT,
        full_name TEXT,
        code_word TEXT UNIQUE,
        role TEXT DEFAULT 'patient',
        registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Таблица вопросов
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        user_name TEXT,
        question TEXT,
        answer TEXT,
        answered_by INTEGER,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        answered_at TIMESTAMP
    )
    ''')

    # Таблица справок
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS certificates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_code TEXT,
        file_id TEXT,
        file_type TEXT,
        description TEXT,
        added_by INTEGER,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_code) REFERENCES users(code_word)
    )
    ''')

    # Таблица обследований
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS examinations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_code TEXT,
        type TEXT,
        date TEXT,
        description TEXT,
        added_by INTEGER,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_code) REFERENCES users(code_word)
    )
    ''')

    # Таблица администраторов/модераторов
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE,
        username TEXT,
        full_name TEXT,
        role TEXT DEFAULT 'moderator',
        added_by INTEGER,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    conn.commit()
    return conn


conn = init_db()


# ===================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====================

def get_user_role(user_id):
    """Получить роль пользователя"""
    cursor = conn.cursor()

    # Проверяем главного админа
    if user_id == ADMIN_ID:
        return 'super_admin'

    # Проверяем в таблице пользователей
    cursor.execute("SELECT role FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if result:
        return result[0]

    # Проверяем в таблице админов
    cursor.execute("SELECT role FROM admins WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if result:
        return result[0]

    return None


def is_admin(user_id):
    """Проверка, является ли пользователь админом или модератором"""
    role = get_user_role(user_id)
    return role in ['super_admin', 'admin', 'moderator']


def is_super_admin(user_id):
    """Проверка, является ли пользователь главным админом"""
    return user_id == ADMIN_ID


def get_user_by_code(code_word):
    """Найти пользователя по кодовому слову"""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE code_word = ?", (code_word,))
    return cursor.fetchone()


def create_main_keyboard(user_id):
    """Создание главной клавиатуры в зависимости от роли"""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)

    if is_admin(user_id):
        # Клавиатура для админов/модераторов
        keyboard.row("👨‍⚕️ Панель управления")
        keyboard.row("❓ Помощь/Вопросы", "📄 Справки")
        keyboard.row("🏥 Обследования", "💬 Ответить на вопросы")
    else:
        # Клавиатура для пациентов
        keyboard.row("❓ Помощь/Вопросы", "📄 Справки")
        keyboard.row("🏥 Обследования")

    return keyboard


def create_admin_keyboard():
    """Клавиатура админ-панели"""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.row("👤 Добавить пациента")
    keyboard.row("🛠️ Добавить модератора", "📋 Добавить справку")
    keyboard.row("📅 Назначить обследование", "📊 Список пациентов")
    keyboard.row("📝 Список вопросов", "🚪 Выйти из админки")
    return keyboard


# ===================== ОСНОВНЫЕ КОМАНДЫ =====================

@bot.message_handler(commands=['start'])
def start_command(message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username or "Без имени"
    full_name = f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip()

    cursor = conn.cursor()

    # Проверяем, зарегистрирован ли пользователь
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()

    if not user and not is_admin(user_id):
        # Если не зарегистрирован и не админ
        bot.send_message(
            message.chat.id,
            "🏥 *Добро пожаловать в Медицинский Бот!*\n\n"
            "Для регистрации отправьте мне кодовое слово, "
            "которое вам предоставил администратор.",
            parse_mode='Markdown',
            reply_markup=types.ReplyKeyboardRemove()
        )
        return

    # Создаем приветственное сообщение
    welcome_text = "🏥 *Добро пожаловать в Медицинский Бот!*\n\n"

    if is_super_admin(user_id):
        welcome_text += "👑 *Вы: Главный администратор*\n"
    elif is_admin(user_id):
        welcome_text += "⚙️ *Вы: Модератор/Администратор*\n"
    else:
        cursor.execute("SELECT full_name FROM users WHERE user_id = ?", (user_id,))
        user_data = cursor.fetchone()
        if user_data:
            welcome_text += f"👤 *Вы: {user_data[0]}*\n"

    welcome_text += "\nВыберите действие из меню ниже:"

    bot.send_message(
        message.chat.id,
        welcome_text,
        parse_mode='Markdown',
        reply_markup=create_main_keyboard(user_id)
    )


@bot.message_handler(commands=['admin'])
def admin_command(message):
    """Вход в админ-панель"""
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "🚫 *У вас нет доступа к админ-панели!*", parse_mode='Markdown')
        return

    bot.send_message(
        message.chat.id,
        "👨‍⚕️ *Панель управления администратора*\n\n"
        "Выберите действие:",
        parse_mode='Markdown',
        reply_markup=create_admin_keyboard()
    )


# ===================== ОБРАБОТЧИКИ КНОПОК =====================

@bot.message_handler(func=lambda message: message.text == "❓ Помощь/Вопросы")
def help_questions(message):
    """Обработчик кнопки Помощь/Вопросы"""
    user_id = message.from_user.id

    # Проверяем, зарегистрирован ли пользователь (для пациентов)
    if not is_admin(user_id):
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        if not cursor.fetchone():
            bot.send_message(message.chat.id, "⚠️ *Вы не зарегистрированы в системе!*", parse_mode='Markdown')
            return

    bot.send_message(
        message.chat.id,
        "❓ *Помощь и вопросы*\n\n"
        "Напишите ваш вопрос, и модератор ответит вам в ближайшее время.\n"
        "Опишите проблему подробно для быстрого решения.",
        parse_mode='Markdown'
    )
    bot.register_next_step_handler(message, process_question)


def process_question(message):
    """Обработка вопроса от пользователя"""
    user_id = message.from_user.id
    username = message.from_user.username or "Без имени"
    full_name = f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip()
    question = message.text

    # Сохраняем вопрос в БД
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO questions (user_id, user_name, question) VALUES (?, ?, ?)",
        (user_id, full_name, question)
    )
    conn.commit()
    question_id = cursor.lastrowid

    # Отправляем уведомление всем админам
    cursor.execute("SELECT user_id FROM admins")
    admins = cursor.fetchall()

    cursor.execute("SELECT user_id FROM users WHERE role IN ('admin', 'moderator')")
    moderators = cursor.fetchall()

    all_admins = [admin[0] for admin in admins] + [mod[0] for mod in moderators] + [ADMIN_ID]

    notification_sent = False
    for admin_id in set(all_admins):
        try:
            bot.send_message(
                admin_id,
                f"🔔 *Новый вопрос от пациента*\n\n"
                f"👤 *Пациент:* {full_name}\n"
                f"🔍 *Username:* @{username}\n"
                f"📝 *Вопрос:* {question}\n\n"
                f"Для ответа нажмите кнопку ниже:",
                parse_mode='Markdown',
                reply_markup=types.InlineKeyboardMarkup().add(
                    types.InlineKeyboardButton("📝 Ответить", callback_data=f"answer_{question_id}")
                )
            )
            notification_sent = True
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление админу {admin_id}: {e}")

    bot.send_message(
        message.chat.id,
        "✅ *Ваш вопрос отправлен!*\n\n"
        "Модератор ответит вам в ближайшее время.",
        parse_mode='Markdown'
    )


@bot.message_handler(func=lambda message: message.text == "📄 Справки")
def certificates_handler(message):
    """Обработчик кнопки Справки"""
    user_id = message.from_user.id

    # Проверяем регистрацию (для пациентов)
    if not is_admin(user_id):
        cursor = conn.cursor()
        cursor.execute("SELECT code_word FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()

        if not user:
            bot.send_message(message.chat.id, "⚠️ *Вы не зарегистрированы в системе!*", parse_mode='Markdown')
            return

        user_code = user[0]
    else:
        # Для админов - запрашиваем код пациента
        bot.send_message(
            message.chat.id,
            "👤 *Просмотр справок пациента*\n\n"
            "Введите кодовое слово пациента:",
            parse_mode='Markdown'
        )
        bot.register_next_step_handler(message, get_certificates_for_patient)
        return

    # Ищем справки для пользователя
    cursor.execute(
        "SELECT * FROM certificates WHERE user_code = ? ORDER BY added_at DESC",
        (user_code,)
    )
    certificates = cursor.fetchall()

    if not certificates:
        bot.send_message(
            message.chat.id,
            "📄 *Справки*\n\n"
            "📭 У вас пока нет доступных справок.",
            parse_mode='Markdown'
        )
        return

    bot.send_message(
        message.chat.id,
        f"📄 *Ваши справки*\n\n"
        f"📊 Найдено справок: {len(certificates)}\n"
        "Отправляю последние справки...",
        parse_mode='Markdown'
    )

    # Отправляем справки (максимум 5 последних)
    for cert in certificates[:5]:
        file_id = cert[2]
        file_type = cert[3]
        description = cert[4]

        try:
            if file_type == 'photo':
                bot.send_photo(message.chat.id, file_id, caption=f"📄 {description}")
            elif file_type == 'document':
                bot.send_document(message.chat.id, file_id, caption=f"📄 {description}")
            else:
                bot.send_message(message.chat.id, f"📄 {description}")
        except Exception as e:
            logger.error(f"Ошибка отправки файла: {e}")
            bot.send_message(message.chat.id, f"❌ Ошибка при загрузке справки: {description}")


def get_certificates_for_patient(message):
    """Получить справки для пациента (для админов)"""
    user_code = message.text.strip()

    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM certificates WHERE user_code = ? ORDER BY added_at DESC",
        (user_code,)
    )
    certificates = cursor.fetchall()

    if not certificates:
        bot.send_message(
            message.chat.id,
            f"📭 *Справки пациента {user_code}*\n\n"
            "У этого пациента нет доступных справок.",
            parse_mode='Markdown'
        )
        return

    bot.send_message(
        message.chat.id,
        f"📄 *Справки пациента {user_code}*\n\n"
        f"📊 Найдено справок: {len(certificates)}",
        parse_mode='Markdown'
    )

    # Отправляем справки
    for cert in certificates[:5]:
        file_id = cert[2]
        file_type = cert[3]
        description = cert[4]

        try:
            if file_type == 'photo':
                bot.send_photo(message.chat.id, file_id, caption=f"📄 {description}")
            elif file_type == 'document':
                bot.send_document(message.chat.id, file_id, caption=f"📄 {description}")
        except Exception as e:
            logger.error(f"Ошибка отправки файла: {e}")
            bot.send_message(message.chat.id, f"❌ Ошибка при загрузке справки: {description}")


@bot.message_handler(func=lambda message: message.text == "🏥 Обследования")
def examinations_handler(message):
    """Обработчик кнопки Обследования"""
    user_id = message.from_user.id

    # Проверяем регистрацию (для пациентов)
    if not is_admin(user_id):
        cursor = conn.cursor()
        cursor.execute("SELECT code_word FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()

        if not user:
            bot.send_message(message.chat.id, "⚠️ *Вы не зарегистрированы в системе!*", parse_mode='Markdown')
            return

        user_code = user[0]
    else:
        # Для админов - запрашиваем код пациента
        bot.send_message(
            message.chat.id,
            "👤 *Просмотр обследований пациента*\n\n"
            "Введите кодовое слово пациента:",
            parse_mode='Markdown'
        )
        bot.register_next_step_handler(message, get_examinations_for_patient)
        return

    # Ищем обследования для пользователя
    cursor.execute(
        "SELECT * FROM examinations WHERE user_code = ? ORDER BY date ASC",
        (user_code,)
    )
    examinations = cursor.fetchall()

    if not examinations:
        bot.send_message(
            message.chat.id,
            "🏥 *Обследования*\n\n"
            "📅 У вас пока нет назначенных обследований.",
            parse_mode='Markdown'
        )
        return

    response = "🏥 *Ваши обследования*\n\n"

    for exam in examinations:
        exam_type = exam[2]
        exam_date = exam[3]
        exam_desc = exam[4]
        response += f"📅 *Дата:* {exam_date}\n"
        response += f"🔬 *Тип:* {exam_type}\n"
        response += f"📝 *Описание:* {exam_desc}\n"
        response += "─" * 30 + "\n"

    bot.send_message(message.chat.id, response, parse_mode='Markdown')


def get_examinations_for_patient(message):
    """Получить обследования для пациента (для админов)"""
    user_code = message.text.strip()

    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM examinations WHERE user_code = ? ORDER BY date ASC",
        (user_code,)
    )
    examinations = cursor.fetchall()

    if not examinations:
        bot.send_message(
            message.chat.id,
            f"📅 *Обследования пациента {user_code}*\n\n"
            "У этого пациента нет назначенных обследований.",
            parse_mode='Markdown'
        )
        return

    response = f"🏥 *Обследования пациента {user_code}*\n\n"

    for exam in examinations:
        exam_type = exam[2]
        exam_date = exam[3]
        exam_desc = exam[4]
        response += f"📅 *Дата:* {exam_date}\n"
        response += f"🔬 *Тип:* {exam_type}\n"
        response += f"📝 *Описание:* {exam_desc}\n"
        response += "─" * 30 + "\n"

    bot.send_message(message.chat.id, response, parse_mode='Markdown')


@bot.message_handler(func=lambda message: message.text == "👨‍⚕️ Панель управления")
def admin_panel(message):
    """Обработчик кнопки Панель управления"""
    admin_command(message)


@bot.message_handler(func=lambda message: message.text == "💬 Ответить на вопросы")
def answer_questions_panel(message):
    """Панель ответа на вопросы"""
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "🚫 *У вас нет доступа!*", parse_mode='Markdown')
        return

    cursor = conn.cursor()
    cursor.execute(
        "SELECT q.id, q.user_name, q.question, q.created_at FROM questions q "
        "WHERE q.status = 'pending' ORDER BY q.created_at DESC LIMIT 10"
    )
    questions = cursor.fetchall()

    if not questions:
        bot.send_message(
            message.chat.id,
            "📝 *Вопросы для ответа*\n\n"
            "✅ На данный момент нет ожидающих вопросов.",
            parse_mode='Markdown'
        )
        return

    response = "📝 *Ожидающие вопросы*\n\n"

    keyboard = types.InlineKeyboardMarkup()

    for q in questions:
        q_id, user_name, question_text, created_at = q
        short_question = (question_text[:50] + '...') if len(question_text) > 50 else question_text
        response += f"🆔 *ID:* {q_id}\n"
        response += f"👤 *От:* {user_name}\n"
        response += f"❓ *Вопрос:* {short_question}\n"
        response += f"📅 *Дата:* {created_at}\n"
        response += "─" * 30 + "\n"

        # Добавляем кнопку для ответа
        keyboard.add(types.InlineKeyboardButton(
            text=f"📝 Ответить на вопрос {q_id}",
            callback_data=f"answer_{q_id}"
        ))

    bot.send_message(message.chat.id, response, parse_mode='Markdown', reply_markup=keyboard)


# ===================== АДМИН-ПАНЕЛЬ =====================

@bot.message_handler(func=lambda message: message.text == "👤 Добавить пациента")
def add_patient_start(message):
    """Начало добавления пациента"""
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "🚫 *У вас нет доступа!*", parse_mode='Markdown')
        return

    bot.send_message(
        message.chat.id,
        "👤 *Добавление пациента*\n\n"
        "Введите данные в формате:\n"
        "`Кодовое_слово Фамилия Имя Отчество`\n\n"
        "*Пример:* `mypass123 Иванов Иван Сергеевич`",
        parse_mode='Markdown'
    )
    bot.register_next_step_handler(message, add_patient_process)


def add_patient_process(message):
    """Обработка данных пациента"""
    try:
        data = message.text.split()
        if len(data) < 3:
            bot.send_message(message.chat.id, "❌ *Неправильный формат!* Нужно: Кодовое_слово Фамилия Имя Отчество",
                             parse_mode='Markdown')
            return

        code_word = data[0]
        full_name = ' '.join(data[1:])

        cursor = conn.cursor()

        # Проверяем, не существует ли уже такое кодовое слово
        cursor.execute("SELECT * FROM users WHERE code_word = ?", (code_word,))
        if cursor.fetchone():
            bot.send_message(message.chat.id, "⚠️ *Такое кодовое слово уже существует!*", parse_mode='Markdown')
            return

        # Добавляем пациента в базу данных (без user_id, он добавится при регистрации)
        cursor.execute(
            "INSERT INTO users (code_word, full_name, role) VALUES (?, ?, 'patient')",
            (code_word, full_name)
        )
        conn.commit()

        bot.send_message(
            message.chat.id,
            "✅ *Пациент добавлен!*\n\n"
            f"👤 *ФИО:* {full_name}\n"
            f"🔑 *Кодовое слово:* `{code_word}`\n\n"
            f"Пациент может зарегистрироваться, отправив боту это кодовое слово.",
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Ошибка добавления пациента: {e}")
        bot.send_message(message.chat.id, "❌ *Ошибка при добавлении пациента!*", parse_mode='Markdown')


@bot.message_handler(func=lambda message: message.text == "🛠️ Добавить модератора")
def add_moderator_start(message):
    """Добавление модератора"""
    if not is_super_admin(message.from_user.id):
        bot.send_message(message.chat.id, "🚫 *Только главный админ может добавлять модераторов!*",
                         parse_mode='Markdown')
        return

    bot.send_message(
        message.chat.id,
        "🛠️ *Добавление модератора*\n\n"
        "Отправьте мне ID пользователя (можно получить через @userinfobot):",
        parse_mode='Markdown'
    )
    bot.register_next_step_handler(message, add_moderator_process_id)


def add_moderator_process_id(message):
    """Получение ID модератора"""
    try:
        user_id = int(message.text.strip())
    except ValueError:
        bot.send_message(message.chat.id, "❌ *ID должен быть числом!*", parse_mode='Markdown')
        return

    bot.temp_moderator_id = user_id
    bot.send_message(
        message.chat.id,
        "📝 Теперь введите ФИО модератора:",
        parse_mode='Markdown'
    )
    bot.register_next_step_handler(message, add_moderator_process_name)


def add_moderator_process_name(message):
    """Добавление модератора с именем"""
    try:
        user_id = bot.temp_moderator_id
        full_name = message.text.strip()

        cursor = conn.cursor()

        # Проверяем, не существует ли уже такой модератор
        cursor.execute("SELECT * FROM admins WHERE user_id = ?", (user_id,))
        if cursor.fetchone():
            bot.send_message(message.chat.id, "⚠️ *Этот пользователь уже является модератором!*", parse_mode='Markdown')
            return

        # Добавляем модератора
        cursor.execute(
            "INSERT INTO admins (user_id, full_name, added_by) VALUES (?, ?, ?)",
            (user_id, full_name, message.from_user.id)
        )
        conn.commit()

        # Пытаемся уведомить нового модератора
        try:
            bot.send_message(
                user_id,
                "🎉 *Поздравляем!*\n\n"
                "Вы были назначены модератором в медицинском боте.\n"
                "Используйте команду /start для начала работы.",
                parse_mode='Markdown'
            )
        except:
            pass  # Не удалось отправить сообщение

        bot.send_message(
            message.chat.id,
            "✅ *Модератор добавлен!*\n\n"
            f"👤 *ФИО:* {full_name}\n"
            f"🆔 *ID:* {user_id}",
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Ошибка добавления модератора: {e}")
        bot.send_message(message.chat.id, "❌ *Ошибка при добавлении модератора!*", parse_mode='Markdown')


@bot.message_handler(func=lambda message: message.text == "📋 Добавить справку")
def add_certificate_start(message):
    """Начало добавления справки"""
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "🚫 *У вас нет доступа!*", parse_mode='Markdown')
        return

    bot.send_message(
        message.chat.id,
        "📋 *Добавление справки*\n\n"
        "Введите кодовое слово пациента:",
        parse_mode='Markdown'
    )
    bot.register_next_step_handler(message, add_certificate_process_code)


def add_certificate_process_code(message):
    """Обработка кодового слова для справки"""
    user_code = message.text.strip()

    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE code_word = ?", (user_code,))
    if not cursor.fetchone():
        bot.send_message(message.chat.id, "⚠️ *Пациент с таким кодовым словом не найден!*", parse_mode='Markdown')
        return

    bot.user_code = user_code
    bot.send_message(
        message.chat.id,
        "✅ *Пациент найден!*\n\n"
        "Теперь отправьте файл справки (фото или документ) и в подписи укажите описание:",
        parse_mode='Markdown'
    )
    bot.register_next_step_handler(message, add_certificate_process_file)


def add_certificate_process_file(message):
    """Обработка файла справки"""
    try:
        user_code = bot.user_code

        if message.content_type == 'photo':
            file_id = message.photo[-1].file_id
            file_type = 'photo'
            description = message.caption or f"Медицинская справка"
        elif message.content_type == 'document':
            file_id = message.document.file_id
            file_type = 'document'
            description = message.caption or f"Медицинская справка"
        else:
            bot.send_message(message.chat.id, "❌ *Пожалуйста, отправьте фото или документ!*", parse_mode='Markdown')
            return

        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO certificates (user_code, file_id, file_type, description, added_by) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_code, file_id, file_type, description, message.from_user.id)
        )
        conn.commit()

        bot.send_message(
            message.chat.id,
            "✅ *Справка добавлена!*\n\n"
            f"📄 Справка успешно добавлена для пациента с кодом: `{user_code}`",
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Ошибка добавления справки: {e}")
        bot.send_message(message.chat.id, "❌ *Ошибка при добавлении справки!*", parse_mode='Markdown')


@bot.message_handler(func=lambda message: message.text == "📅 Назначить обследование")
def add_examination_start(message):
    """Начало добавления обследования"""
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "🚫 *У вас нет доступа!*", parse_mode='Markdown')
        return

    bot.send_message(
        message.chat.id,
        "📅 *Назначение обследования*\n\n"
        "Введите данные в формате:\n"
        "`Кодовое_слово Тип_обследования Дата Описание`\n\n"
        "*Пример:* `mypass123 УЗИ 15.12.2023 Ультразвуковое исследование брюшной полости`",
        parse_mode='Markdown'
    )
    bot.register_next_step_handler(message, add_examination_process)


def add_examination_process(message):
    """Обработка добавления обследования"""
    try:
        data = message.text.split(maxsplit=3)
        if len(data) < 4:
            bot.send_message(message.chat.id, "❌ *Неправильный формат!*", parse_mode='Markdown')
            return

        user_code, exam_type, exam_date, description = data

        # Проверяем существование пациента
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE code_word = ?", (user_code,))
        if not cursor.fetchone():
            bot.send_message(message.chat.id, "⚠️ *Пациент с таким кодовым словом не найден!*", parse_mode='Markdown')
            return

        # Добавляем обследование
        cursor.execute(
            "INSERT INTO examinations (user_code, type, date, description, added_by) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_code, exam_type, exam_date, description, message.from_user.id)
        )
        conn.commit()

        # Пытаемся уведомить пациента
        cursor.execute("SELECT user_id FROM users WHERE code_word = ?", (user_code,))
        patient = cursor.fetchone()
        if patient and patient[0]:
            try:
                bot.send_message(
                    patient[0],
                    "🔔 *Вам назначено новое обследование!*\n\n"
                    f"🏥 *Тип:* {exam_type}\n"
                    f"📅 *Дата:* {exam_date}\n"
                    f"📝 *Описание:* {description}\n\n"
                    "Проверьте раздел 'Обследования' для подробностей.",
                    parse_mode='Markdown'
                )
            except:
                pass

        bot.send_message(
            message.chat.id,
            "✅ *Обследование назначено!*\n\n"
            f"👤 *Пациент:* `{user_code}`\n"
            f"🏥 *Тип:* {exam_type}\n"
            f"📅 *Дата:* {exam_date}\n"
            f"📝 *Описание:* {description}",
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Ошибка назначения обследования: {e}")
        bot.send_message(message.chat.id, "❌ *Ошибка при назначении обследования!*", parse_mode='Markdown')


@bot.message_handler(func=lambda message: message.text == "📊 Список пациентов")
def list_patients(message):
    """Показать список пациентов"""
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "🚫 *У вас нет доступа!*", parse_mode='Markdown')
        return

    cursor = conn.cursor()
    cursor.execute(
        "SELECT full_name, code_word, registered_at, user_id FROM users WHERE role = 'patient' ORDER BY full_name"
    )
    patients = cursor.fetchall()

    if not patients:
        bot.send_message(
            message.chat.id,
            "👤 *Список пациентов*\n\n"
            "📭 Пациентов пока нет.",
            parse_mode='Markdown'
        )
        return

    response = "👤 *Список пациентов*\n\n"

    for patient in patients:
        full_name, code_word, reg_date, user_id = patient
        status = "✅ Зарегистрирован" if user_id else "⏳ Ожидает регистрации"
        response += f"👤 *ФИО:* {full_name}\n"
        response += f"🔑 *Код:* `{code_word}`\n"
        response += f"📊 *Статус:* {status}\n"
        if user_id:
            response += f"🆔 *ID:* {user_id}\n"
        response += "─" * 30 + "\n"

    bot.send_message(message.chat.id, response, parse_mode='Markdown')


@bot.message_handler(func=lambda message: message.text == "📝 Список вопросов")
def list_all_questions(message):
    """Показать все вопросы"""
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "🚫 *У вас нет доступа!*", parse_mode='Markdown')
        return

    cursor = conn.cursor()
    cursor.execute(
        "SELECT q.id, q.user_name, q.question, q.status, q.created_at FROM questions q "
        "ORDER BY q.created_at DESC LIMIT 20"
    )
    questions = cursor.fetchall()

    if not questions:
        bot.send_message(
            message.chat.id,
            "📝 *Все вопросы*\n\n"
            "📭 Вопросов пока нет.",
            parse_mode='Markdown'
        )
        return

    response = "📝 *Последние вопросы*\n\n"

    for q in questions:
        q_id, user_name, question_text, status, created_at = q
        status_icon = "✅" if status == 'answered' else "⏳"
        short_question = (question_text[:30] + '...') if len(question_text) > 30 else question_text

        response += f"{status_icon} *ID:* {q_id}\n"
        response += f"👤 *От:* {user_name}\n"
        response += f"❓ *Вопрос:* {short_question}\n"
        response += f"📅 *Дата:* {created_at}\n"
        response += "─" * 20 + "\n"

    bot.send_message(message.chat.id, response, parse_mode='Markdown')


@bot.message_handler(func=lambda message: message.text == "🚪 Выйти из админки")
def exit_admin(message):
    """Выход из админ-панели"""
    bot.send_message(
        message.chat.id,
        "🏥 Вы вышли из панели администратора.",
        parse_mode='Markdown',
        reply_markup=create_main_keyboard(message.from_user.id)
    )


# ===================== ОБРАБОТЧИКИ CALLBACK =====================

@bot.callback_query_handler(func=lambda call: call.data.startswith('answer_'))
def answer_question_callback(call):
    """Обработка нажатия на кнопку ответа"""
    try:
        question_id = int(call.data.split('_')[1])

        cursor = conn.cursor()
        cursor.execute(
            "SELECT q.user_id, q.user_name, q.question FROM questions q WHERE q.id = ?",
            (question_id,)
        )
        question = cursor.fetchone()

        if not question:
            bot.answer_callback_query(call.id, "❌ Вопрос не найден!")
            return

        user_id, user_name, question_text = question

        # Сохраняем данные для следующего шага
        bot.question_to_answer = question_id
        bot.question_user_id = user_id
        bot.question_text = question_text

        bot.send_message(
            call.message.chat.id,
            f"📝 *Ответ на вопрос #{question_id}*\n\n"
            f"👤 *От:* {user_name}\n"
            f"❓ *Вопрос:* {question_text}\n\n"
            f"Напишите ответ:",
            parse_mode='Markdown'
        )

        bot.answer_callback_query(call.id, "✍️ Напишите ответ...")

    except Exception as e:
        logger.error(f"Ошибка в callback: {e}")
        bot.answer_callback_query(call.id, "❌ Ошибка!")


@bot.message_handler(func=lambda message: hasattr(bot, 'question_to_answer') and bot.question_to_answer)
def process_answer(message):
    """Обработка ответа на вопрос"""
    try:
        question_id = bot.question_to_answer
        user_id = bot.question_user_id
        question_text = bot.question_text
        answer = message.text

        cursor = conn.cursor()

        # Обновляем вопрос
        cursor.execute(
            "UPDATE questions SET answer = ?, answered_by = ?, status = 'answered', answered_at = CURRENT_TIMESTAMP "
            "WHERE id = ?",
            (answer, message.from_user.id, question_id)
        )
        conn.commit()

        # Отправляем ответ пациенту
        try:
            bot.send_message(
                user_id,
                f"💬 *Ответ на ваш вопрос*\n\n"
                f"❓ *Ваш вопрос:* {question_text}\n\n"
                f"📝 *Ответ модератора:* {answer}\n\n"
                f"Спасибо за обращение!",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Не удалось отправить ответ пациенту: {e}")

        # Очищаем временные данные
        del bot.question_to_answer
        del bot.question_user_id
        del bot.question_text

        bot.send_message(
            message.chat.id,
            "✅ *Ответ отправлен!*\n\n"
            f"Ответ успешно отправлен пациенту.",
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Ошибка обработки ответа: {e}")
        bot.send_message(message.chat.id, "❌ *Ошибка при отправке ответа!*", parse_mode='Markdown')


# ===================== РЕГИСТРАЦИЯ ПО КОДОВОМУ СЛОВУ =====================

@bot.message_handler(func=lambda message: len(message.text) > 0 and
                                          message.text not in ["❓ Помощь/Вопросы", "📄 Справки", "🏥 Обследования",
                                                               "👨‍⚕️ Панель управления", "💬 Ответить на вопросы",
                                                               "👤 Добавить пациента", "🛠️ Добавить модератора",
                                                               "📋 Добавить справку", "📅 Назначить обследование",
                                                               "📊 Список пациентов", "📝 Список вопросов",
                                                               "🚪 Выйти из админки"])
def handle_text_message(message):
    """Обработка текстовых сообщений (для регистрации и других команд)"""
    user_id = message.from_user.id
    username = message.from_user.username or "Без имени"
    full_name = f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip()
    text = message.text.strip()

    # Проверяем, не является ли пользователь уже зарегистрированным
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    if cursor.fetchone():
        # Пользователь уже зарегистрирован
        return

    # Проверяем, не является ли пользователь админом
    if is_admin(user_id):
        return

    # Проверяем, является ли сообщение кодовым словом
    cursor.execute("SELECT * FROM users WHERE code_word = ?", (text,))
    patient = cursor.fetchone()

    if patient:
        # Регистрируем пользователя (обновляем user_id и username)
        cursor.execute(
            "UPDATE users SET user_id = ?, username = ? WHERE code_word = ?",
            (user_id, username, text)
        )
        conn.commit()

        # Получаем ФИО пациента
        cursor.execute("SELECT full_name FROM users WHERE user_id = ?", (user_id,))
        user_data = cursor.fetchone()
        patient_name = user_data[0] if user_data else full_name

        bot.send_message(
            message.chat.id,
            f"🎉 *Регистрация успешна!*\n\n"
            f"Добро пожаловать, {patient_name}!\n"
            f"Теперь вам доступны все функции бота.",
            parse_mode='Markdown',
            reply_markup=create_main_keyboard(user_id)
        )

        # Уведомляем админов о новой регистрации
        cursor.execute("SELECT user_id FROM admins")
        admins = cursor.fetchall()
        for admin_id in [admin[0] for admin in admins] + [ADMIN_ID]:
            try:
                bot.send_message(
                    admin_id,
                    f"👤 *Новая регистрация пациента*\n\n"
                    f"✅ *Пациент:* {patient_name}\n"
                    f"🔑 *Код:* `{text}`\n"
                    f"🆔 *ID:* {user_id}\n"
                    f"👤 *Username:* @{username}",
                    parse_mode='Markdown'
                )
            except:
                pass
    else:
        bot.send_message(
            message.chat.id,
            "❌ *Неверное кодовое слово!*\n\n"
            "Проверьте правильность ввода или обратитесь к администратору.",
            parse_mode='Markdown'
        )


# =========== ДОБАВЛЕНО ДЛЯ RENDER ===========
def run_bot():
    """Запуск бота в отдельном потоке"""
    print("=" * 50)
    print("🏥 МЕДИЦИНСКИЙ БОТ ЗАПУЩЕН")
    print("=" * 50)
    print(f"🤖 Бот: @{bot.get_me().username}")
    print(f"👑 Главный админ: {ADMIN_ID}")
    print(f"💾 База данных: hospital_bot.db")
    print("=" * 50)
    print("Ожидание сообщений...")

    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=5)
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")
    finally:
        conn.close()


# Запуск бота в отдельном потоке
bot_thread = Thread(target=run_bot, daemon=True)
bot_thread.start()


if __name__ == "__main__":
    # Запуск Flask сервера
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
# ============================================

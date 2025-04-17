from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
import os
import json
import secrets
import datetime
import time
import io
from werkzeug.utils import secure_filename
from functools import wraps
import telegram
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import threading
import logging
import asyncio
import signal
import sys
import aiohttp
import aiofiles
import os.path
import httpx
from telegram.ext import AIORateLimiter
import requests
from flask_wtf.csrf import CSRFProtect
import uuid

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация Flask
app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB макс. размер файла
app.config['WTF_CSRF_ENABLED'] = False  # Отключаем CSRF защиту полностью

# Инициализация CSRF-защиты (не будет применяться из-за отключенного WTF_CSRF_ENABLED)
csrf = CSRFProtect(app)

# Создаем папку uploads, если её нет
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Создаем папку для аватаров
AVATAR_FOLDER = 'static/avatars'
os.makedirs(AVATAR_FOLDER, exist_ok=True)

# Создаем папку для файлов пользователей
FILES_USERS_DIR = 'files_users'
os.makedirs(FILES_USERS_DIR, exist_ok=True)

# Путь к файлам с данными
DATA_DIR = 'data'
os.makedirs(DATA_DIR, exist_ok=True)

USERS_FILE = os.path.join(DATA_DIR, 'users.json')
MESSAGES_FILE = os.path.join(DATA_DIR, 'messages.json')
SETTINGS_FILE = os.path.join(DATA_DIR, 'settings.json')
ADMINS_FILE = os.path.join(DATA_DIR, 'admins.json')
BUTTONS_FILE = os.path.join(DATA_DIR, 'buttons.json')

# Инициализация файлов данных, если они не существуют
def init_data_files():
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f)
    
    if not os.path.exists(MESSAGES_FILE):
        with open(MESSAGES_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f)
    
    if not os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'bot_token': '',
                'bot_name': 'Telegram Bot',
                'welcome_message': 'Привет! Я ваш бот.',
                'auto_reply': False,
                'admin_id': ''
            }, f)
    
    if not os.path.exists(ADMINS_FILE):
        with open(ADMINS_FILE, 'w', encoding='utf-8') as f:
            json.dump([
                {
                    'username': 'admin',
                    'password': 'admin',  # В реальном проекте используйте хеширование паролей
                    'role': 'admin'
                }
            ], f)
            
    if not os.path.exists(BUTTONS_FILE):
        with open(BUTTONS_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f)

# Инициализируем файлы при запуске
init_data_files()

# Экземпляр бота Telegram
bot = None
application = None

# Функция для загрузки настроек
def load_settings():
    with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

# Функция для загрузки пользователей
def load_users():
    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

# Функция для загрузки сообщений
def load_messages():
    with open(MESSAGES_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

# Функция для загрузки администраторов
def load_admins():
    with open(ADMINS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

# Функция для загрузки кнопок
def load_buttons():
    with open(BUTTONS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

# Функция для сохранения пользователей
def save_users(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

# Функция для сохранения сообщений
def save_messages(messages):
    with open(MESSAGES_FILE, 'w', encoding='utf-8') as f:
        json.dump(messages, f, ensure_ascii=False, indent=4)

# Функция для сохранения настроек
def save_settings(settings):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=4)

# Функция для сохранения кнопок
def save_buttons(buttons):
    with open(BUTTONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(buttons, f, ensure_ascii=False, indent=4)

# Добавляем settings в контекст всех шаблонов
@app.context_processor
def inject_settings():
    return {'settings': load_settings()}

# Инициализация бота
def init_bot():
    global bot, application
    settings = load_settings()
    if settings['bot_token']:
        try:
            # Останавливаем предыдущий экземпляр бота, если он существует
            if application:
                try:
                    logger.info("Останавливаем предыдущий экземпляр бота")
                    # Создаем новый event loop для остановки бота
                    stop_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(stop_loop)
                    try:
                        # Останавливаем бот через новый event loop
                        stop_loop.run_until_complete(application.stop())
                        stop_loop.close()
                    except Exception as e:
                        logger.error(f"Ошибка при остановке бота: {e}")
                    application = None
                    bot = None
                    # Даем время на полное освобождение ресурсов
                    time.sleep(3)
                except Exception as e:
                    logger.error(f"Ошибка при остановке бота: {e}")
                    application = None
                    bot = None
                    # Даем время на полное освобождение ресурсов
                    time.sleep(3)

            logger.info("Инициализация нового экземпляра бота")
            
            # Создаем приложение с базовыми настройками
            application = (
                Application.builder()
                .token(settings['bot_token'])
                .connection_pool_size(200)
                .connect_timeout(60.0)
                .read_timeout(60.0)
                .write_timeout(60.0)
                .pool_timeout(60.0)
                .build()
            )
            
            # Создаем нового бота
            bot = application.bot
            
            # Добавляем обработчики
            application.add_handler(CommandHandler("start", start_command))
            application.add_handler(CommandHandler("help", help_command))
            application.add_handler(CommandHandler("buttons", buttons_command))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
            
            # Запускаем бота в отдельном потоке
            bot_thread = threading.Thread(target=run_bot, daemon=True)
            bot_thread.start()
            
            # Даем время на инициализацию
            time.sleep(5)
            
            # Проверяем, что бот работает
            try:
                # Проверка через HTTP API
                api_url = f'https://api.telegram.org/bot{bot.token}/getMe'
                response = requests.get(api_url, timeout=10)
                if response.status_code != 200 or not response.json().get('ok'):
                    logger.error(f"Ошибка при проверке работы бота: {response.json().get('description')}")
                    return False
            except Exception as e:
                logger.error(f"Ошибка при проверке работы бота: {e}")
                return False
                
            # Считаем бот успешно запущенным, если нет ошибок
            logger.info("Бот инициализирован без ошибок")
            return True
                
        except Exception as e:
            logger.error(f"Ошибка при инициализации бота: {e}")
            if application:
                try:
                    stop_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(stop_loop)
                    stop_loop.run_until_complete(application.stop())
                    stop_loop.close()
                except:
                    pass
                application = None
                bot = None
            return False
    return False

def run_bot():
    try:
        # Создаем новый event loop для бота
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Настраиваем параметры запуска
        application._concurrent_updates = True
        application._concurrent_updates_limit = 50
        
        # Запускаем с настроенными параметрами
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"]
        )
    except Exception as e:
        logger.error(f"Ошибка в работе бота: {e}")
    finally:
        try:
            # Закрываем event loop
            loop.close()
        except:
            pass

# Обработчики команд для бота
async def download_avatar(user_id, file_id):
    try:
        logger.info(f"Начинаем скачивание аватара для пользователя {user_id}")
        logger.info(f"Получаем информацию о файле {file_id}")
        
        file_info = await bot.get_file(file_id)
        file_path = file_info.file_path
        logger.info(f"Получена информация о файле: {file_path}")
        
        # Проверяем, является ли file_path полным URL
        if file_path.startswith('http'):
            file_url = file_path
        else:
            file_url = f"https://api.telegram.org/file/bot{bot.token}/{file_path}"
        
        file_ext = os.path.splitext(file_path)[1] or '.jpg'
        avatar_path = os.path.join(AVATAR_FOLDER, f"{user_id}{file_ext}")
        
        logger.info(f"Скачиваем файл с URL: {file_url}")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(file_url) as response:
                if response.status == 200:
                    logger.info(f"Файл успешно скачан, сохраняем в {avatar_path}")
                    async with aiofiles.open(avatar_path, 'wb') as f:
                        await f.write(await response.read())
                    relative_path = f"avatars/{os.path.basename(avatar_path)}"
                    logger.info(f"Аватар успешно сохранен: {relative_path}")
                    return relative_path
                else:
                    logger.error(f"Ошибка при скачивании файла. Статус: {response.status}, URL: {file_url}")
    except Exception as e:
        logger.error(f"Ошибка при скачивании аватара: {str(e)}", exc_info=True)
    return None

async def start_command(update, context):
    settings = load_settings()
    users = load_users()
    buttons = load_buttons()
    user_id = update.effective_user.id
    username = update.effective_user.username or "Без имени"
    full_name = update.effective_user.full_name or ""
    
    # Скачиваем аватар пользователя
    avatar_path = None
    try:
        logger.info(f"Получаем фотографии профиля для пользователя {user_id}")
        photos = await update.effective_user.get_profile_photos()
        logger.info(f"Получено фотографий: {len(photos.photos) if photos.photos else 0}")
        
        if photos.photos and len(photos.photos) > 0 and len(photos.photos[0]) > 0:
            photo = photos.photos[0][0]  # Берем самую последнюю фотографию
            logger.info(f"Найдена фотография профиля: {photo.file_id}")
            avatar_path = await download_avatar(user_id, photo.file_id)
            logger.info(f"Результат скачивания аватара: {avatar_path}")
    except Exception as e:
        logger.error(f"Ошибка при получении фото профиля: {str(e)}", exc_info=True)
    
    # Проверяем, есть ли пользователь в базе
    user_exists = False
    for user in users:
        if user['id'] == user_id:
            user_exists = True
            user['is_active'] = True
            user['last_activity'] = datetime.datetime.now().isoformat()
            user['username'] = username
            user['full_name'] = full_name
            if avatar_path:
                user['avatar'] = avatar_path
                logger.info(f"Обновлен аватар для пользователя {user_id}: {avatar_path}")
            break
    
    # Если пользователя нет, добавляем его
    if not user_exists:
        new_user = {
            'id': user_id,
            'username': username,
            'full_name': full_name,
            'avatar': avatar_path,
            'created_at': datetime.datetime.now().isoformat(),
            'is_active': True,
            'last_activity': datetime.datetime.now().isoformat(),
            'message_count': 0
        }
        users.append(new_user)
        logger.info(f"Добавлен новый пользователь: {new_user}")
    
    save_users(users)
    
    # Создаем клавиатуру с кнопками
    keyboard = []
    if buttons:
        keyboard_buttons = []
        for button in buttons:
            keyboard_buttons.append(telegram.KeyboardButton(button['text']))
            if len(keyboard_buttons) == 2:  # По 2 кнопки в ряд
                keyboard.append(keyboard_buttons)
                keyboard_buttons = []
        if keyboard_buttons:  # Добавляем оставшиеся кнопки
            keyboard.append(keyboard_buttons)
    
    reply_markup = telegram.ReplyKeyboardMarkup(keyboard, resize_keyboard=True) if keyboard else None
    await update.message.reply_text(settings['welcome_message'], reply_markup=reply_markup)

async def help_command(update, context):
    await update.message.reply_text("Список доступных команд:\n/start - Начать работу с ботом\n/help - Показать список команд\n/buttons - Показать кнопки")

async def buttons_command(update, context):
    if not update.message or not update.effective_chat:
        return
        
    buttons = load_buttons()
    
    # Создаем клавиатуру с кнопками
    keyboard = []
    if buttons:
        keyboard_buttons = []
        for button in buttons:
            keyboard_buttons.append(telegram.KeyboardButton(button['text']))
            if len(keyboard_buttons) == 2:  # По 2 кнопки в ряд
                keyboard.append(keyboard_buttons)
                keyboard_buttons = []
        if keyboard_buttons:  # Добавляем оставшиеся кнопки
            keyboard.append(keyboard_buttons)
        
        reply_markup = telegram.ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Вот доступные кнопки:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Кнопки еще не настроены. Администратор может добавить их через панель управления.")

# Функция для экранирования текста для MARKDOWN_V2
def escape_markdown_v2(text):
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    escaped_text = text
    for char in special_chars:
        escaped_text = escaped_text.replace(char, f"\\{char}")
    return escaped_text

async def message_handler(update, context):
    user_id = update.effective_user.id
    users = load_users()
    messages = load_messages()
    settings = load_settings()
    buttons = load_buttons()
    
    # Обновляем статус пользователя
    username = None
    for user in users:
        if user['id'] == user_id:
            user['is_active'] = True
            user['last_activity'] = datetime.datetime.now().isoformat()
            user['message_count'] = user.get('message_count', 0) + 1
            username = user.get('username', 'Неизвестный')
            break
    
    # Проверяем, является ли сообщение нажатием на кнопку
    is_button_press = False
    button_info = None
    
    for button in buttons:
        if update.message.text == button['text']:
            is_button_press = True
            button_info = button
            break
    
    # Сохраняем сообщение с доп. информацией о кнопке
    message_data = {
        'id': len(messages) + 1,
        'user_id': user_id,
        'username': username,
        'text': update.message.text,
        'timestamp': datetime.datetime.now().isoformat(),
        'is_incoming': True,
        'is_button_press': is_button_press
    }
    
    # Если это нажатие на кнопку, добавляем информацию о кнопке
    if is_button_press and button_info:
        message_data['button_id'] = button_info['id']
        message_data['button_text'] = button_info['text']
        message_data['button_response'] = button_info['response']
        
        # Отправляем ответ на нажатие кнопки
        response_text = button_info['response']
        
        # Экранируем основной текст для MARKDOWN_V2
        escaped_response = escape_markdown_v2(response_text)
        
        # Добавляем ссылку, если она есть
        if button_info.get('url'):
            url = button_info.get('url')
            url_text = button_info.get('url_text') or url
            
            # Экранируем специальные символы для MARKDOWN_V2
            escaped_url_text = escape_markdown_v2(url_text)
            
            # Для URL нужно экранировать только некоторые символы
            escaped_url = url
            for char in [')']:  # Только закрывающая скобка требует экранирования в URL
                escaped_url = escaped_url.replace(char, f"\\{char}")
            
            # Собираем ссылку в формате MARKDOWN_V2
            escaped_response += f"\n\n[{escaped_url_text}]({escaped_url})"
        
        # Если у кнопки есть изображение, отправляем его
        if button_info.get('image_path'):
            try:
                # Используем корректный путь к файлу с нормализацией слэшей
                image_path = os.path.join('static', button_info['image_path'].replace('/', os.path.sep))
                if os.path.exists(image_path):
                    # Отправляем изображение с подписью (текстом ответа)
                    await update.message.reply_photo(
                        photo=open(image_path, 'rb'),
                        caption=escaped_response,
                        parse_mode=telegram.constants.ParseMode.MARKDOWN_V2
                    )
                else:
                    logger.error(f"Изображение не найдено по пути: {image_path}")
                    # Если файл не существует, отправляем только текст
                    await update.message.reply_text(
                        escaped_response,
                        parse_mode=telegram.constants.ParseMode.MARKDOWN_V2
                    )
            except Exception as e:
                logger.error(f"Ошибка при отправке изображения: {e}")
                # В случае ошибки отправляем только текст
                await update.message.reply_text(
                    escaped_response,
                    parse_mode=telegram.constants.ParseMode.MARKDOWN_V2
                )
        else:
            # Если изображения нет, отправляем только текст
            await update.message.reply_text(
                escaped_response,
                parse_mode=telegram.constants.ParseMode.MARKDOWN_V2
            )
    else:
        # Автоматический ответ, если включено
        if settings['auto_reply']:
            reply_text = f"Получено сообщение: {update.message.text}"
            await update.message.reply_text(reply_text)
            
            # Сохраняем ответ бота
            messages.append({
                'id': len(messages) + 1,
                'user_id': user_id,
                'username': username,
                'text': reply_text,
                'timestamp': datetime.datetime.now().isoformat(),
                'is_incoming': False,
                'is_button_press': False
            })
    
    # Добавляем сообщение к списку
    messages.append(message_data)
    
    save_users(users)
    save_messages(messages)

# Декоратор для проверки авторизации
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session or not session['logged_in']:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Маршруты Flask
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        admins = load_admins()
        for admin in admins:
            if admin['username'] == username and admin['password'] == password:
                session['logged_in'] = True
                session['username'] = username
                return redirect(url_for('dashboard'))
        
        return render_template('login.html', error='Неверное имя пользователя или пароль')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def admin():
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
@login_required
def dashboard():
    users = load_users()
    messages = load_messages()
    
    # Получаем данные для статистики
    today = datetime.datetime.now().date()
    
    # Подсчет новых пользователей за 24 часа
    new_users_24h = 0
    for user in users:
        created_at = datetime.datetime.fromisoformat(user['created_at']).date()
        if created_at == today:
            new_users_24h += 1
    
    # Подсчет активных пользователей за 24 часа
    active_users_24h = 0
    for user in users:
        if 'last_activity' in user:
            last_activity = datetime.datetime.fromisoformat(user['last_activity']).date()
            if last_activity == today:
                active_users_24h += 1
    
    # Подсчет сообщений за 24 часа
    messages_24h = 0
    for msg in messages:
        msg_date = datetime.datetime.fromisoformat(msg['timestamp']).date()
        if msg_date == today:
            messages_24h += 1
    
    # Данные для графиков
    last_7_days = [(datetime.datetime.now() - datetime.timedelta(days=i)).date() for i in range(6, -1, -1)]
    activity_labels = [day.strftime('%d.%m') for day in last_7_days]
    new_users_labels = activity_labels.copy()
    
    # Активность пользователей за последние 7 дней
    activity_data = []
    for day in last_7_days:
        active_count = 0
        for user in users:
            if 'last_activity' in user:
                last_activity = datetime.datetime.fromisoformat(user['last_activity']).date()
                if last_activity == day:
                    active_count += 1
        activity_data.append(active_count)
    
    # Новые пользователи за последние 7 дней
    new_users_data = []
    for day in last_7_days:
        new_count = 0
        for user in users:
            created_at = datetime.datetime.fromisoformat(user['created_at']).date()
            if created_at == day:
                new_count += 1
        new_users_data.append(new_count)
    
    # Создаем словарь со статистикой
    stats = {
        'total_users': len(users),
        'active_users': active_users_24h,
        'new_users_24h': new_users_24h,
        'messages_24h': messages_24h
    }
    
    return render_template('dashboard.html',
                          stats=stats,
                          activity_labels=activity_labels,
                          activity_data=activity_data,
                          new_users_labels=new_users_labels,
                          new_users_data=new_users_data,
                          username=session.get('username', 'admin'),
                          active_page="dashboard")

@app.route('/users')
@login_required
def users_page():
    users = load_users()
    settings = load_settings()
    
    return render_template('users.html', 
                          users=users,
                          bot_name=settings['bot_name'],
                          username=session.get('username', 'admin'),
                          active_page="users")

@app.route('/message-history')
@login_required
def messages_page():
    messages = load_messages()
    settings = load_settings()
    users = load_users()
    
    # Создаем словарь с информацией о пользователях для быстрого доступа
    users_info = {}
    for user in users:
        users_info[user['id']] = {
            'username': user.get('username', 'Без имени'),
            'full_name': user.get('full_name', ''),
            'avatar': user.get('avatar', '')
        }
    
    # Обогащаем сообщения информацией о пользователях
    for message in messages:
        user_id = message.get('user_id')
        if user_id in users_info and 'username' not in message:
            message['username'] = users_info[user_id]['username']
    
    # Сортируем сообщения по времени (новые сверху)
    messages.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    
    return render_template('messages.html', 
                          messages=messages,
                          users_info=users_info,
                          bot_name=settings['bot_name'],
                          username=session.get('username', 'admin'),
                          active_page="messages")

@app.route('/bot-settings')
@login_required
def settings_page():
    settings = load_settings()
    
    # Проверяем статус бота
    bot_status = {
        'is_active': False,
        'username': None,
        'error': None
    }
    
    if bot:
        try:
            # Проверяем статус бота через HTTP API
            response = requests.get(
                f'https://api.telegram.org/bot{bot.token}/getMe',
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    bot_status['is_active'] = True
                    bot_status['username'] = data.get('result', {}).get('username')
                else:
                    bot_status['error'] = data.get('description', 'Неизвестная ошибка API')
            else:
                bot_status['error'] = f"Код ответа API: {response.status_code}"
        except Exception as e:
            bot_status['error'] = str(e)
    
    return render_template('settings.html', 
                          settings=settings,
                          bot_name=settings['bot_name'],
                          username=session.get('username', 'admin'),
                          active_page="settings",
                          bot_status=bot_status)

@app.route('/database-management')
@login_required
def database_page():
    settings = load_settings()
    
    return render_template('database.html', 
                          settings=settings,
                          bot_name=settings['bot_name'],
                          username=session.get('username', 'admin'),
                          active_page="database")

@app.route('/send_message', methods=['POST'])
@login_required
def send_message():
    global bot
    
    user_id = int(request.form['user_id'])
    message_text = request.form['message']
    attachment = request.files.get('attachment')
    
    # Проверяем инициализацию бота
    if not bot:
        flash('Ошибка: Бот не инициализирован. Проверьте настройки бота.', 'danger')
        return redirect(url_for('admin'))
    
    users = load_users()
    messages = load_messages()
    
    # Проверяем, существует ли пользователь
    user = None
    for u in users:
        if u['id'] == user_id:
            user = u
            break
            
    if not user:
        flash('Пользователь не найден', 'danger')
        return redirect(url_for('admin'))
    
    try:
        # Отправляем сообщение через HTTP API напрямую
        # Базовый URL API
        api_url = f'https://api.telegram.org/bot{bot.token}'
        
        # Отправляем сообщение
        if attachment and attachment.filename:
            # Создаем папку для файлов пользователя
            user_folder = os.path.join(FILES_USERS_DIR, f"{user.get('username', str(user_id))}")
            os.makedirs(user_folder, exist_ok=True)
            
            filename = secure_filename(attachment.filename)
            # Добавляем временную метку к имени файла
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_')
            filename = timestamp + filename
            file_path = os.path.join(user_folder, filename)
            
            # Сохраняем файл
            attachment.save(file_path)
            
            try:
                # Определяем тип файла и метод для отправки
                method = None
                file_param = None
                
                if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                    method = 'sendPhoto'
                    file_param = 'photo'
                elif filename.lower().endswith(('.mp4', '.avi', '.mov')):
                    method = 'sendVideo'
                    file_param = 'video'
                elif filename.lower().endswith(('.mp3', '.wav', '.ogg')):
                    method = 'sendAudio'
                    file_param = 'audio'
                else:
                    method = 'sendDocument'
                    file_param = 'document'
                
                # Подготавливаем данные для запроса
                with open(file_path, 'rb') as file_to_send:
                    files = {file_param: file_to_send}
                    data = {
                        'chat_id': user_id,
                        'caption': message_text if message_text else None
                    }
                    
                    # Отправляем запрос
                    response = requests.post(f'{api_url}/{method}', files=files, data=data, timeout=60)
                
                # Проверяем ответ
                response_json = response.json()
                if not response_json.get('ok'):
                    raise Exception(f"Ошибка API: {response_json.get('description')}")
                
                # Сохраняем информацию о файле
                file_info = {
                    'filename': filename,
                    'path': file_path,
                    'type': os.path.splitext(filename)[1],
                    'size': os.path.getsize(file_path)
                }
            except Exception as e:
                logger.error(f"Ошибка при отправке файла: {e}")
                # В случае ошибки при отправке, удаляем сохраненный файл
                try:
                    os.remove(file_path)
                except:
                    pass
                raise Exception(f"Ошибка при отправке файла: {str(e)}")
        else:
            # Отправляем только текстовое сообщение
            response = requests.post(
                f'{api_url}/sendMessage',
                json={'chat_id': user_id, 'text': message_text},
                timeout=30
            )
            
            # Проверяем ответ
            response_json = response.json()
            if not response_json.get('ok'):
                raise Exception(f"Ошибка API: {response_json.get('description')}")
                
            file_info = None
        
        # Сохраняем сообщение в базу
        message_data = {
            'id': len(messages) + 1,
            'user_id': user_id,
            'username': user.get('username', 'Без имени'),
            'text': message_text,
            'timestamp': datetime.datetime.now().isoformat(),
            'is_incoming': False,
            'is_button_press': False,
            'admin_sent': True,
            'admin_username': session.get('username', 'admin')
        }
        
        if file_info:
            message_data['attachment'] = file_info
            
        messages.append(message_data)
        save_messages(messages)
        
        flash('Сообщение успешно отправлено', 'success')
            
    except Exception as e:
        error_msg = str(e)
        if "bot" in error_msg.lower() and "none" in error_msg.lower():
            error_msg = "Ошибка: Бот не инициализирован или остановлен. Проверьте настройки бота."
        elif "timeout" in error_msg.lower():
            error_msg = "Ошибка: Превышено время ожидания ответа от сервера Telegram. Попробуйте отправить файл меньшего размера или повторить попытку позже."
        logger.error(f"Ошибка при отправке сообщения: {e}", exc_info=True)
        flash(f'Ошибка при отправке сообщения: {error_msg}', 'danger')
    
    return redirect(url_for('admin'))

@app.route('/send_broadcast', methods=['POST'])
@login_required
def send_broadcast():
    message_text = request.form['message']
    attachment = request.files.get('attachment')
    
    users = load_users()
    messages = load_messages()
    
    successful_count = 0
    failed_count = 0
    
    # Проверяем, что бот инициализирован
    if not bot or not bot.token:
        flash('Ошибка: Бот не инициализирован. Проверьте настройки бота.', 'danger')
        return redirect(url_for('admin'))
    
    api_url = f'https://api.telegram.org/bot{bot.token}'
    
    if attachment and attachment.filename:
        filename = secure_filename(attachment.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        attachment.save(file_path)
        
        try:
            for user in users:
                try:
                    user_id = user['id']
                    username = user.get('username', 'Без имени')
                    
                    # Определяем тип файла и метод для отправки
                    method = None
                    file_param = None
                    
                    if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                        method = 'sendPhoto'
                        file_param = 'photo'
                    elif filename.lower().endswith(('.mp4', '.avi', '.mov')):
                        method = 'sendVideo'
                        file_param = 'video'
                    elif filename.lower().endswith(('.mp3', '.wav', '.ogg')):
                        method = 'sendAudio'
                        file_param = 'audio'
                    else:
                        method = 'sendDocument'
                        file_param = 'document'
                    
                    # Отправляем файл через HTTP API
                    with open(file_path, 'rb') as file_to_send:
                        files = {file_param: file_to_send}
                        data = {
                            'chat_id': user_id,
                            'caption': message_text if message_text else None
                        }
                        
                        # Отправляем запрос
                        response = requests.post(f'{api_url}/{method}', files=files, data=data, timeout=30)
                    
                    # Проверяем ответ
                    response_json = response.json()
                    if response.status_code == 200 and response_json.get('ok'):
                        # Сохраняем сообщение в базу
                        messages.append({
                            'id': len(messages) + 1,
                            'user_id': user_id,
                            'username': username,
                            'text': message_text,
                            'timestamp': datetime.datetime.now().isoformat(),
                            'is_incoming': False,
                            'is_button_press': False,
                            'broadcast': True,
                            'admin_username': session.get('username', 'admin')
                        })
                        successful_count += 1
                    else:
                        logger.error(f"Ошибка API при отправке файла пользователю {user_id}: {response_json.get('description')}")
                        failed_count += 1
                except Exception as e:
                    logger.error(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")
                    failed_count += 1
            
            # Удаляем временный файл
            try:
                os.remove(file_path)
            except Exception as e:
                logger.error(f"Ошибка при удалении временного файла {file_path}: {e}")
        except Exception as e:
            logger.error(f"Общая ошибка при рассылке: {e}")
    else:
        for user in users:
            try:
                user_id = user['id']
                username = user.get('username', 'Без имени')
                
                # Отправляем текстовое сообщение через HTTP API
                response = requests.post(
                    f'{api_url}/sendMessage',
                    json={'chat_id': user_id, 'text': message_text},
                    timeout=30
                )
                
                # Проверяем ответ
                response_json = response.json()
                if response.status_code == 200 and response_json.get('ok'):
                    # Сохраняем сообщение в базу
                    messages.append({
                        'id': len(messages) + 1,
                        'user_id': user_id,
                        'username': username,
                        'text': message_text,
                        'timestamp': datetime.datetime.now().isoformat(),
                        'is_incoming': False,
                        'is_button_press': False,
                        'broadcast': True,
                        'admin_username': session.get('username', 'admin')
                    })
                    successful_count += 1
                else:
                    logger.error(f"Ошибка API при отправке сообщения пользователю {user_id}: {response_json.get('description')}")
                    failed_count += 1
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")
                failed_count += 1
    
    save_messages(messages)
    
    flash(f'Сообщение отправлено {successful_count} пользователям. Не удалось отправить {failed_count} пользователям.', 'info')
    return redirect(url_for('dashboard'))

@app.route('/save_settings', methods=['POST'])
@login_required
def save_settings_handler():
    settings = load_settings()
    
    # Проверяем наличие действия
    action = request.form.get('action')
    if action:
        if action == 'restart':
            flash('Бот перезапущен', 'success')
            init_bot()
            return redirect(url_for('settings_page'))
        elif action == 'stop':
            flash('Бот остановлен', 'success')
            global bot, application
            application = None
            bot = None
            return redirect(url_for('settings_page'))
    
    # Обновляем настройки
    settings['bot_token'] = request.form.get('bot_token', '')
    settings['bot_name'] = request.form.get('bot_name', 'Telegram Bot')
    settings['welcome_message'] = request.form.get('welcome_message', 'Привет! Я ваш бот.')
    settings['auto_reply'] = 'auto_reply' in request.form
    settings['admin_id'] = request.form.get('admin_id', '')
    
    save_settings(settings)
    
    # Перезапускаем бота, если токен изменился
    init_bot()
    
    flash('Настройки сохранены', 'success')
    return redirect(url_for('settings_page'))

@app.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    users = load_users()
    messages = load_messages()
    
    # Находим пользователя
    user = next((u for u in users if u['id'] == user_id), None)
    if user:
        # Удаляем сообщения пользователя
        messages = [m for m in messages if m['user_id'] != user_id]
        save_messages(messages)
        
        # Удаляем пользователя
        users = [u for u in users if u['id'] != user_id]
        save_users(users)
        
        try:
            # Отправляем сообщение пользователю о блокировке через HTTP API
            if bot and bot.token:
                api_url = f'https://api.telegram.org/bot{bot.token}/sendMessage'
                response = requests.post(
                    api_url,
                    json={
                        'chat_id': user_id,
                        'text': "Вы были заблокированы администратором."
                    },
                    timeout=10
                )
                
                if not response.json().get('ok'):
                    logger.error(f"Ошибка при отправке сообщения о блокировке пользователю {user_id}: {response.json().get('description')}")
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения о блокировке пользователю {user_id}: {e}")
        
        flash('Пользователь успешно удален', 'success')
    else:
        flash('Пользователь не найден', 'error')
    
    return redirect(url_for('users'))

@app.route('/send_message/<int:user_id>', methods=['POST'])
@login_required
def send_user_message(user_id):
    message_text = request.form['message']
    messages = load_messages()
    
    # Проверяем инициализацию бота
    if not bot or not bot.token:
        flash('Ошибка: Бот не инициализирован. Проверьте настройки бота.', 'danger')
        return redirect(url_for('messages'))
    
    try:
        # Отправляем сообщение через HTTP API
        api_url = f'https://api.telegram.org/bot{bot.token}'
        response = requests.post(
            f'{api_url}/sendMessage',
            json={'chat_id': user_id, 'text': message_text},
            timeout=30
        )
        
        # Проверяем ответ
        response_json = response.json()
        if not response_json.get('ok'):
            raise Exception(f"Ошибка API: {response_json.get('description')}")
        
        # Сохраняем сообщение в базу
        messages.append({
            'id': len(messages) + 1,
            'user_id': user_id,
            'text': message_text,
            'timestamp': datetime.datetime.now().isoformat(),
            'is_incoming': False
        })
        save_messages(messages)
        
        flash('Сообщение успешно отправлено', 'success')
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")
        flash(f'Ошибка при отправке сообщения: {str(e)}', 'danger')
    
    return redirect(url_for('messages'))

@app.route('/export_data')
@login_required
def export_data():
    # Создаем словарь с данными
    data = {
        'users': load_users(),
        'messages': load_messages(),
        'settings': load_settings()
    }
    
    # Создаем JSON файл
    json_data = json.dumps(data, ensure_ascii=False, indent=4)
    
    # Создаем файл для скачивания
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"telegram_bot_data_{timestamp}.json"
    
    # Отправляем файл
    return send_file(
        io.BytesIO(json_data.encode('utf-8')),
        mimetype='application/json',
        as_attachment=True,
        download_name=filename
    )

@app.route('/import_data', methods=['POST'])
@login_required
def import_data():
    if 'import_file' not in request.files:
        flash('Файл не выбран', 'danger')
        return redirect(url_for('admin'))
    
    file = request.files['import_file']
    
    if file.filename == '':
        flash('Файл не выбран', 'danger')
        return redirect(url_for('admin'))
    
    if file and file.filename.endswith('.json'):
        try:
            data = json.loads(file.read().decode('utf-8'))
            
            # Проверяем структуру данных
            if 'users' in data and 'messages' in data and 'settings' in data:
                # Сохраняем данные
                save_users(data['users'])
                save_messages(data['messages'])
                
                # Сохраняем настройки
                with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                    json.dump(data['settings'], f, ensure_ascii=False, indent=4)
                
                # Перезапускаем бота с новыми настройками
                global application
                if application:
                    application.stop()
                init_bot()
                
                flash('Данные успешно импортированы', 'success')
            else:
                flash('Неверный формат файла', 'danger')
        except Exception as e:
            flash(f'Ошибка при импорте данных: {e}', 'danger')
    else:
        flash('Выберите файл JSON', 'danger')
    
    return redirect(url_for('admin'))

@app.route('/clear_database')
@login_required
def clear_database():
    # Очищаем базу данных
    save_users([])
    save_messages([])
    
    flash('База данных успешно очищена', 'success')
    return redirect(url_for('admin'))

@app.route('/create_backup')
@login_required
def create_backup():
    # Создаем папку для бэкапов, если её нет
    backup_dir = os.path.join(DATA_DIR, 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    
    # Создаем имя файла для бэкапа
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f"backup_{timestamp}.json"
    backup_path = os.path.join(backup_dir, backup_filename)
    
    # Собираем данные
    data = {
        'users': load_users(),
        'messages': load_messages(),
        'settings': load_settings()
    }
    
    # Сохраняем бэкап
    with open(backup_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    
    flash(f'Резервная копия создана: {backup_filename}', 'success')
    return redirect(url_for('admin'))

@app.route('/optimize_database')
@login_required
def optimize_database():
    # В данном случае "оптимизация" - это просто удаление дубликатов и устаревших записей
    users = load_users()
    messages = load_messages()
    
    # Удаляем дубликаты пользователей
    unique_users = []
    user_ids = set()
    
    for user in users:
        if user['id'] not in user_ids:
            user_ids.add(user['id'])
            unique_users.append(user)
    
    # Ограничиваем историю сообщений (например, последние 1000)
    messages.sort(key=lambda x: datetime.datetime.fromisoformat(x['timestamp']), reverse=True)
    messages = messages[:1000]
    
    # Сохраняем оптимизированные данные
    save_users(unique_users)
    save_messages(messages)
    
    flash('База данных успешно оптимизирована', 'success')
    return redirect(url_for('admin'))

# Маршруты для управления кнопками
@app.route('/buttons')
@login_required
def buttons_page():
    buttons = load_buttons()
    settings = load_settings()
    return render_template('buttons.html',
                          buttons=buttons,
                          settings=settings,
                          bot_name=settings['bot_name'],
                          username=session.get('username', 'admin'),
                          active_page="buttons",
                          preview_enabled=True)

@app.route('/add_button', methods=['POST'])
@login_required
def add_button():
    buttons = load_buttons()
    
    # Получаем данные из формы
    text = request.form.get('text', '')
    response = request.form.get('response', '')
    url = request.form.get('url', '')
    url_text = request.form.get('url_text', '')
    
    if not text or not response:
        flash('Пожалуйста, заполните обязательные поля', 'error')
        return redirect(url_for('buttons_page'))
    
    # Формируем объект кнопки
    button_id = str(len(buttons) + 1)
    new_button = {
        'id': button_id,
        'text': text,
        'response': response,
        'url': url,
        'url_text': url_text,
        'image_path': None
    }
    
    # Обрабатываем загруженное изображение, если есть
    if 'image' in request.files and request.files['image'].filename:
        try:
            image = request.files['image']
            
            # Проверяем тип файла
            if not allowed_file(image.filename):
                flash('Неподдерживаемый формат файла. Разрешены только PNG, JPG и GIF', 'error')
                return redirect(url_for('buttons_page'))
            
            # Создаем папку для хранения изображений кнопок, если она не существует
            button_images_dir = os.path.join('static', 'button_images')
            os.makedirs(button_images_dir, exist_ok=True)
            
            # Генерируем уникальное имя файла
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_filename = secure_filename(image.filename).replace(' ', '_')
            filename = f"button_{button_id}_{timestamp}_{safe_filename}"
            file_path = os.path.join(button_images_dir, filename)
            
            # Сохраняем файл
            image.save(file_path)
            
            # Убедимся, что файл существует
            if not os.path.exists(file_path):
                raise Exception(f"Файл не был сохранен: {file_path}")
            
            # Сохраняем относительный путь к изображению, используя прямые слэши для URL
            relative_path = 'button_images/' + filename
            new_button['image_path'] = relative_path
            logger.info(f"Изображение сохранено по пути: {file_path}, относительный путь: {relative_path}")
            
        except Exception as e:
            logger.error(f"Ошибка при загрузке изображения: {str(e)}")
            flash(f'Ошибка при загрузке изображения: {str(e)}', 'warning')
    
    buttons.append(new_button)
    save_buttons(buttons)
    
    flash('Кнопка успешно добавлена', 'success')
    return redirect(url_for('buttons_page'))

@app.route('/edit_button/<string:button_id>', methods=['GET', 'POST'])
def edit_button(button_id):
    buttons = load_buttons()
    
    if button_id not in buttons:
        flash('Кнопка не найдена', 'error')
        return redirect(url_for('buttons'))
    
    if request.method == 'POST':
        text = request.form.get('text')
        response = request.form.get('response')
        url = request.form.get('url', '')
        url_text = request.form.get('url_text', '')
        
        if not text or not response:
            flash('Пожалуйста, заполните обязательные поля', 'error')
            return redirect(url_for('buttons'))
        
        # Обновляем текст и ответ кнопки
        buttons[button_id]['text'] = text
        buttons[button_id]['response'] = response
        buttons[button_id]['url'] = url
        buttons[button_id]['url_text'] = url_text
        
        # Обработка изображения
        if 'image' in request.files and request.files['image'].filename != '':
            image_file = request.files['image']
            if allowed_file(image_file.filename):
                # Генерируем уникальное имя файла
                filename = secure_filename(image_file.filename)
                ext = filename.rsplit('.', 1)[1].lower()
                new_filename = f"{uuid.uuid4().hex}.{ext}"
                
                # Создаем папку для изображений кнопок, если она не существует
                buttons_image_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'buttons')
                os.makedirs(buttons_image_dir, exist_ok=True)
                
                # Сохраняем изображение
                image_path = os.path.join(buttons_image_dir, new_filename)
                image_file.save(image_path)
                
                # Удаляем старое изображение, если оно было
                if 'image_path' in buttons[button_id] and buttons[button_id]['image_path']:
                    old_image_path = os.path.join(app.root_path, 'static', buttons[button_id]['image_path'])
                    if os.path.exists(old_image_path):
                        os.remove(old_image_path)
                
                # Обновляем путь к изображению в данных кнопки, используя прямые слэши
                buttons[button_id]['image_path'] = f"uploads/buttons/{new_filename}"
            else:
                flash('Неподдерживаемый формат файла. Разрешены только PNG, JPG и GIF', 'error')
                return redirect(url_for('buttons'))
        
        # Обработка удаления изображения
        if 'remove_image' in request.form and request.form['remove_image'] == 'true':
            if 'image_path' in buttons[button_id] and buttons[button_id]['image_path']:
                # Удаляем файл изображения
                old_image_path = os.path.join(app.root_path, 'static', buttons[button_id]['image_path'])
                if os.path.exists(old_image_path):
                    os.remove(old_image_path)
                # Удаляем ссылку на изображение из данных кнопки
                buttons[button_id]['image_path'] = ''
        
        # Сохраняем обновленные данные кнопок
        save_buttons(buttons)
        flash('Кнопка успешно обновлена', 'success')
        return redirect(url_for('buttons'))
    
    # Если метод GET, возвращаем данные кнопки для редактирования
    return jsonify(buttons[button_id])

@app.route('/delete_button/<button_id>', methods=['POST'])
@login_required
def delete_button(button_id):
    buttons = load_buttons()
    
    # Удаляем кнопку
    buttons = [b for b in buttons if b['id'] != button_id]
    save_buttons(buttons)
    
    flash('Кнопка успешно удалена', 'success')
    return redirect(url_for('buttons_page'))

@app.route('/preview', methods=['GET'])
def preview():
    return render_template('preview.html')

@app.route('/preview-button', methods=['POST'])
def preview_button():
    try:
        # Получаем данные из формы
        text = request.form.get('text', '').strip()
        response = request.form.get('response', '').strip()
        url = request.form.get('url', '').strip()
        url_text = request.form.get('url_text', '').strip()
        
        # Обработка изображения, если оно есть
        image_path = None
        if 'image' in request.files and request.files['image'].filename:
            image = request.files['image']
            # Создаем временную директорию для хранения изображений предпросмотра
            preview_dir = os.path.join(app.static_folder, 'preview_images')
            os.makedirs(preview_dir, exist_ok=True)
            
            # Генерируем уникальное имя файла
            filename = secure_filename(image.filename)
            temp_filename = f"preview_{int(time.time())}_{filename}"
            temp_path = os.path.join(preview_dir, temp_filename)
            
            # Сохраняем файл
            image.save(temp_path)
            image_path = f"/static/preview_images/{temp_filename}"
            
            # Устанавливаем таймер для удаления временного файла через 10 минут
            def remove_temp_file():
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                except Exception as e:
                    app.logger.error(f"Ошибка при удалении временного файла: {e}")
            
            timer = threading.Timer(600, remove_temp_file)
            timer.daemon = True
            timer.start()
        
        # Валидация обязательных полей
        if not text or not response:
            return render_template('preview.html', error="Пожалуйста, заполните обязательные поля: Текст кнопки и Ответ")
        
        # Отображаем предварительный просмотр
        return render_template('preview.html', 
                              button_text=text, 
                              response=response, 
                              url=url, 
                              url_text=url_text, 
                              image_path=image_path)
    
    except Exception as e:
        app.logger.error(f"Ошибка при предварительном просмотре: {str(e)}")
        return render_template('preview.html', error=f"Произошла ошибка: {str(e)}")

@app.route('/preview_button_page')
@login_required
def preview_button_page():
    return render_template('preview_button.html', 
                         button_text='', 
                         response_text='',
                         settings=load_settings(),
                         username=session.get('username', 'admin'))

def signal_handler(sig, frame):
    print('\nЗавершение работы...')
    global application
    if application:
        print('Останавливаем бота...')
        try:
            # Создаем новый event loop для корректной остановки бота
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Останавливаем бот
            try:
                loop.run_until_complete(application.stop())
            except RuntimeError as e:
                # Игнорируем ошибку "Application is not running"
                if "Application is not running" not in str(e):
                    print(f'Ошибка при остановке бота: {e}')
                else:
                    print('Бот уже остановлен')
            finally:
                loop.close()
                application = None
        except Exception as e:
            print(f'Ошибка при остановке бота: {e}')
    print('Завершаем работу веб-сервера...')
    # Используем os._exit вместо sys.exit для избежания конфликтов с другими потоками
    import os
    os._exit(0)

@app.errorhandler(500)
def handle_server_error(e):
    return render_template('error.html', 
                           error="Произошла внутренняя ошибка сервера. Пожалуйста, попробуйте позже."), 500

# Определение разрешенных расширений файлов для загрузки
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

if __name__ == '__main__':
    # Регистрируем обработчик сигнала SIGINT (Ctrl+C)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        init_bot()
        print('Бот запущен. Нажмите Ctrl+C для завершения.')
        app.run(debug=False, host='0.0.0.0', port=5000, use_reloader=False)
    except KeyboardInterrupt:
        print('\nПолучен сигнал завершения.')
    finally:
        if application:
            print('Останавливаем бота...')
            try:
                # Создаем новый event loop для корректной остановки бота
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Останавливаем бот
                try:
                    loop.run_until_complete(application.stop())
                except RuntimeError as e:
                    # Игнорируем ошибку "Application is not running"
                    if "Application is not running" not in str(e):
                        print(f'Ошибка при остановке бота: {e}')
                    else:
                        print('Бот уже остановлен')
                finally:
                    loop.close()
                    application = None
            except Exception as e:
                print(f'Ошибка при остановке бота: {e}')
        print('Работа завершена.')
        sys.exit(0) 
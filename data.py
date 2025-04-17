import os
import json
import datetime
from typing import List, Dict, Any, Optional, Union

# Директория с данными
DATA_DIR = 'data'
os.makedirs(DATA_DIR, exist_ok=True)

# Пути к файлам данных
USERS_FILE = os.path.join(DATA_DIR, 'users.json')
MESSAGES_FILE = os.path.join(DATA_DIR, 'messages.json')
SETTINGS_FILE = os.path.join(DATA_DIR, 'settings.json')
ADMINS_FILE = os.path.join(DATA_DIR, 'admins.json')

# Типы данных
UserType = Dict[str, Union[int, str, bool, List[str]]]
MessageType = Dict[str, Union[int, str, bool]]
SettingsType = Dict[str, Union[str, bool]]
AdminType = Dict[str, str]

def init_data_files() -> None:
    """Инициализация файлов с данными, если они не существуют."""
    
    # Пользователи
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f)
    
    # Сообщения
    if not os.path.exists(MESSAGES_FILE):
        with open(MESSAGES_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f)
    
    # Настройки
    if not os.path.exists(SETTINGS_FILE):
        default_settings = {
            'bot_token': '',
            'bot_name': 'Telegram Bot',
            'welcome_message': 'Привет! Я ваш Telegram бот.',
            'auto_reply': False,
            'admin_id': ''
        }
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_settings, f, ensure_ascii=False, indent=4)
    
    # Администраторы
    if not os.path.exists(ADMINS_FILE):
        default_admin = {
            'username': 'admin',
            'password': 'admin',  # В реальном проекте используйте хеширование паролей
            'role': 'admin'
        }
        with open(ADMINS_FILE, 'w', encoding='utf-8') as f:
            json.dump([default_admin], f, ensure_ascii=False, indent=4)

def load_users() -> List[UserType]:
    """Загрузка списка пользователей."""
    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_users(users: List[UserType]) -> None:
    """Сохранение списка пользователей."""
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

def load_messages() -> List[MessageType]:
    """Загрузка списка сообщений."""
    with open(MESSAGES_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_messages(messages: List[MessageType]) -> None:
    """Сохранение списка сообщений."""
    with open(MESSAGES_FILE, 'w', encoding='utf-8') as f:
        json.dump(messages, f, ensure_ascii=False, indent=4)

def load_settings() -> SettingsType:
    """Загрузка настроек бота."""
    with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_settings(settings: SettingsType) -> None:
    """Сохранение настроек бота."""
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=4)

def load_admins() -> List[AdminType]:
    """Загрузка списка администраторов."""
    with open(ADMINS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_admins(admins: List[AdminType]) -> None:
    """Сохранение списка администраторов."""
    with open(ADMINS_FILE, 'w', encoding='utf-8') as f:
        json.dump(admins, f, ensure_ascii=False, indent=4)

def add_user(user_id: int, username: Optional[str] = None, 
             full_name: Optional[str] = None) -> UserType:
    """Добавление нового пользователя или обновление существующего."""
    users = load_users()
    
    # Проверяем, существует ли пользователь
    for user in users:
        if user['id'] == user_id:
            # Обновляем данные пользователя
            user['username'] = username or user.get('username', 'Без имени')
            user['full_name'] = full_name or user.get('full_name', '')
            user['is_active'] = True
            user['last_activity'] = datetime.datetime.now().isoformat()
            save_users(users)
            return user
    
    # Создаем нового пользователя
    new_user = {
        'id': user_id,
        'username': username or 'Без имени',
        'full_name': full_name or '',
        'created_at': datetime.datetime.now().isoformat(),
        'is_active': True,
        'last_activity': datetime.datetime.now().isoformat(),
        'message_count': 0
    }
    
    users.append(new_user)
    save_users(users)
    return new_user

def add_message(user_id: int, text: str, is_incoming: bool = True) -> MessageType:
    """Добавление нового сообщения."""
    messages = load_messages()
    
    new_message = {
        'id': len(messages) + 1,
        'user_id': user_id,
        'text': text,
        'timestamp': datetime.datetime.now().isoformat(),
        'is_incoming': is_incoming
    }
    
    messages.append(new_message)
    save_messages(messages)
    
    # Увеличиваем счетчик сообщений у пользователя
    users = load_users()
    for user in users:
        if user['id'] == user_id:
            user['message_count'] = user.get('message_count', 0) + 1
            user['last_activity'] = datetime.datetime.now().isoformat()
            break
    save_users(users)
    
    return new_message

def get_user(user_id: int) -> Optional[UserType]:
    """Получение данных о пользователе по его ID."""
    users = load_users()
    for user in users:
        if user['id'] == user_id:
            return user
    return None

def get_user_messages(user_id: int) -> List[MessageType]:
    """Получение всех сообщений пользователя."""
    messages = load_messages()
    return [msg for msg in messages if msg['user_id'] == user_id]

def delete_user(user_id: int) -> bool:
    """Удаление пользователя."""
    users = load_users()
    initial_count = len(users)
    users = [user for user in users if user['id'] != user_id]
    
    if len(users) < initial_count:
        save_users(users)
        return True
    return False

def get_statistics() -> Dict[str, Any]:
    """Получение статистики использования бота."""
    users = load_users()
    messages = load_messages()
    
    today = datetime.datetime.now().date()
    
    # Общая статистика
    stats = {
        'total_users': len(users),
        'total_messages': len(messages),
        'active_users_today': 0,
        'new_users_today': 0,
        'messages_today': 0
    }
    
    # Статистика за сегодня
    for user in users:
        created_at = datetime.datetime.fromisoformat(user['created_at']).date()
        if created_at == today:
            stats['new_users_today'] += 1
        
        if 'last_activity' in user:
            last_activity = datetime.datetime.fromisoformat(user['last_activity']).date()
            if last_activity == today:
                stats['active_users_today'] += 1
    
    # Сообщения за сегодня
    stats['messages_today'] = sum(
        1 for msg in messages 
        if datetime.datetime.fromisoformat(msg['timestamp']).date() == today
    )
    
    # Данные для графиков (за последние 7 дней)
    last_7_days = [(datetime.datetime.now() - datetime.timedelta(days=i)).date() 
                    for i in range(6, -1, -1)]
    
    stats['chart_dates'] = [day.strftime('%d.%m') for day in last_7_days]
    
    # Активность пользователей за 7 дней
    stats['user_activity'] = []
    for day in last_7_days:
        active_count = sum(
            1 for user in users 
            if 'last_activity' in user and 
            datetime.datetime.fromisoformat(user['last_activity']).date() == day
        )
        stats['user_activity'].append(active_count)
    
    # Новые пользователи за 7 дней
    stats['new_users'] = []
    for day in last_7_days:
        new_count = sum(
            1 for user in users 
            if datetime.datetime.fromisoformat(user['created_at']).date() == day
        )
        stats['new_users'].append(new_count)
    
    # Сообщения за 7 дней
    stats['messages_count'] = []
    for day in last_7_days:
        msg_count = sum(
            1 for msg in messages 
            if datetime.datetime.fromisoformat(msg['timestamp']).date() == day
        )
        stats['messages_count'].append(msg_count)
        
    return stats

def create_backup() -> str:
    """Создание резервной копии данных."""
    # Создаем папку для бэкапов
    backup_dir = os.path.join(DATA_DIR, 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    
    # Формируем имя файла с меткой времени
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = os.path.join(backup_dir, f'backup_{timestamp}.json')
    
    # Собираем все данные
    data = {
        'users': load_users(),
        'messages': load_messages(),
        'settings': load_settings(),
        'backup_date': datetime.datetime.now().isoformat()
    }
    
    # Сохраняем бэкап
    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    
    return backup_file

def restore_backup(backup_file: str) -> bool:
    """Восстановление данных из резервной копии."""
    try:
        with open(backup_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if all(key in data for key in ['users', 'messages', 'settings']):
            save_users(data['users'])
            save_messages(data['messages'])
            save_settings(data['settings'])
            return True
        return False
    except Exception:
        return False

# Инициализация при импорте модуля
init_data_files() 
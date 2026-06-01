import sqlite3
from datetime import datetime,timedelta
import uuid # Для генерации уникальных ID
from typing import List, Dict # Понадобится для подсказок типов
import sys
import os

# Добавляем папку backend в sys.path для импорта config
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import DATABASE_FILE
from data.seed_data import INITIAL_MESSAGES,INITIAL_ROOMS,INITIAL_USERS

# Создаем папку data, если её нет
os.makedirs(os.path.dirname(DATABASE_FILE), exist_ok=True)

print(f"Используем файл БД: {DATABASE_FILE}")

def get_db_connection():
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row # Это позволит получать данные как словари (например, row['username'])
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Таблица для пользователей (id, username)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL UNIQUE
        );
    """)

    # Таблица для сообщений (id, user_id, room, text, timestamp)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            room TEXT NOT NULL,
            text TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
    """)
    
    # Таблица для комнат (name)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            name TEXT PRIMARY KEY
        );
    """)
    
    # Таблица для отслеживания активных пользователей в комнатах (many-to-many)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS room_users (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            room_name TEXT NOT NULL,
            joined_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (room_name) REFERENCES rooms (name),
            UNIQUE(user_id, room_name)
        );
    """)

    conn.commit() # Сохраняем изменения
    conn.close() # Закрываем БД


def seed_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Заполняем пользователей
    cursor.execute("SELECT COUNT(*) FROM users")

    if cursor.fetchone()[0] == 0: # Если таблица пользователей пуста
        print("Заполняем пользователей...")
        for username in INITIAL_USERS:
            user_id = str(uuid.uuid4())
            cursor.execute("INSERT INTO users (id, username) VALUES (?, ?)", (user_id, username))
            
    # Заполняем комнаты
    cursor.execute("SELECT COUNT(*) FROM rooms")

    if cursor.fetchone()[0] == 0: # Если таблица комнат пуста
        print("Заполняем комнаты...")
        for room_name in INITIAL_ROOMS:
            cursor.execute("INSERT INTO rooms (name) VALUES (?)", (room_name,))

    # Заполняем сообщения (нужно сначала получить ID пользователей)
    cursor.execute("SELECT COUNT(*) FROM messages")
    if cursor.fetchone()[0] == 0: # Если таблица сообщений пуста
        print("Заполняем сообщения...")
        # Получаем всех пользователей для сопоставления
        users_map ={} 
        for row in conn.execute("SELECT id, username FROM users").fetchall():
            users_map [row['username']]=row['id']

        for room, sender_username, text, minutes_ago in INITIAL_MESSAGES:
            message_id = str(uuid.uuid4())
            user_id = users_map.get(sender_username) # Получаем user_id по username
            if user_id:
                timestamp = datetime.now() - timedelta(minutes=minutes_ago)
                cursor.execute(
                    "INSERT INTO messages (id, user_id, room, text, timestamp) VALUES (?, ?, ?, ?, ?)",
                    (message_id, user_id, room, text, timestamp.isoformat())
                )
            else:
                print(f"Внимание: Пользователь '{sender_username}' не найден для сообщения.")
    conn.commit()
    conn.close()


def add_message(user_id:str, room:str, text:str) -> str:
    conn = get_db_connection()
    cursor = conn.cursor()
    msg_id = str(uuid.uuid4())
    timestamp = datetime.now().isoformat()
    sql_insert = "INSERT INTO messages VALUES (?, ?, ?, ?, ?)"
    cursor.execute(sql_insert, (msg_id, user_id, room, text, timestamp))
    conn.commit()
    conn.close()
    return msg_id


def get_messages_for_room(room_name: str) -> List[Dict]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT m.id, m.user_id, u.username, m.room, m.text, m.timestamp
        FROM messages m
        JOIN users u ON m.user_id = u.id
        WHERE m.room = ?
        ORDER BY m.timestamp ASC
    """, (room_name,))
    
    rows = cursor.fetchall()
    conn.close()
    
    messages = []
    for row in rows:
        messages.append({
            'id': row['id'],
            'user_id': row['user_id'],
            'username': row['username'],
            'room': row['room'],
            'text': row['text'],
            'timestamp': row['timestamp']
        })
    return messages


def update_message_text(message_id: str, new_text: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE messages SET text = ? WHERE id = ?", (new_text, message_id))
    conn.commit()
    
    if cursor.rowcount == 0:
        conn.close()
        return False
    
    conn.close()
    return True


def delete_message_by_id(message_id: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages WHERE id = ?", (message_id,))
    conn.commit()
    
    if cursor.rowcount == 0:
        conn.close()
        return False
    
    conn.close()
    return True


def get_or_create_user(username: str) -> Dict:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Ищем существующего пользователя
    cursor.execute("SELECT id, username FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    
    if row:
        conn.close()
        return {'id': row['id'], 'username': row['username'], 'created': False}
    
    # Создаем нового пользователя
    user_id = str(uuid.uuid4())
    cursor.execute("INSERT INTO users (id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()
    conn.close()
    
    return {'id': user_id, 'username': username, 'created': True}


def get_user_by_id(user_id: str) -> Dict | None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {'id': row['id'], 'username': row['username']}
    return None


def get_all_users() -> List[Dict]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username FROM users ORDER BY username ASC")
    rows = cursor.fetchall()
    conn.close()
    
    users = []
    for row in rows:
        users.append({'id': row['id'], 'username': row['username']})
    return users


def add_room(room_name: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("INSERT INTO rooms (name) VALUES (?)", (room_name,))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False


def get_all_rooms() -> List[str]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM rooms ORDER BY name ASC")
    rows = cursor.fetchall()
    conn.close()
    
    rooms = [row['name'] for row in rows]
    return rooms


# ========== ФУНКЦИИ ДЛЯ УПРАВЛЕНИЯ АКТИВНЫМИ ПОЛЬЗОВАТЕЛЯМИ В КОМНАТАХ ==========

def add_user_to_room(user_id: str, room_name: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Проверяем, существуют ли пользователь и комната
    cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    if not cursor.fetchone():
        conn.close()
        return False
    
    cursor.execute("SELECT name FROM rooms WHERE name = ?", (room_name,))
    if not cursor.fetchone():
        conn.close()
        return False
    
    try:
        entry_id = str(uuid.uuid4())
        joined_at = datetime.now().isoformat()
        cursor.execute(
            "INSERT INTO room_users (id, user_id, room_name, joined_at) VALUES (?, ?, ?, ?)",
            (entry_id, user_id, room_name, joined_at)
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False


def remove_user_from_room(user_id: str, room_name: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM room_users WHERE user_id = ? AND room_name = ?", (user_id, room_name))
    conn.commit()
    
    if cursor.rowcount == 0:
        conn.close()
        return False
    
    conn.close()
    return True


def get_active_users_in_room(room_name: str) -> List[Dict]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ru.id, u.id as user_id, u.username, ru.room_name, ru.joined_at
        FROM room_users ru
        JOIN users u ON ru.user_id = u.id
        WHERE ru.room_name = ?
        ORDER BY ru.joined_at ASC
    """, (room_name,))
    
    rows = cursor.fetchall()
    conn.close()
    
    users = []
    for row in rows:
        users.append({
            'user_id': row['user_id'],
            'username': row['username'],
            'room_name': row['room_name'],
            'joined_at': row['joined_at']
        })
    return users


def get_user_rooms(user_id: str) -> List[Dict]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT ru.room_name, ru.joined_at
        FROM room_users ru
        WHERE ru.user_id = ?
        ORDER BY ru.joined_at ASC
    """, (user_id,))
    
    rows = cursor.fetchall()
    conn.close()
    
    rooms = []
    for row in rows:
        rooms.append({
            'room_name': row['room_name'],
            'joined_at': row['joined_at']
        })
    return rooms


def is_user_in_room(user_id: str, room_name: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM room_users WHERE user_id = ? AND room_name = ?", (user_id, room_name))
    result = cursor.fetchone()
    conn.close()
    return result is not None


if __name__ == "__main__": 
    print("=" * 60)
    print("ИНИЦИАЛИЗАЦИЯ БД")
    print("=" * 60)
    get_db_connection()
    init_db()
    seed_db()

    # Добавляем новые сообщения
    print("✓ Добавление сообщений...")
    msg_id_1 = add_message("0bba9bbf-7802-4e98-9a16-ec961c1e49eb", "general", "Всем привет!")
    print(f"  Сообщение 1 добавлено с ID: {msg_id_1}")
    
    msg_id_2 = add_message("0bba9bbf-7802-4e98-9a16-ec961c1e49eb", "work", "Как дела с проектом?")
    print(f"  Сообщение 2 добавлено с ID: {msg_id_2}")
    
    msg_id_3 = add_message("b07a4c85-f090-4422-964c-0f1417392cb9", "work", "Дела хорошо, справляемся!")
    print(f"  Сообщение 3 добавлено с ID: {msg_id_3}")
    
    # Получаем сообщения из комнат
    print("✓ Получение сообщений из комнаты 'general':")
    messages_general = get_messages_for_room("general")
    for msg in messages_general:
        print(f"  - {msg['username']}: {msg['text']} ({msg['timestamp']})")
    
    print("✓ Получение сообщений из комнаты 'work':")
    messages_work = get_messages_for_room("work")
    for msg in messages_work:
        print(f"  - {msg['username']}: {msg['text']} ({msg['timestamp']})")
    

    # Обновляем сообщение
    print("✓ Обновление текста сообщения...")
    old_msg = messages_work[len(messages_work)-1]
    print(f"  Было: {old_msg['text']}")
    success = update_message_text(old_msg['id'], "Все отлично! Проект на финише!")
    if success:
        print(f"  Стало: Все отлично! Проект на финише!")
    
    # Проверяем обновление
    print("✓ Проверка обновленных сообщений 'work':")
    messages_work = get_messages_for_room("work")
    for msg in messages_work:
        print(f"  - {msg['username']}: {msg['text']}")
    
    # Удаляем сообщение
    if len(messages_general) > 0:
        msg_to_delete = messages_general[0]
        print(f"✓ Удаление сообщения: '{msg_to_delete['text']}'")
        success = delete_message_by_id(msg_to_delete['id'])
        if success:
            print("  Сообщение успешно удалено!")
    
    # Получаем или создаем пользователя
    print("✓ Получение или создание пользователя...")
    user1 = get_or_create_user("Алиса")
    print(f"  Пользователь '{user1['username']}': ID={user1['id']}, создан={user1['created']}")
    
    user2 = get_or_create_user("Новый пользователь")
    print(f"  Пользователь '{user2['username']}': ID={user2['id']}, создан={user2['created']}")
    
    # Получаем пользователя по ID
    print("✓ Получение пользователя по ID...")
    found_user = get_user_by_id(user1['id'])
    if found_user:
        print(f"  Найден пользователь: {found_user['username']} (ID: {found_user['id']})")
    
    # Получаем всех пользователей
    print("✓ Все пользователи в системе:")
    all_users = get_all_users()
    for user in all_users:
        print(f"  - {user['username']} (ID: {user['id']})")
    
    # Добавляем новую комнату
    print("✓ Добавление новой комнаты...")
    success = add_room("random")
    print(f"  Комната 'random' добавлена: {success}")
    
    success = add_room("random")  # Попытка добавить существующую
    print(f"  Попытка добавить 'random' еще раз: {success} (ожидается False)")
    
    # Получаем все комнаты
    print("✓ Все комнаты в системе:")
    all_rooms = get_all_rooms()
    for room in all_rooms:
        print(f"  - {room}")
    
    print("=" * 60)
    print("ЗАДАЧА 8: Управление активными пользователями в комнатах")
    print("=" * 60)
    
    # Получаем ID пользователей для тестирования
    all_users_list = get_all_users()
    alice_id = all_users_list[0]['id']  # Алиса
    bob_id = all_users_list[1]['id']    # Боб
    charlie_id = all_users_list[2]['id']  # Чарли
    
    # Добавляем пользователей в комнаты
    print("✓ Добавление пользователей в комнаты...")
    success1 = add_user_to_room(alice_id, "general")
    print(f"  Алиса присоединилась к 'general': {success1}")
    
    success2 = add_user_to_room(bob_id, "general")
    print(f"  Боб присоединился к 'general': {success2}")
    
    success3 = add_user_to_room(charlie_id, "work")
    print(f"  Чарли присоединился к 'work': {success3}")
    
    success4 = add_user_to_room(alice_id, "work")
    print(f"  Алиса присоединилась к 'work': {success4}")
    
    # Попытка добавить того же пользователя еще раз
    success_dup = add_user_to_room(alice_id, "general")
    print(f"  Попытка добавить Алису в 'general' еще раз: {success_dup} (ожидается False)")
    
    # Получаем активных пользователей в комнате
    print("✓ Активные пользователи в комнате 'general':")
    active_general = get_active_users_in_room("general")
    for user in active_general:
        print(f"  - {user['username']} (присоединился: {user['joined_at']})")
    
    print("✓ Активные пользователи в комнате 'work':")
    active_work = get_active_users_in_room("work")
    for user in active_work:
        print(f"  - {user['username']} (присоединился: {user['joined_at']})")
    
    # Проверяем, в каких комнатах находится пользователь
    print("✓ Комнаты, в которых находится Алиса:")
    alice_rooms = get_user_rooms(alice_id)
    for room_info in alice_rooms:
        print(f"  - {room_info['room_name']} (присоединилась: {room_info['joined_at']})")
    
    # Проверяем находится ли пользователь в комнате
    print("✓ Проверка присутствия пользователя в комнате:")
    is_alice_in_general = is_user_in_room(alice_id, "general")
    print(f"  Алиса в 'general': {is_alice_in_general} (ожидается True)")
    
    is_bob_in_work = is_user_in_room(bob_id, "work")
    print(f"  Боб в 'work': {is_bob_in_work} (ожидается False)")
    
    # Удаляем пользователя из комнаты
    print("✓ Удаление пользователя из комнаты...")
    removed = remove_user_from_room(alice_id, "general")
    print(f"  Алиса удалена из 'general': {removed} (ожидается True)")
    
    removed_again = remove_user_from_room(alice_id, "general")
    print(f"  Попытка удалить Алису из 'general' еще раз: {removed_again} (ожидается False)")
    
    # Проверяем активных пользователей после удаления
    print("✓ Активные пользователи в 'general' после удаления Алисы:")
    active_general_after = get_active_users_in_room("general")
    for user in active_general_after:
        print(f"  - {user['username']}")
    print(f"  Всего: {len(active_general_after)} пользователей")
    
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО!")
    print("=" * 60)

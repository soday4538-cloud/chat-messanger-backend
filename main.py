import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
# from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict
from datetime import datetime
# from pathlib import Path
# Импортируем конфиг
from config import DEBUG, ALLOWED_ORIGINS

# Импортируем функции из db_provider
from data.db_provider import (
    init_db,
    seed_db,
    add_message,
    get_messages_for_room,
    update_message_text,
    delete_message_by_id,
    get_or_create_user,
    get_user_by_id,
    get_all_users,
    add_room,
    get_all_rooms,
    add_user_to_room,
    remove_user_from_room,
    get_active_users_in_room,
    get_user_rooms,
    is_user_in_room,
)


# Создаем основной объект приложения
app = FastAPI()

# frontend_path = Path(__file__).parent.parent / "frontend"
# app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
# Это ОЧЕНЬ ВАЖНО для разработки. Позволяет нашему фронтенду
# делать запросы к этому серверу. В реальном продакшене настройки могут быть строже.
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # Загружается из config.py
    allow_credentials=True,
    allow_methods=["*"],  # Разрешаем все методы (GET, POST, DELETE и т.д.)
    allow_headers=["*"],  # Разрешаем все заголовки
)

# Инициализируем БД при запуске приложения
init_db()
seed_db()

# Модели данных 
class User(BaseModel):
    id: str
    name: str
    active_rooms: List[str] = []
    status: str = "offline"  # "offline", "online", "away"


class MessageBase(BaseModel):
    sender_id: str  # Только ID отправителя вместо обFlъекта User
    text: str
    room: str


class Message(BaseModel):
    id: str
    user_id: str
    username: str
    room: str
    text: str
    timestamp: str


class MessageUpdate(BaseModel):
    text: str


class UserRegister(BaseModel):
    username: str


class UserLogin(BaseModel):
    username: str


class JoinRoomRequest(BaseModel):
    user_id: str


class LeaveRoomRequest(BaseModel):
    user_id: str


# ============ API ЭНДПОИНТЫ ============

@app.get("/users", response_model=List[User], summary="Получить список пользователей")
async def get_users():
    users_data = get_all_users()
    users = []
    for user_data in users_data:
        user_rooms = get_user_rooms(user_data['id'])
        active_rooms = [room['room_name'] for room in user_rooms]
        users.append(User(
            id=user_data['id'],
            name=user_data['username'],
            active_rooms=active_rooms,
            status="online" if active_rooms else "offline"
        ))
    return users


@app.get("/rooms/{room_name}/messages", response_model=List[Message], summary="Получить сообщения для комнаты")
async def get_messages(room_name: str):
    messages_data = get_messages_for_room(room_name)
    messages = []
    for msg_data in messages_data:
        messages.append(Message(
            id=msg_data['id'],
            user_id=msg_data['user_id'],
            username=msg_data['username'],
            room=msg_data['room'],
            text=msg_data['text'],
            timestamp=msg_data['timestamp']
        ))
    return messages


@app.post("/messages", response_model=Message, status_code=201, summary="Отправить новое сообщение")
async def create_message(message_in: MessageBase):
    # Проверяем, существует ли пользователь
    sender = get_user_by_id(message_in.sender_id)
    if not sender:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    # Добавляем сообщение в БД
    msg_id = add_message(message_in.sender_id, message_in.room, message_in.text)
    
    return Message(
        id=msg_id,
        user_id=message_in.sender_id,
        username=sender['username'],
        room=message_in.room,
        text=message_in.text,
        timestamp=datetime.now().isoformat()
    )


@app.delete("/messages/{message_id}", status_code=204, summary="Удалить сообщение")
async def delete_message(message_id: str):
    success = delete_message_by_id(message_id)
    if not success:
        raise HTTPException(status_code=404, detail="Сообщение не найдено")


@app.get("/rooms/{room_name}/messages/poll", response_model=List[Message], summary="Опрос новых сообщений в комнате (Polling)")
def poll_new_messages(room_name: str, since: int):
    # Преобразуем миллисекунды в секунды для timestamp
    since_timestamp = since / 1000
    
    # Получаем сообщения из конкретной комнаты
    room_messages = get_messages_for_room(room_name)
    messages = []
    
    for msg in room_messages:
        try:
            # Парсим ISO timestamp и сравниваем как datetime объекты
            msg_datetime = datetime.fromisoformat(msg['timestamp'])
            since_datetime = datetime.fromtimestamp(since_timestamp)
            
            # Сравниваем как datetime объекты для точности
            if msg_datetime > since_datetime:
                messages.append(Message(
                    id=msg['id'],
                    user_id=msg['user_id'],
                    username=msg['username'],
                    room=msg['room'],
                    text=msg['text'],
                    timestamp=msg['timestamp']
                ))
        except ValueError:
            # Если не удалось распарсить timestamp, пропускаем сообщение
            continue
    
    return sorted(messages, key=lambda m: m.timestamp)


@app.post("/register", response_model=User, status_code=201, summary="Зарегистрировать нового пользователя")
async def register_user(user_data: UserRegister):
    user = get_or_create_user(user_data.username)
    
    if not user['created']:
        raise HTTPException(status_code=400, detail="Такой ник уже занят! Выбери другой")
    
    return User(
        id=user['id'],
        name=user['username'],
        active_rooms=[],
        status="offline"
    )


@app.post("/login")
def login(user_data: UserLogin):
    user = get_or_create_user(user_data.username)
    
    user_rooms = get_user_rooms(user['id'])
    active_rooms = [room['room_name'] for room in user_rooms]
    
    return {
        "message": "Успешный вход",
        "user": User(
            id=user['id'],
            name=user['username'],
            active_rooms=active_rooms,
            status="online" if active_rooms else "offline"
        )
    }


@app.post("/rooms/{room_name}/join", response_model=Dict, status_code=200, summary="Присоединиться к комнате")
async def join_room(room_name: str, request: JoinRoomRequest):
    # Проверяем, существует ли пользователь
    user = get_user_by_id(request.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    # Проверяем, существует ли комната, если нет - создаем
    if room_name not in get_all_rooms():
        add_room(room_name)
    
    # Проверяем, уже ли пользователь в комнате
    if is_user_in_room(request.user_id, room_name):
        raise HTTPException(status_code=400, detail="Пользователь уже в этой комнате")
    
    # Добавляем пользователя в комнату
    add_user_to_room(request.user_id, room_name)
    
    # Получаем активных пользователей в этой комнате
    active_users_data = get_active_users_in_room(room_name)
    active_users = []
    for active_user in active_users_data:
        active_users.append(User(
            id=active_user['user_id'],
            name=active_user['username'],
            active_rooms=[room_name],
            status="online"
        ))
    
    return {
        "message": f"Успешно присоединился к комнате '{room_name}'",
        "room": room_name,
        "user": User(
            id=user['id'],
            name=user['username'],
            active_rooms=[room_name],
            status="online"
        ),
        "active_users": active_users
    }


@app.get("/rooms/{room_name}/users", response_model=Dict, status_code=200, summary="Получить активных пользователей комнаты")
async def get_room_users(room_name: str):
    # Проверяем, существует ли комната
    if room_name not in get_all_rooms():
        raise HTTPException(status_code=404, detail="Комната не найдена")
    
    # Получаем активных пользователей
    active_users_data = get_active_users_in_room(room_name)
    active_users = []
    for user_data in active_users_data:
        active_users.append(User(
            id=user_data['user_id'],
            name=user_data['username'],
            active_rooms=[room_name],
            status="online"
        ))
    
    return {
        "room": room_name,
        "active_users": active_users,
        "count": len(active_users)
    }


@app.post("/rooms/{room_name}/leave", response_model=Dict, status_code=200, summary="Покинуть комнату")
async def leave_room(room_name: str, request: LeaveRoomRequest):
    # Проверяем, существует ли комната
    if room_name not in get_all_rooms():
        raise HTTPException(status_code=404, detail="Комната не найдена")
    
    # Проверяем, существует ли пользователь
    user = get_user_by_id(request.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    # Проверяем, находится ли пользователь в комнате
    if not is_user_in_room(request.user_id, room_name):
        raise HTTPException(status_code=400, detail="Пользователь не находится в этой комнате")
    
    # Удаляем пользователя из комнаты
    remove_user_from_room(request.user_id, room_name)
    
    # Определяем статус пользователя (если нет комнат - offline)
    user_rooms = get_user_rooms(request.user_id)
    user_status = "online" if user_rooms else "offline"
    active_rooms = [room['room_name'] for room in user_rooms]
    
    return {
        "message": f"Успешно покинул комнату '{room_name}'",
        "room": room_name,
        "user": User(
            id=user['id'],
            name=user['username'],
            active_rooms=active_rooms,
            status=user_status
        )
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env
load_dotenv()

# Получаем абсолютный путь к папке backend
BACKEND_DIR = os.path.dirname(__file__)

# Создаем абсолютный путь к базе данных в папке data
DATABASE_FILE = os.path.join(BACKEND_DIR, 'data', 'chat.db')
SECRET_KEY = os.getenv('SECRET_KEY', 'defaultsecret')
DEBUG = os.getenv('DEBUG', 'False') == 'True'
ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', '*').split(',')

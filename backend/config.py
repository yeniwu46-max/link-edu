import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()

DEFAULT_MYSQL_URL = (
    'mysql+pymysql://root:root@127.0.0.1:3306/link?charset=utf8mb4'
)


class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', DEFAULT_MYSQL_URL)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 3600,
    }
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'link-demo-change-me')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=8)
    SEED_ON_STARTUP = os.getenv('SEED_ON_STARTUP', 'true').lower() == 'true'
    DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '').strip()
    DEEPSEEK_BASE_URL = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com').strip().rstrip('/')
    DEEPSEEK_MODEL = os.getenv('DEEPSEEK_MODEL', 'deepseek-v4-flash').strip()
    DEEPSEEK_REASONING_EFFORT = os.getenv('DEEPSEEK_REASONING_EFFORT', 'high').strip()
    DEEPSEEK_TIMEOUT_SECONDS = float(os.getenv('DEEPSEEK_TIMEOUT_SECONDS', '60'))

    @staticmethod
    def is_mysql():
        return Config.SQLALCHEMY_DATABASE_URI.startswith('mysql')

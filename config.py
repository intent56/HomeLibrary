import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, ".env"))


class Config(object):
    # Определяет, включен ли режим отладки
    # В случае если включен, flask будет показывать
    # подробную отладочную информацию. Если выключен -
    # - 500 ошибку без какой либо дополнительной информации.
    DEBUG = False
    # Включение защиты против "Cross-site Request Forgery (CSRF)"
    CSRF_ENABLED = True
    SECRET_KEY = os.environ.get("SECRET_KEY") or "you-will-never-guess"
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "").replace(
        "postgres://", "postgresql://"
    ) or "sqlite:///" + os.path.join(basedir, "app.db")
    UPLOAD_FOLDER = "uploads"
    ITEMS_PER_PAGE_AGGREGATOR = 5
    ITEMS_PER_PAGE = 5
    ITEMS_PER_PAGE_BOOK = 5
    ITEMS_PER_PAGE_AUTHOR = 4
    ITEMS_PER_PAGE_INTERPRETER = 4
    ITEMS_PER_PAGE_PUBLISHER = 4
    ITEMS_PER_PAGE_GENRE = 4
    ITEMS_PER_PAGE_LANGUAGE = 4
    ITEMS_PER_PAGE_FORMAT = 5
    ITEMS_PER_PAGE_COVER = 5
    ITEMS_PER_PAGE_SOURCE = 5
    LOG_TO_STDOUT = os.environ.get("LOG_TO_STDOUT")
    BASE_DIR = basedir


class ProductionConfig(Config):
    DEBUG = False


class DevelopmentConfig(Config):
    DEVELOPMENT = True
    DEBUG = True

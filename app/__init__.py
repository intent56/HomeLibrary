from flask import Flask
from config import Config
from app.extensions import db, migrate, csrf
import base64


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    # Глобальный фильтр для кодирования в base64
    @app.template_filter('b64encode')
    def b64encode_filter(data):
        if data:
            return base64.b64encode(data).decode('utf-8')
        return ''

    from app.errors import bp as errors_bp
    app.register_blueprint(errors_bp)

    from app.api import api
    app.register_blueprint(api)

    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

# --- Доменные blueprint'ы ---
    from app.authors import bp as authors_bp
    app.register_blueprint(authors_bp)

    from app.publishers import bp as publishers_bp
    app.register_blueprint(publishers_bp)

    from app.genres import bp as genres_bp
    app.register_blueprint(genres_bp)

    from app.covers import bp as covers_bp
    app.register_blueprint(covers_bp)

    from app.formats import bp as formats_bp
    app.register_blueprint(formats_bp)

    from app.interpreters import bp as interpreters_bp
    app.register_blueprint(interpreters_bp)

    from app.languages import bp as languages_bp
    app.register_blueprint(languages_bp)

    return app

from app.models.main import (
    Book,
    Author,
    Format,
    Language,
    Cover,
    Genre,
    Publisher,
    Interpreter,
)

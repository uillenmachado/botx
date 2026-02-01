from flask import Flask, request
from .config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_babel import Babel
from flask_caching import Cache
from flask_login import LoginManager
from flask_restx import Api
from flask_wtf.csrf import CSRFProtect
from pythonjsonlogger import jsonlogger
import logging

db = SQLAlchemy()
migrate = Migrate()
cache = Cache()
login = LoginManager()
csrf = CSRFProtect()
api = Api(title="Twitter Bot API", version="1.0", doc="/api/docs", prefix="/api")


def get_locale():
    """Select best matching locale from request"""
    from flask import current_app
    return request.accept_languages.best_match(current_app.config['LANGUAGES'])


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(Config)

    # Structured logging
    handler = logging.StreamHandler()
    handler.setFormatter(jsonlogger.JsonFormatter())
    app.logger.addHandler(handler)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    cache.init_app(app)
    login.init_app(app)
    csrf.init_app(app)
    api.init_app(app)
    
    # Flask-Babel with locale selector
    babel = Babel(app, locale_selector=get_locale)

    # Register blueprints
    from .routes import core, auth, api_routes, bot_routes
    app.register_blueprint(core.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(bot_routes.bp)
    api_routes.init(api)

    # User loader for Flask-Login
    from .models import User
    
    @login.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    return app


from flask import Flask, request
from .config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_babel import Babel
from flask_caching import Cache
from flask_login import LoginManager
from flask_restx import Api
from pythonjsonlogger import jsonlogger
import logging, os

db=SQLAlchemy()
migrate=Migrate()
babel=Babel()
cache=Cache()
login=LoginManager()
api=Api(title="Twitter Bot API",version="1.0",doc="/docs")

def create_app():
    app=Flask(__name__,template_folder="templates",static_folder="static")
    app.config.from_object(Config)

    # structured logging
    handler=logging.StreamHandler()
    handler.setFormatter(jsonlogger.JsonFormatter())
    app.logger.addHandler(handler)

    db.init_app(app)
    migrate.init_app(app,db)
    babel.init_app(app)
    cache.init_app(app)
    login.init_app(app)
    api.init_app(app)

    from .routes import core, auth, api_routes
    app.register_blueprint(core.bp)
    app.register_blueprint(auth.bp)
    api_routes.init(api)

    @babel.localeselector
    def get_locale():
        return request.accept_languages.best_match(app.config['LANGUAGES'])

    return app

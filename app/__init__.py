from flask import Flask
from .config import Config
from .db import init_db
from .routes import bp as main_bp
from .metrics import metrics_bp
from flask_wtf.csrf import CSRFProtect

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    csrf = CSRFProtect(app)

    init_db(app.config['DATABASE'])

    app.register_blueprint(main_bp)
    app.register_blueprint(metrics_bp, url_prefix='/metrics')

    return app
import os
import secrets


class Config:
    # Security - use env var or generate persistent key
    SECRET_KEY = os.getenv("SECRET_KEY")
    if not SECRET_KEY:
        # In production, SECRET_KEY should always be set via environment
        # This fallback is for development only
        import warnings
        warnings.warn(
            "SECRET_KEY not set! Using random key. "
            "Sessions will be invalidated on restart. "
            "Set SECRET_KEY environment variable for production.",
            RuntimeWarning
        )
        SECRET_KEY = secrets.token_hex(32)
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URI", "sqlite:///bot.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Cache
    CACHE_TYPE = "RedisCache"
    CACHE_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CACHE_DEFAULT_TIMEOUT = 300
    
    # Internationalization
    LANGUAGES = ['pt', 'en']
    
    # Rate limiting
    RATELIMIT = int(os.getenv("RATELIMIT", 25))
    RATELIMIT_WINDOW = int(os.getenv("RATELIMIT_WINDOW", 86400))  # 24 hours
    
    # Environment
    ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
    DEBUG = ENVIRONMENT == "development"
    
    # Upload settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")

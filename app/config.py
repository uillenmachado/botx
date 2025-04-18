import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", os.urandom(24).hex())
    ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
    DEBUG = ENVIRONMENT == "development"
    DATABASE = os.getenv("DATABASE_URI", "bot.db")
    RATE_LIMIT = int(os.getenv("RATE_LIMIT", "25"))
    RATE_WINDOW = int(os.getenv("RATE_WINDOW", "86400"))  # seconds
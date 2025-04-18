
import os
class Config:
    SECRET_KEY=os.getenv("SECRET_KEY",os.urandom(24).hex())
    SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URI","sqlite:///bot.db")
    SQLALCHEMY_TRACK_MODIFICATIONS=False
    CACHE_TYPE="SimpleCache"
    CACHE_DEFAULT_TIMEOUT=300
    LANGUAGES=['pt','en']
    RATELIMIT=25
    RATELIMIT_WINDOW=86400
    ENVIRONMENT=os.getenv("ENVIRONMENT","production")
    DEBUG=ENVIRONMENT=="development"

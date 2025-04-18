
from . import db
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model,UserMixin):
    id=db.Column(db.Integer,primary_key=True)
    username=db.Column(db.String(64),unique=True,nullable=False)
    password_hash=db.Column(db.String(128),nullable=False)
    def set_password(self,password):
        self.password_hash=generate_password_hash(password)
    def check_password(self,p):return check_password_hash(self.password_hash,p)

class ScheduledPost(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    content=db.Column(db.Text,nullable=False)
    time=db.Column(db.String(5),nullable=False)
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    sent=db.Column(db.Boolean,default=False)

class PostHistory(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    content=db.Column(db.Text,nullable=False)
    tweet_id=db.Column(db.String(64))
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    likes=db.Column(db.Integer,default=0)
    retweets=db.Column(db.Integer,default=0)


class FailedPostQueue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    tries = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

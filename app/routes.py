import json, random, logging
from flask import Blueprint, request, jsonify, render_template, current_app
from datetime import datetime
from .twitter_client import TwitterClient
from .scheduler import add_job, cancel_job, jobs, run as run_scheduler
from .utils import with_retry
from .config import Config
import sqlite3, os

bp = Blueprint('main', __name__)
run_scheduler()

# init twitter client
tw_client = TwitterClient(Config.RATE_LIMIT, Config.RATE_WINDOW)

# load content pools
def load_pool(name):
    path=os.path.join(current_app.root_path,"content",name)
    with open(path,"r",encoding="utf-8") as f:
        return json.load(f)
PROVOCACOES = load_pool("provocacoes.json")
FRASES = load_pool("frases_impacto.json")
last_posts=[]

def generate_post(context=""):
    for _ in range(5):
        provoc = f"{context.capitalize()}? Desculpa, mas isso é conversa de vendedor de curso online." if context else random.choice(PROVOCACOES)
        impacto=random.choice(FRASES)
        post=f"{provoc}\n\n\"{impacto}\""
        if post not in last_posts:
            last_posts.append(post)
            if len(last_posts)>5: last_posts.pop(0)
            return post
    return post

@bp.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@bp.route("/generate", methods=["POST"])
def generate():
    context=request.form.get("context","").strip()
    return jsonify({"post":generate_post(context)})

@bp.route("/post", methods=["POST"])
def post_now():
    post=request.form.get("post","")
    if not post:
        return jsonify({"status":"error","message":"Post vazio."}),400
    result=tw_client.post_tweet(post)
    return jsonify(result), (200 if result["status"]=="success" else 429)

@bp.route("/schedule", methods=["POST"])
def schedule_post():
    post=request.form.get("post","")
    time_str=request.form.get("time","")
    if not (post and time_str):
        return jsonify({"status":"error","message":"Falha, dados ausentes."}),400
    add_job(post,time_str,tw_client.post_tweet)
    return jsonify({"status":"success","message":f"Agendado para {time_str}"}),200

@bp.route("/scheduled")
def view_scheduled():
    return jsonify(jobs)

@bp.route("/delete_scheduled", methods=["POST"])
def delete_scheduled():
    idx=request.form.get("index","")
    if not idx.isdigit(): return jsonify({"status":"error","message":"Índice inválido."}),400
    idx=int(idx)
    if idx<0 or idx>=len(jobs): return jsonify({"status":"error","message":"Fora do intervalo."}),400
    cancel_job(jobs[idx]["time"])
    jobs.pop(idx)
    return jsonify({"status":"success","message":"Removido."})
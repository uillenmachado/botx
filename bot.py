import os
import json
import random
import time
import schedule
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
from typing import List, Dict
from collections import deque

from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
from flask_wtf.csrf import CSRFProtect
import tweepy

# ------------------------------------------------------------------------------
# ENV & logging
# ------------------------------------------------------------------------------
load_dotenv()

# Logging (console + rotating file)
log_handler = RotatingFileHandler(
    "bot.log",
    maxBytes=1024 * 1024,  # 1 MB
    backupCount=5,
    encoding="utf-8",
)
console_handler = logging.StreamHandler()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[log_handler, console_handler],
)

# ------------------------------------------------------------------------------
# Flask + CSRF
# ------------------------------------------------------------------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", os.urandom(24).hex())
csrf = CSRFProtect(app)

# ------------------------------------------------------------------------------
# Twitter auth
# ------------------------------------------------------------------------------
API_KEY = os.getenv("API_KEY")
API_KEY_SECRET = os.getenv("API_KEY_SECRET")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("ACCESS_TOKEN_SECRET")

if not all([API_KEY, API_KEY_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET]):
    raise SystemExit("❌ Credenciais não encontradas no .env")

try:
    auth = tweepy.OAuthHandler(API_KEY, API_KEY_SECRET)
    auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    api = tweepy.API(auth)
    api.verify_credentials()
    logging.info("✅ Autenticado no X com sucesso.")
except Exception as exc:
    logging.exception("Erro de autenticação no X")
    raise SystemExit("Verifique suas credenciais.") from exc

# ------------------------------------------------------------------------------
# Content pools
# ------------------------------------------------------------------------------
def load_content(file_path: str, fallback: List[str]) -> List[str]:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logging.warning("Arquivo %s não encontrado, usando fallback.", file_path)
        return fallback

PROVOCACOES_FALLBACK = [
    "Empreender é fácil, né? Só acordar cedo, pagar boleto e rezar pra não falir."
]
FRASES_FALLBACK = ["Quem promete tudo geralmente entrega nada."]

PROVOCACOES = load_content("content/provocacoes.json", PROVOCACOES_FALLBACK)
FRASES_IMPACTO = load_content("content/frases_impacto.json", FRASES_FALLBACK)

last_posts: List[str] = []

# ------------------------------------------------------------------------------
# Persistence utils
# ------------------------------------------------------------------------------
def load_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default

def save_json(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

scheduled_posts: List[Dict] = load_json("scheduled_posts.json", [])
post_count_data = load_json("post_count.json", {"count": 0, "date": datetime.now().isoformat()})
post_count = post_count_data["count"]
last_date = datetime.fromisoformat(post_count_data["date"])
if last_date.date() != datetime.now().date():
    post_count = 0

# ------------------------------------------------------------------------------
# Rate Limiter
# ------------------------------------------------------------------------------
class RateLimiter:
    def __init__(self, max_requests: int, time_window: int):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = deque()

    def can_request(self) -> bool:
        now = datetime.now()
        while self.requests and self.requests[0] < now - timedelta(seconds=self.time_window):
            self.requests.popleft()
        if len(self.requests) < self.max_requests:
            self.requests.append(now)
            return True
        return False

tweet_limiter = RateLimiter(25, 86400)  # 25 tweets / 24h

# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------
def generate_post(context: str = "") -> str:
    for _ in range(5):
        provocacao = (
            f"{context.capitalize()}? Desculpa, mas isso é conversa de vendedor de curso online."
            if context
            else random.choice(PROVOCACOES)
        )
        impacto = random.choice(FRASES_IMPACTO)
        post = f"{provocacao}\n\n\"{impacto}\""
        if post not in last_posts:
            last_posts.append(post)
            if len(last_posts) > 5:
                last_posts.pop(0)
            return post
    return post  # fallback

def save_post_count():
    save_json("post_count.json", {"count": post_count, "date": datetime.now().isoformat()})

def post_with_retry(content: str, max_retries: int = 3):
    retries = 0
    while retries < max_retries:
        try:
            return api.update_status(content)
        except tweepy.errors.TweepyException as e:
            if "rate limit" in str(e).lower():
                wait_time = min(60 * (2 ** retries), 15 * 60)
                logging.warning("Rate limit atingido, aguardando %ss...", wait_time)
                time.sleep(wait_time)
                retries += 1
            else:
                raise
    raise Exception("Falha após várias tentativas.")

def post_to_x(content: str) -> Dict:
    global post_count
    if len(content) > 280:
        return {"status": "error", "message": "Tweet excede 280 caracteres."}
    if not tweet_limiter.can_request():
        return {"status": "error", "message": "Limite diário de posts atingido."}
    try:
        post_with_retry(content)
        post_count += 1
        save_post_count()
        logging.info("📤 Tweet publicado. Total hoje: %s", post_count)
        return {"status": "success", "message": "Postado com sucesso!"}
    except Exception as exc:
        logging.exception("Falha ao postar")
        return {"status": "error", "message": str(exc)}

# ------------------------------------------------------------------------------
# Scheduler
# ------------------------------------------------------------------------------
def schedule_runner():
    while True:
        schedule.run_pending()
        time.sleep(30)

def save_scheduled_posts():
    save_json("scheduled_posts.json", scheduled_posts)

# re‑register jobs after restart
def register_job(item):
    schedule.every().day.at(item["time"]).do(lambda p=item["post"]: post_to_x(p))

for item in scheduled_posts:
    register_job(item)

# check missed posts (last 30 mins)
def check_missed_posts():
    now = datetime.now()
    for item in scheduled_posts:
        scheduled_time = datetime.strptime(item["time"], "%H:%M").replace(
            year=now.year, month=now.month, day=now.day
        )
        if scheduled_time < now and (now - scheduled_time).seconds < 1800:
            logging.info("Enviando post perdido das %s", item["time"])
            post_to_x(item["post"])

check_missed_posts()

# start scheduler thread
import threading

threading.Thread(target=schedule_runner, daemon=True).start()

# ------------------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------------------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/generate", methods=["POST"])
def generate():
    context = request.form.get("context", "").strip()
    return jsonify({"post": generate_post(context)})

@app.route("/post", methods=["POST"])
def post_route():
    post = request.form.get("post", "")
    if not post:
        return jsonify({"status": "error", "message": "Post vazio."}), 400
    return jsonify(post_to_x(post))

@app.route("/schedule", methods=["POST"])
def schedule_post():
    post = request.form.get("post", "")
    time_str = request.form.get("time", "")
    if not (post and time_str):
        return jsonify({"status": "error", "message": "Post ou horário ausente."}), 400
    register_job({"post": post, "time": time_str})
    scheduled_posts.append({"post": post, "time": time_str})
    save_scheduled_posts()
    logging.info("Novo post agendado para %s", time_str)
    return jsonify({"status": "success", "message": f"Post agendado para {time_str}!"})

@app.route("/scheduled")
def scheduled():
    return jsonify(scheduled_posts)

@app.route("/delete_scheduled", methods=["POST"])
def delete_scheduled():
    idx = request.form.get("index", "")
    if not idx.isdigit():
        return jsonify({"status": "error", "message": "Índice inválido."}), 400
    idx = int(idx)
    if idx < 0 or idx >= len(scheduled_posts):
        return jsonify({"status": "error", "message": "Índice fora do intervalo."}), 400
    item = scheduled_posts.pop(idx)
    save_scheduled_posts()
    # remove job with same time
    for job in list(schedule.jobs):
        if job.at_time == item["time"]:
            schedule.cancel_job(job)
    logging.info("Agendamento excluído (%s).", idx)
    return jsonify({"status": "success", "message": "Agendamento removido."})

@app.route("/history")
def history():
    try:
        tweets = api.user_timeline(count=20, tweet_mode="extended")
        return jsonify(
            [
                {"text": t.full_text, "date": t.created_at.isoformat()}
                for t in tweets
            ]
        )
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
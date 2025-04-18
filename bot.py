import os
import random
import logging
import threading
import time
import schedule
import json
from datetime import datetime
from typing import List, Dict
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
import tweepy

# ------------------------------------------------------------------------------
# Environment & logging
# ------------------------------------------------------------------------------
load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

# ------------------------------------------------------------------------------
# Twitter (X) authentication
# ------------------------------------------------------------------------------
API_KEY = os.getenv("API_KEY")
API_KEY_SECRET = os.getenv("API_KEY_SECRET")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("ACCESS_TOKEN_SECRET")

if not all([API_KEY, API_KEY_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET]):
    raise SystemExit("❌ Credenciais da API não encontradas no .env")

try:
    auth = tweepy.OAuthHandler(API_KEY, API_KEY_SECRET)
    auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    api = tweepy.API(auth)
    api.verify_credentials()
    logging.info("✅ Autenticado com sucesso na API do X.")
except Exception as exc:
    logging.error("❌ Falha na autenticação: %s", exc)
    raise SystemExit("Verifique suas credenciais.")

# ------------------------------------------------------------------------------
# Flask app
# ------------------------------------------------------------------------------
app = Flask(__name__)

# ------------------------------------------------------------------------------
# Content pools
# ------------------------------------------------------------------------------
PROVOCACOES: List[str] = [
    "Empreender é fácil, né? Só acordar cedo, pagar boleto e rezar pra não falir.",
    "Dinheiro rápido, vida perfeita, zero problemas... Conheço esse comercial.",
    "Guru te ensina a ficar rico em 3 passos. Passo 1: pague o curso dele.",
    "Liberdade financeira em 6 meses? Só se for vendendo ilusão no Instagram.",
    "Todo mundo é CEO na bio. Na vida real, o boleto manda.",
    "Sucesso garantido, carro de luxo, praia todo dia... Parece golpe? É.",
    "O Brasil adora um herói de rede social. Pena que a realidade dá soco.",
    "Investiu tudo na promessa de 10% ao mês? Parabéns, você é o produto.",
    "Acharam a fórmula da felicidade eterna. Spoiler: não funciona.",
    "Trabalhe 4 horas por semana e seja milionário. Quem vende isso já é.",
    "Se guru fosse bom, vendia peixe, não curso milagroso.",
    "Enquanto você dorme, o boleto sonha em vencer você.",
    "Pitch perfeito? Só se for no universo paralelo do Instagram.",
    "Ganho 6 dígitos por mês! Mas esqueceu de falar que é em centavos.",
    "Startup de um homem só: CEO, CFO, COO e contagem regressiva pra falir."
]

FRASES_IMPACTO: List[str] = [
    "Quem promete tudo geralmente entrega nada.",
    "O maior risco é acreditar em atalhos.",
    "Quando o sonho é barato, o custo é você.",
    "A verdade dói, mas a ilusão mata.",
    "Ninguém fica rico vendendo honestidade.",
    "O ego grita, a realidade sussurra.",
    "Promessas grandes, bolsos vazios.",
    "A lama é mais honesta que o discurso bonito.",
    "Você não compra sucesso. Você paga por ele.",
    "A vida não tem CTRL+Z.",
    "Mentiras vendem. Verdades constroem.",
    "Atalho até existe: chama-se desilusão.",
    "O palco é lindo, mas o bastidor fede.",
    "Sonhar é de graça, acordar custa caro."
]

# ------------------------------------------------------------------------------
# Utils: Persistence
# ------------------------------------------------------------------------------
SCHEDULED_FILE = "scheduled_posts.json"

def load_scheduled_posts() -> List[Dict]:
    try:
        with open(SCHEDULED_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_scheduled_posts() -> None:
    with open(SCHEDULED_FILE, "w", encoding="utf-8") as f:
        json.dump(scheduled_posts, f, ensure_ascii=False, indent=2)

# ------------------------------------------------------------------------------
# State
# ------------------------------------------------------------------------------
scheduled_posts: List[Dict] = load_scheduled_posts()
last_posts: List[str] = []
post_count: int = 0  # resets on restart

# ------------------------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------------------------
def generate_post(context: str = "") -> str:
    """Generate a unique sarcastic post."""
    global last_posts
    for _ in range(5):
        if context:
            provocacao = f"{context.capitalize()}? Desculpa, mas isso é conversa de vendedor de curso online."
        else:
            provocacao = random.choice(PROVOCACOES)
        impacto = random.choice(FRASES_IMPACTO)
        post = f"{provocacao}\n\n\"{impacto}\""
        if post not in last_posts:
            last_posts.append(post)
            if len(last_posts) > 5:
                last_posts.pop(0)
            return post
    return post  # fallback (possibly repeated)

def post_to_x(content: str) -> Dict:
    """Publish a tweet and handle common errors."""
    global post_count
    DAILY_LIMIT = 25
    if len(content) > 280:
        return {"status": "error", "message": "Tweet excede 280 caracteres."}
    if post_count >= DAILY_LIMIT:
        return {"status": "error", "message": "Limite diário de posts atingido."}
    try:
        api.update_status(content)
        post_count += 1
        logging.info("📤 Post #%s publicado.", post_count)
        return {"status": "success", "message": "Postado com sucesso!"}
    except tweepy.errors.TweepyException as e:
        msg_lower = str(e).lower()
        if "duplicate" in msg_lower:
            return {"status": "error", "message": "Tweet duplicado. Tente algo diferente."}
        elif "auth" in msg_lower:
            return {"status": "error", "message": "Erro de autenticação. Verifique as credenciais."}
        else:
            logging.exception("Erro no Twitter")
            return {"status": "error", "message": f"Erro do Twitter: {str(e)}"}
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

# Recarrega agendamentos do arquivo
for item in scheduled_posts:
    schedule.every().day.at(item["time"]).do(lambda p=item["post"]: post_to_x(p))

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
    post = generate_post(context)
    return jsonify({"post": post})

@app.route("/post", methods=["POST"])
def post_now():
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
    try:
        schedule.every().day.at(time_str).do(lambda p=post: post_to_x(p))
        scheduled_posts.append({"post": post, "time": time_str})
        save_scheduled_posts()
        logging.info("🗓️ Post agendado para %s", time_str)
        return jsonify({"status": "success", "message": f"Post agendado para {time_str}!"})
    except Exception as exc:
        logging.exception("Falha ao agendar post")
        return jsonify({"status": "error", "message": str(exc)}), 500

@app.route("/scheduled")
def view_scheduled():
    return jsonify(scheduled_posts)

# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
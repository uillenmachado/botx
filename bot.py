import os
import random
import logging
import threading
import time
import schedule
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
import tweepy

# ------------------------------------------------------------------------------
# Initial setup
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
try:
    auth = tweepy.OAuthHandler(os.getenv("API_KEY"), os.getenv("API_SECRET"))
    auth.set_access_token(os.getenv("ACCESS_TOKEN"), os.getenv("ACCESS_TOKEN_SECRET"))
    api = tweepy.API(auth)
    api.verify_credentials()
    logging.info("✅ Authenticated with X API successfully.")
except Exception as exc:
    logging.error("❌ Failed to authenticate with X: %s", exc)
    raise SystemExit("Check your API credentials.")

# ------------------------------------------------------------------------------
# Flask application setup
# ------------------------------------------------------------------------------
app = Flask(__name__)

# ------------------------------------------------------------------------------
# Content pools
# ------------------------------------------------------------------------------

PROVOCACOES = [
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
]

FRASES_IMPACTO = [
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
]

# ------------------------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------------------------
def generate_post(context: str = "") -> str:
    """Generate a sarcastic post in Portuguese."""
    if context:
        provocacao = f"{context.capitalize()}? Desculpa, mas isso é conversa de vendedor de curso online."
    else:
        provocacao = random.choice(PROVOCACOES)
    impacto = random.choice(FRASES_IMPACTO)
    return f"{provocacao}\n\n\"{impacto}\""

def post_to_x(content: str) -> dict:
    """Publish a tweet. Returns a dict with operation status."""
    try:
        api.update_status(content)
        logging.info("📤 Post published to X.")
        return {"status": "success", "message": "Postado com sucesso!"}
    except Exception as exc:
        logging.exception("Failed to post to X")
        return {"status": "error", "message": str(exc)}

# ------------------------------------------------------------------------------
# Scheduler setup
# ------------------------------------------------------------------------------
scheduled_posts = []

def run_schedule() -> None:
    """Continuously run pending scheduled tasks in a background thread."""
    while True:
        schedule.run_pending()
        time.sleep(30)

threading.Thread(target=run_schedule, daemon=True).start()

# ------------------------------------------------------------------------------
# Flask routes
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
        schedule.every().day.at(time_str).do(lambda: post_to_x(post))
        scheduled_posts.append({"post": post, "time": time_str})
        logging.info("🗓️ Post agendado para %s", time_str)
        return jsonify({"status": "success", "message": f"Post agendado para {time_str}!"})
    except Exception as exc:
        logging.exception("Failed to schedule post")
        return jsonify({"status": "error", "message": str(exc)}), 500

@app.route("/scheduled")
def view_scheduled():
    """Return the list of scheduled posts."""
    return jsonify(scheduled_posts)

# ------------------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    # NOTE: In production, use a proper WSGI server like Gunicorn.
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
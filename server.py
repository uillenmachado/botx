# server.py
"""
Servidor Flask para gerenciar o Bot X via interface web de forma simples e amigável.

Como usar:
1) pip install flask
2) python server.py
3) Acesse http://127.0.0.1:5000 no navegador.

Autor: [Seu Nome / Ajustes]
"""

import logging
import sys
from flask import Flask, request, jsonify, render_template # type: ignore

# Configura log no console
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

# Importações das funções que já existem no seu projeto
from post_manager import (
    create_post, get_post_list, approve_post, edit_post, delete_post,
    schedule_post, get_stats
)

app = Flask(__name__)

@app.route("/")
def index():
    """Carrega a página inicial (index.html)"""
    return render_template("index.html")

# --------------------------------------------------
#                 R O T A S   D E   A P I
# --------------------------------------------------

@app.route("/api/create_post", methods=["POST"])
def api_create_post():
    """Cria uma nova postagem com texto e horário."""
    data = request.json
    text = data.get("text", "")
    time_ = data.get("time", "now")
    success, message = create_post(text, time_)
    return jsonify({"success": success, "message": message})

@app.route("/api/list_posts", methods=["GET"])
def api_list_posts():
    """Lista postagens (all / pending / approved / scheduled / history)."""
    status = request.args.get("status", "all")
    posts = get_post_list(status)
    return jsonify({"posts": posts})

@app.route("/api/approve_post", methods=["POST"])
def api_approve_post():
    """Aprova ou rejeita uma postagem pendente."""
    data = request.json
    index = data.get("index", 0)
    do_approve = data.get("approve", True)
    new_time = data.get("new_time", None)
    success, message, post_data = approve_post(index, do_approve, new_time)
    return jsonify({"success": success, "message": message})

@app.route("/api/edit_post", methods=["POST"])
def api_edit_post():
    """Edita o texto/horário de uma postagem, em um status específico."""
    data = request.json
    index = data.get("index", 0)
    status = data.get("status", "pending")  # pending, approved ou scheduled
    new_text = data.get("new_text")
    new_time = data.get("new_time")
    success, message = edit_post(index, new_text, new_time, status)
    return jsonify({"success": success, "message": message})

@app.route("/api/delete_post", methods=["POST"])
def api_delete_post():
    """Deleta uma postagem em um status (pending, approved ou scheduled)."""
    data = request.json
    index = data.get("index", 0)
    status = data.get("status", "pending")
    success, message = delete_post(index, status)
    return jsonify({"success": success, "message": message})

@app.route("/api/schedule_post", methods=["POST"])
def api_schedule_post():
    """Agenda (ou remove agendamento) para um post aprovado."""
    data = request.json
    index = data.get("index", 0)
    scheduled = data.get("scheduled", True)
    success, message, post_data = schedule_post(index, scheduled)
    return jsonify({"success": success, "message": message})

@app.route("/api/get_stats", methods=["GET"])
def api_get_stats():
    """Retorna estatísticas gerais: total em cada status, posts hoje, etc."""
    stats = get_stats()
    return jsonify(stats)

# --------------------------------------------------
#              I N I C I A R   S E R V I D O R
# --------------------------------------------------
if __name__ == "__main__":
    # Executa o servidor Flask na porta 5000 (padrão). 
    # Abra no navegador: http://127.0.0.1:5000
    app.run(debug=True, port=5000)

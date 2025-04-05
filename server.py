#!/usr/bin/env python3
"""
Servidor Flask para BotX - Interface web para gerenciamento de posts no X (Twitter)

Este módulo implementa um servidor web Flask que complementa a interface CLI
do BotX, permitindo gerenciar postagens através de uma interface web amigável.
O servidor se integra com o sistema de banco de dados SQLite e as funções
principais do bot.

Recursos principais:
- Interface web responsiva e intuitiva
- API RESTful para operações de CRUD de postagens
- Integração direta com o bot principal
- Suporte para visualização e gerenciamento de todas as postagens
- Dashboard com estatísticas

Uso:
    python bot.py --web           # Inicia o bot com interface web
    python server.py              # Inicia apenas o servidor web

Autor: Uillen Machado (com melhorias)
Repositório: github.com/uillenmachado/botx
"""

import os
import sys
import logging
import json
import webbrowser
import threading
import time
from pathlib import Path
from datetime import datetime

# Importações explícitas de Flask
try:
    from flask import Flask, request, jsonify, render_template, send_from_directory
except ImportError:
    print("Erro: Flask não está instalado. Execute 'python setup.py' para instalar dependências.")
    sys.exit(1)

# Determina o diretório base (onde o server.py está localizado)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Configura path para importações de módulos locais
sys.path.append(BASE_DIR)

# Configura logging
logger = logging.getLogger(__name__)

# Importa configurações do projeto
try:
    from config import (
        WEB_HOST, WEB_PORT, DEBUG_MODE, 
        TEMPLATES_DIR, STATIC_DIR, TIMEZONE_OBJ
    )
except ImportError as e:
    print(f"Erro ao importar configurações: {e}")
    print("Certifique-se de que o arquivo config.py está no mesmo diretório.")
    sys.exit(1)

# Inicializa o aplicativo Flask
app = Flask(
    __name__,
    template_folder=TEMPLATES_DIR,
    static_folder=STATIC_DIR
)

# Configuração para lidar com erros JSON
app.config["JSONIFY_PRETTYPRINT_REGULAR"] = True
app.config["JSON_SORT_KEYS"] = False  # Mantem a ordem das chaves na resposta JSON
app.config["PROPAGATE_EXCEPTIONS"] = not DEBUG_MODE  # Em produção, não propaga exceções

# Variável global para armazenar referência ao objeto bot quando iniciado via bot.py
bot_instance = None

# Importações explícitas para os módulos do bot
# Estas serão usadas apenas quando necessário, através de importação condicional
# para evitar importações dinâmicas problemáticas
from bot import DatabaseManager, PostManager
import twitter_api

# =============================================================================
# Rotas para servir arquivos estáticos e templates
# =============================================================================

@app.route("/")
def index():
    """Rota principal que serve a página inicial."""
    try:
        # Verifica se existe o diretório templates e o arquivo index.html
        index_path = os.path.join(TEMPLATES_DIR, "index.html")
        if not os.path.exists(index_path):
            return render_fallback_page()
        
        return render_template("index.html")
    except Exception as e:
        logger.error(f"Erro ao renderizar página inicial: {e}")
        return render_fallback_page()

def render_fallback_page():
    """Renderiza uma página HTML simples quando o template não é encontrado."""
    html_content = """
    <!DOCTYPE html>
    <html lang="pt-br">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>BotX - Página Inicial</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f0f2f5; }
            .container { max-width: 800px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            h1 { color: #1da1f2; }
            .notice { background-color: #ffeeba; padding: 15px; border-radius: 5px; margin: 15px 0; }
            .btn { display: inline-block; background-color: #1da1f2; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px; margin-top: 15px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>BotX - Gerenciador de Postagens para X (Twitter)</h1>
            <p>Bem-vindo à interface web do BotX!</p>
            
            <div class="notice">
                <strong>Aviso:</strong> O template index.html não foi encontrado.
                <p>Verifique se o diretório 'templates' existe e contém o arquivo 'index.html'.</p>
            </div>
            
            <p>Para iniciar o bot com a interface web completa, execute:</p>
            <pre>python bot.py --web</pre>
            
            <a href="/api/get_stats" class="btn">Ver Estatísticas (JSON)</a>
        </div>
    </body>
    </html>
    """
    return html_content

# =============================================================================
# API Endpoints
# =============================================================================

@app.route("/api/create_post", methods=["POST"])
def api_create_post():
    """
    Cria uma nova postagem.
    
    Request body:
        text (str): Texto da postagem
        time (str): Horário da postagem (formato HH:MM ou "now")
        
    Returns:
        json: Resultado da operação
    """
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "message": "Dados da requisição inválidos ou ausentes"}), 400
        
        text = data.get("text", "").strip()
        time_str = data.get("time", "now").strip()
        
        if not text:
            return jsonify({"success": False, "message": "O texto da postagem não pode estar vazio"}), 400
        
        # Se o bot está disponível, usa a instância
        if bot_instance and hasattr(bot_instance, "post_manager"):
            success, message, post = bot_instance.post_manager.create_post(text, time_str)
            return jsonify({"success": success, "message": message, "post": post})
        
        # Fallback para o modo standalone (sem bot.py)
        try:
            # Inicializa conexão local com o banco
            db_manager = DatabaseManager()
            post_manager = PostManager(db_manager)
            
            # Cria o post
            success, message, post = post_manager.create_post(text, time_str)
            
            # Fecha a conexão
            db_manager.close()
            
            return jsonify({"success": success, "message": message, "post": post})
        except Exception as e:
            logger.error(f"Erro ao criar postagem em modo standalone: {e}")
            return jsonify({
                "success": False, 
                "message": f"Erro interno do servidor: {str(e)}"
            }), 500
    
    except Exception as e:
        logger.error(f"Erro ao criar postagem: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Erro ao processar solicitação: {str(e)}"}), 500

@app.route("/api/list_posts", methods=["GET"])
def api_list_posts():
    """
    Lista as postagens com base no status solicitado.
    
    Query parameters:
        status (str): Status das postagens (all, pending, approved, scheduled, history)
        limit (int, optional): Limite de postagens a serem retornadas
        
    Returns:
        json: Lista de postagens
    """
    try:
        status = request.args.get("status", "all")
        limit_str = request.args.get("limit", "")
        limit = int(limit_str) if limit_str.isdigit() else None
        
        # Se o bot está disponível, usa a instância
        if bot_instance and hasattr(bot_instance, "post_manager"):
            posts = bot_instance.post_manager.get_posts(status, limit)
            return jsonify({"success": True, "posts": format_posts_for_display(posts)})
        
        # Fallback para o modo standalone (sem bot.py)
        try:
            # Inicializa conexão local com o banco
            db_manager = DatabaseManager()
            post_manager = PostManager(db_manager)
            
            # Obtém os posts
            posts = post_manager.get_posts(status, limit)
            
            # Fecha a conexão
            db_manager.close()
            
            return jsonify({"success": True, "posts": format_posts_for_display(posts)})
        except Exception as e:
            logger.error(f"Erro ao listar postagens em modo standalone: {e}")
            return jsonify({
                "success": False, 
                "message": f"Erro interno do servidor: {str(e)}",
                "posts": []
            }), 500
    
    except Exception as e:
        logger.error(f"Erro ao listar postagens: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Erro ao processar solicitação: {str(e)}", "posts": []}), 500

def format_posts_for_display(posts):
    """
    Formata posts para exibição na interface web.
    
    Args:
        posts (list): Lista de posts recuperados do banco de dados
        
    Returns:
        list: Lista formatada de posts para exibição
    """
    if not posts:
        return []
    
    result = []
    for i, post in enumerate(posts):
        # Determina o status para exibição
        status_display = post.get("status", "unknown")
        
        # Formata datas para exibição
        created_at = format_date(post.get("created_at"))
        time_field = post.get("scheduled_time", "N/A")
        
        # Adiciona timestamp apropriado com base no status
        if status_display == "posted":
            time_info = f"Publicado: {format_date(post.get('posted_at'))}"
        elif status_display == "scheduled":
            time_info = f"Agendado: {time_field} | Criado: {created_at}"
        elif status_display == "approved":
            time_info = f"Aprovado: {format_date(post.get('approved_at'))} | Horário: {time_field}"
        else:  # pending
            time_info = f"Criado: {created_at} | Horário: {time_field}"
        
        # Formata o texto para exibição
        text = post.get("text", "")
        text_short = text[:60] + "..." if len(text) > 60 else text
        
        # Monta a string formatada
        post_id = post.get("id", "N/A")[:8]  # Primeiros 8 caracteres do ID
        formatted = f"{status_display.title()} #{i+1} [ID:{post_id}]: {text_short} | {time_info}"
        
        result.append(formatted)
    
    return result

def format_date(date_str):
    """
    Formata uma string de data ISO para exibição.
    
    Args:
        date_str (str): Data em formato ISO
        
    Returns:
        str: Data formatada ou 'N/A' se inválida
    """
    if not date_str:
        return "N/A"
    
    try:
        dt = datetime.fromisoformat(date_str)
        return dt.strftime("%d/%m/%Y %H:%M")
    except (ValueError, TypeError):
        return date_str

@app.route("/api/approve_post", methods=["POST"])
def api_approve_post():
    """
    Aprova ou rejeita uma postagem pendente.
    
    Request body:
        index (int): Índice da postagem (base 0)
        approve (bool): True para aprovar, False para rejeitar
        new_time (str, optional): Novo horário para a postagem
        
    Returns:
        json: Resultado da operação
    """
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "message": "Dados da requisição inválidos ou ausentes"}), 400
        
        post_index = data.get("index", 0)
        approve = data.get("approve", True)
        new_time = data.get("new_time")
        
        # Se o bot está disponível, usa a instância
        if bot_instance and hasattr(bot_instance, "post_manager"):
            success, message, post = bot_instance.post_manager.approve_post(post_index, approve, new_time)
            return jsonify({"success": success, "message": message, "post": post})
        
        # Fallback para o modo standalone
        try:
            db_manager = DatabaseManager()
            post_manager = PostManager(db_manager)
            
            success, message, post = post_manager.approve_post(post_index, approve, new_time)
            
            db_manager.close()
            
            return jsonify({"success": success, "message": message, "post": post})
        except Exception as e:
            logger.error(f"Erro ao aprovar/rejeitar postagem em modo standalone: {e}")
            return jsonify({
                "success": False, 
                "message": f"Erro interno do servidor: {str(e)}"
            }), 500
    
    except Exception as e:
        logger.error(f"Erro ao aprovar/rejeitar postagem: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Erro ao processar solicitação: {str(e)}"}), 500

@app.route("/api/edit_post", methods=["POST"])
def api_edit_post():
    """
    Edita uma postagem existente.
    
    Request body:
        index (int): Índice da postagem (base 0)
        status (str): Status atual da postagem (pending, approved, scheduled)
        new_text (str, optional): Novo texto para a postagem
        new_time (str, optional): Novo horário para a postagem
        
    Returns:
        json: Resultado da operação
    """
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "message": "Dados da requisição inválidos ou ausentes"}), 400
        
        post_index = data.get("index", 0)
        status = data.get("status", "pending")
        new_text = data.get("new_text")
        new_time = data.get("new_time")
        
        # Validação para não receber texto vazio
        if new_text is not None and not new_text.strip():
            return jsonify({"success": False, "message": "O texto da postagem não pode estar vazio"}), 400
        
        # Se o bot está disponível, usa a instância
        if bot_instance and hasattr(bot_instance, "post_manager"):
            # No bot refatorado, o edit_post agora usa ID do post em vez de índice
            # Primeiro precisamos buscar o post pelo índice no status específico
            posts = bot_instance.post_manager.get_posts(status)
            
            if post_index < 0 or post_index >= len(posts):
                return jsonify({"success": False, "message": f"Índice {post_index} inválido para status '{status}'"}), 400
            
            post = posts[post_index]
            
            # Agora podemos editar usando o ID
            success, message, updated_post = bot_instance.post_manager.edit_post(
                post["id"], 
                new_text=new_text,
                new_time=new_time
            )
            
            return jsonify({"success": success, "message": message, "post": updated_post})
        
        # Fallback para o modo standalone
        try:
            db_manager = DatabaseManager()
            post_manager = PostManager(db_manager)
            
            # Mesmo processo acima, para o modo standalone
            posts = post_manager.get_posts(status)
            
            if post_index < 0 or post_index >= len(posts):
                return jsonify({"success": False, "message": f"Índice {post_index} inválido para status '{status}'"}), 400
            
            post = posts[post_index]
            
            success, message, updated_post = post_manager.edit_post(
                post["id"],
                new_text=new_text,
                new_time=new_time
            )
            
            db_manager.close()
            
            return jsonify({"success": success, "message": message, "post": updated_post})
        except Exception as e:
            logger.error(f"Erro ao editar postagem em modo standalone: {e}")
            return jsonify({
                "success": False, 
                "message": f"Erro interno do servidor: {str(e)}"
            }), 500
    
    except Exception as e:
        logger.error(f"Erro ao editar postagem: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Erro ao processar solicitação: {str(e)}"}), 500

@app.route("/api/delete_post", methods=["POST"])
def api_delete_post():
    """
    Exclui uma postagem.
    
    Request body:
        index (int): Índice da postagem (base 0)
        status (str): Status atual da postagem (pending, approved, scheduled)
        
    Returns:
        json: Resultado da operação
    """
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "message": "Dados da requisição inválidos ou ausentes"}), 400
        
        post_index = data.get("index", 0)
        status = data.get("status", "pending")
        
        # Se o bot está disponível, usa a instância
        if bot_instance and hasattr(bot_instance, "post_manager"):
            # No bot refatorado, o delete_post agora usa ID do post em vez de índice
            # Primeiro precisamos buscar o post pelo índice no status específico
            posts = bot_instance.post_manager.get_posts(status)
            
            if post_index < 0 or post_index >= len(posts):
                return jsonify({"success": False, "message": f"Índice {post_index} inválido para status '{status}'"}), 400
            
            post = posts[post_index]
            
            # Agora podemos excluir usando o ID
            success, message = bot_instance.post_manager.delete_post(post["id"])
            
            return jsonify({"success": success, "message": message})
        
        # Fallback para o modo standalone
        try:
            db_manager = DatabaseManager()
            post_manager = PostManager(db_manager)
            
            # Mesmo processo acima, para o modo standalone
            posts = post_manager.get_posts(status)
            
            if post_index < 0 or post_index >= len(posts):
                return jsonify({"success": False, "message": f"Índice {post_index} inválido para status '{status}'"}), 400
            
            post = posts[post_index]
            
            success, message = post_manager.delete_post(post["id"])
            
            db_manager.close()
            
            return jsonify({"success": success, "message": message})
        except Exception as e:
            logger.error(f"Erro ao excluir postagem em modo standalone: {e}")
            return jsonify({
                "success": False, 
                "message": f"Erro interno do servidor: {str(e)}"
            }), 500
    
    except Exception as e:
        logger.error(f"Erro ao excluir postagem: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Erro ao processar solicitação: {str(e)}"}), 500

@app.route("/api/schedule_post", methods=["POST"])
def api_schedule_post():
    """
    Agenda ou desagenda uma postagem.
    
    Request body:
        index (int): Índice da postagem (base 0)
        scheduled (bool): True para agendar, False para desagendar
        
    Returns:
        json: Resultado da operação
    """
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "message": f"Índice {post_index} inválido para status '{search_status}'"}), 400
            
            post = posts[post_index]
            
            # Agenda ou desagenda usando o ID
            success, message, updated_post = bot_instance.post_manager.schedule_post(post["id"], scheduled)
            
            # Se agendou com sucesso e o bot está rodando, adiciona ao scheduler
            if success and scheduled and updated_post and hasattr(bot_instance, "scheduler"):
                try:
                    # Adiciona ao scheduler apenas se o horário não for 'now'
                    if updated_post["scheduled_time"].lower() != "now":
                        hour, minute = updated_post["scheduled_time"].split(':')
                        
                        bot_instance.scheduler.add_job(
                            bot_instance._post_scheduled_tweet,
                            'cron',
                            hour=int(hour),
                            minute=int(minute),
                            id=f"post_{updated_post['id']}",
                            args=[updated_post["id"]],
                            replace_existing=True
                        )
                        
                        message += f" Agendado para {updated_post['scheduled_time']}."
                except Exception as e:
                    logger.error(f"Erro ao adicionar job ao scheduler: {e}")
                    message += f" (Aviso: erro ao programar no scheduler)"
            
            return jsonify({"success": success, "message": message, "post": updated_post})
        
        # Fallback para o modo standalone
        try:
            db_manager = DatabaseManager()
            post_manager = PostManager(db_manager)
            
            # Mesmo processo acima, para o modo standalone
            search_status = "approved" if scheduled else "scheduled"
            posts = post_manager.get_posts(search_status)
            
            if post_index < 0 or post_index >= len(posts):
                return jsonify({"success": False, "message": f"Índice {post_index} inválido para status '{search_status}'"}), 400
            
            post = posts[post_index]
            
            success, message, updated_post = post_manager.schedule_post(post["id"], scheduled)
            
            db_manager.close()
            
            return jsonify({
                "success": success, 
                "message": message + " (Nota: bot não está rodando, será agendado quando o bot iniciar)", 
                "post": updated_post
            })
        except Exception as e:
            logger.error(f"Erro ao importar módulos do bot: {e}")
            return jsonify({
                "success": False, 
                "message": "Erro interno do servidor. Verifique os logs para mais detalhes."
            }), 500
    
    except Exception as e:
        logger.error(f"Erro ao agendar/desagendar postagem: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Erro ao processar solicitação: {str(e)}"}), 500

@app.route("/api/get_stats", methods=["GET"])
def api_get_stats():
    """
    Obtém estatísticas gerais do bot.
    
    Returns:
        json: Estatísticas do bot
    """
    try:
        # Se o bot está disponível, usa a instância
        if bot_instance and hasattr(bot_instance, "post_manager"):
            stats = bot_instance.post_manager.get_stats()
            
            # Adiciona informações adicionais se disponíveis
            if hasattr(bot_instance, "monthly_posts") and hasattr(bot_instance, "daily_posts"):
                stats["current_session"] = {
                    "daily_posts": bot_instance.daily_posts,
                    "monthly_posts": bot_instance.monthly_posts
                }
            
            # Adiciona informações do scheduler se disponível
            if hasattr(bot_instance, "scheduler"):
                jobs = bot_instance.scheduler.get_jobs()
                scheduled_jobs = [
                    {
                        "id": job.id,
                        "next_run": job.next_run_time.strftime("%Y-%m-%d %H:%M:%S") if job.next_run_time else "Paused",
                        "type": "scheduled_post" if job.id.startswith("post_") else "system"
                    }
                    for job in jobs
                ]
                
                stats["scheduler"] = {
                    "running": bot_instance.scheduler.running,
                    "jobs": scheduled_jobs,
                    "jobs_count": len(scheduled_jobs)
                }
            
            # Adiciona informações de tendências se disponível
            if hasattr(bot_instance, "trend_manager"):
                try:
                    trends, last_updated = bot_instance.trend_manager.get_trends(limit=5)
                    stats["trends"] = {
                        "items": trends,
                        "last_updated": last_updated.isoformat() if last_updated else None
                    }
                except Exception as e:
                    logger.error(f"Erro ao obter tendências: {e}")
            
            return jsonify(stats)
        
        # Fallback para o modo standalone
        try:
            db_manager = DatabaseManager()
            post_manager = PostManager(db_manager)
            
            stats = post_manager.get_stats()
            
            db_manager.close()
            
            # Adiciona mensagem no modo standalone
            stats["server_mode"] = "standalone"
            stats["note"] = "Limitado: servidor rodando sem bot.py. Para funcionalidade completa, inicie com: python bot.py --web"
            
            return jsonify(stats)
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas em modo standalone: {e}")
            return jsonify({
                "success": False, 
                "message": f"Erro interno do servidor: {str(e)}",
                "error": str(e)
            }), 500
    
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Erro ao processar solicitação: {str(e)}"}), 500

# =============================================================================
# API para integração com sistemas externos
# =============================================================================

@app.route("/api/health", methods=["GET"])
def api_health():
    """
    Endpoint para verificação de saúde do servidor.
    Útil para monitoramento e integração com outros sistemas.
    
    Returns:
        json: Estado de saúde do servidor e do bot
    """
    health = {
        "server": {
            "status": "online",
            "timestamp": datetime.now(TIMEZONE_OBJ).isoformat(),
            "version": "2.0.0"
        }
    }
    
    # Adiciona informações do bot se disponível
    if bot_instance:
        bot_health = {
            "status": "online" if getattr(bot_instance, "bot_running", False) else "offline",
            "scheduler_running": getattr(bot_instance.scheduler, "running", False) if hasattr(bot_instance, "scheduler") else False
        }
        
        # Adiciona estatísticas básicas
        if hasattr(bot_instance, "post_manager"):
            try:
                stats = bot_instance.post_manager.get_stats()
                bot_health["stats"] = {
                    "posts_today": stats.get("posts_today", 0),
                    "total_posts": stats.get("total_all", 0)
                }
            except Exception as e:
                logger.error(f"Erro ao obter estatísticas para health check: {e}")
        
        health["bot"] = bot_health
    else:
        health["bot"] = {"status": "disconnected"}
    
    return jsonify(health)

@app.route("/api/trends", methods=["GET"])
def api_trends():
    """
    Retorna as tendências atuais do X (Twitter).
    
    Query parameters:
        limit (int, optional): Limite de tendências a serem retornadas
        
    Returns:
        json: Lista de tendências
    """
    try:
        limit_str = request.args.get("limit", "")
        limit = int(limit_str) if limit_str.isdigit() else None
        
        # Se o bot está disponível, usa a instância
        if bot_instance and hasattr(bot_instance, "trend_manager"):
            trends, last_updated = bot_instance.trend_manager.get_trends(limit)
            
            return jsonify({
                "success": True,
                "trends": trends,
                "last_updated": last_updated.isoformat() if last_updated else None
            })
        
        # Fallback para o modo standalone usando importação explícita
        try:
            # Usando a importação direta de twitter_api
            trends, timestamp = twitter_api.get_trends()
            
            if limit and limit < len(trends):
                trends = trends[:limit]
            
            return jsonify({
                "success": True,
                "trends": trends,
                "last_updated": timestamp.isoformat() if timestamp else None
            })
        except Exception as e:
            logger.error(f"Erro ao obter tendências em modo standalone: {e}")
            return jsonify({
                "success": False,
                "message": "Erro ao acessar API do Twitter em modo standalone.",
                "error": str(e)
            }), 500
    
    except Exception as e:
        logger.error(f"Erro ao obter tendências: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "message": f"Erro ao processar solicitação: {str(e)}"
        }), 500

# =============================================================================
# Funções do servidor
# =============================================================================

def start_server(bot=None, host=WEB_HOST, port=WEB_PORT, open_browser=True):
    """
    Inicia o servidor Flask.
    
    Args:
        bot (BotX, optional): Instância do bot para integração
        host (str): Host para o servidor (ex: 127.0.0.1)
        port (int): Porta para o servidor (ex: 5000)
        open_browser (bool): Se True, abre o navegador automaticamente
    """
    global bot_instance
    
    # Armazena a referência ao bot para uso em todas as rotas
    bot_instance = bot
    
    # Cria diretórios necessários se não existirem
    os.makedirs(TEMPLATES_DIR, exist_ok=True)
    os.makedirs(STATIC_DIR, exist_ok=True)
    
    # Verifica se precisa copiar o template index.html
    index_path = os.path.join(TEMPLATES_DIR, "index.html")
    if not os.path.exists(index_path):
        # Tenta copiar o template padrão disponível no pacote
        try:
            default_template = os.path.join(BASE_DIR, "templates", "index.html")
            if os.path.exists(default_template):
                import shutil
                shutil.copy2(default_template, index_path)
                logger.info(f"Template index.html copiado para {index_path}")
        except Exception as e:
            logger.warning(f"Não foi possível copiar o template padrão: {e}")
    
    # URL para acesso
    url = f"http://{host}:{port}"
    
    # Configuração de log
    logger.info(f"Iniciando servidor web em {url}")
    
    # Abre o navegador em uma thread separada após um pequeno delay
    if open_browser:
        def open_browser_with_delay():
            time.sleep(1.5)  # Pequeno delay para dar tempo do servidor iniciar
            webbrowser.open(url)
            logger.info(f"Navegador aberto em {url}")
        
        threading.Thread(target=open_browser_with_delay, daemon=True).start()
    
    # Inicia o servidor Flask
    try:
        app.run(host=host, port=port, debug=DEBUG_MODE, use_reloader=False)
    except Exception as e:
        logger.error(f"Erro ao iniciar servidor Flask: {e}")
        
        # Tenta iniciar em outra porta se a principal estiver ocupada
        if "Address already in use" in str(e):
            new_port = port + 1
            logger.info(f"Porta {port} em uso. Tentando porta alternativa {new_port}.")
            
            try:
                new_url = f"http://{host}:{new_port}"
                
                # Se abrir navegador, redireciona para a nova porta
                if open_browser:
                    threading.Thread(target=lambda: (time.sleep(1.5), webbrowser.open(new_url)), daemon=True).start()
                
                app.run(host=host, port=new_port, debug=DEBUG_MODE, use_reloader=False)
            except Exception as secondary_error:
                logger.error(f"Erro ao iniciar servidor na porta alternativa: {secondary_error}")
                raise
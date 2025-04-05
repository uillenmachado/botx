#!/usr/bin/env python3
"""
Bot para X (Twitter) - Interface interativa e lógica principal

Este módulo implementa o dashboard interativo no terminal e a lógica principal
do bot, incluindo o agendamento de posts, loop de execução e integração com o
servidor web Flask opcional.

Recursos principais:
- Interface CLI colorida e intuitiva
- Agendamento de posts com APScheduler (persistente em SQLite)
- Gestão de posts por banco de dados SQLite
- Integração com API do Twitter/X
- Integração opcional com interface web (Flask)

Uso:
    python bot.py          # Inicia o bot em modo normal
    python bot.py --help   # Exibe ajuda
    python bot.py --web    # Inicia o bot com interface web

Autor: Uillen Machado (com melhorias)
Repositório: github.com/uillenmachado/botx
"""

import os
import sys
import time
import logging
import argparse
import threading
import textwrap
import sqlite3
import json
from datetime import datetime, timedelta
import signal
import importlib
import webbrowser
from pathlib import Path

# Determina o diretório base (onde o bot.py está localizado)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Importa utilitários e configurações
try:
    # Tenta importar colorama para suporte a cores no terminal
    from colorama import init, Fore, Style # type: ignore
    init()  # Inicializa o colorama
    
    # Define cores
    COLOR_INFO = Fore.CYAN
    COLOR_SUCCESS = Fore.GREEN
    COLOR_WARNING = Fore.YELLOW
    COLOR_ERROR = Fore.RED
    COLOR_HEADER = Fore.MAGENTA
    COLOR_RESET = Style.RESET_ALL
    
    # Flag para indicar que colorama está disponível
    HAS_COLORS = True
except ImportError:
    # Fallback sem cores se colorama não estiver disponível
    COLOR_INFO = ""
    COLOR_SUCCESS = ""
    COLOR_WARNING = ""
    COLOR_ERROR = ""
    COLOR_HEADER = ""
    COLOR_RESET = ""
    HAS_COLORS = False

# Verifica dependências
try:
    # Scheduler para agendamento de tarefas (APScheduler)
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
    from apscheduler.executors.pool import ThreadPoolExecutor
    
    # Flag para indicar que todas as dependências estão disponíveis
    DEPENDENCIES_OK = True
except ImportError as e:
    print(f"ERRO: Dependência não encontrada: {e}")
    print("Execute 'python setup.py' para instalar todas as dependências.")
    DEPENDENCIES_OK = False
    if input("Deseja continuar mesmo assim? (s/n): ").lower() != 's':
        sys.exit(1)

# Importa configurações e módulos locais
sys.path.append(BASE_DIR)
try:
    from config import (
        API_KEY, API_KEY_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET, BEARER_TOKEN,
        LOG_FILE, LOG_DIR, DB_FILE, POSTS_FILE, TEMPLATES_DIR, STATIC_DIR,
        POST_INTERVAL_MINUTES, APPROVE_TIMEOUT, DAILY_POST_LIMIT, MONTHLY_POST_LIMIT,
        TREND_UPDATE_HOUR, DATE_FORMAT, WOEID_GLOBAL, MAX_TWEET_LENGTH,
        COLOR_INFO as CONFIG_COLOR_INFO, COLOR_SUCCESS as CONFIG_COLOR_SUCCESS,
        COLOR_WARNING as CONFIG_COLOR_WARNING, COLOR_ERROR as CONFIG_COLOR_ERROR,
        COLOR_HEADER as CONFIG_COLOR_HEADER, COLOR_NORMAL as CONFIG_COLOR_NORMAL,
        SCHEDULER_MISFIRE_GRACE_TIME, SCHEDULER_COALESCE, SCHEDULER_MAX_INSTANCES,
        WEB_HOST, WEB_PORT, DEBUG_MODE
    )
    from twitter_api import (
        initialize_api, get_trends, post_tweet, get_user_info,
        check_api_limits, health_check
    )
except ImportError as e:
    print(f"ERRO: Não foi possível importar módulos locais: {e}")
    print("Certifique-se de que os arquivos config.py e twitter_api.py estão no mesmo diretório.")
    sys.exit(1)

# Configura o logger
logger = logging.getLogger(__name__)

# =============================================================================
# Configuração de CLI com argparse
# =============================================================================

def parse_arguments():
    """
    Analisa os argumentos de linha de comando.
    
    Returns:
        argparse.Namespace: Objeto com argumentos processados
    """
    parser = argparse.ArgumentParser(
        description="BotX - Bot para automação de postagens no Twitter/X",
        epilog="Para mais informações, visite github.com/uillenmachado/botx"
    )
    
    parser.add_argument(
        "--web", action="store_true",
        help="Inicia o bot com interface web"
    )
    
    parser.add_argument(
        "--port", type=int, default=WEB_PORT,
        help=f"Porta para a interface web (padrão: {WEB_PORT})"
    )
    
    parser.add_argument(
        "--host", type=str, default=WEB_HOST,
        help=f"Host para a interface web (padrão: {WEB_HOST})"
    )
    
    parser.add_argument(
        "--debug", action="store_true",
        help="Ativa o modo de debug"
    )
    
    parser.add_argument(
        "--no-browser", action="store_true",
        help="Não abre o navegador automaticamente ao iniciar o servidor web"
    )
    
    return parser.parse_args()

# =============================================================================
# Classes de banco de dados (SQLite)
# =============================================================================

class DatabaseManager:
    """
    Gerencia a conexão com o banco de dados SQLite e operações relacionadas.
    """
    
    def __init__(self, db_file=DB_FILE):
        """
        Inicializa o gerenciador de banco de dados.
        
        Args:
            db_file (str): Caminho para o arquivo de banco de dados SQLite
        """
        self.db_file = db_file
        self.connection = None
        self.cursor = None
        self.lock = threading.Lock()
        
        # Verifica se o banco de dados existe
        if not os.path.exists(db_file):
            logger.warning(f"Banco de dados não encontrado em {db_file}. Criando novo banco de dados.")
            self.initialize_database()
        
        # Tenta se conectar ao banco de dados
        try:
            self.connect()
        except Exception as e:
            logger.error(f"Erro ao conectar ao banco de dados: {e}")
            raise
    
    def connect(self):
        """
        Conecta ao banco de dados SQLite.
        
        Returns:
            sqlite3.Connection: Conexão com o banco de dados
        """
        try:
            self.connection = sqlite3.connect(
                self.db_file,
                timeout=30,  # Timeout em segundos
                check_same_thread=False  # Permite acesso de múltiplas threads
            )
            
            # Configura a conexão para retornar rows como dicionários
            self.connection.row_factory = sqlite3.Row
            
            # Habilita chaves estrangeiras
            self.cursor = self.connection.cursor()
            self.cursor.execute("PRAGMA foreign_keys = ON")
            
            logger.info(f"Conectado ao banco de dados: {self.db_file}")
            return self.connection
        except Exception as e:
            logger.error(f"Erro ao conectar ao banco de dados: {e}")
            raise
    
    def close(self):
        """Fecha a conexão com o banco de dados."""
        if self.connection:
            self.connection.close()
            logger.info("Conexão com o banco de dados fechada.")
    
    def initialize_database(self):
        """
        Inicializa o banco de dados criando as tabelas necessárias.
        """
        # Tenta criar o diretório do banco de dados se não existir
        os.makedirs(os.path.dirname(self.db_file), exist_ok=True)
        
        try:
            # Conecta ao banco de dados (cria o arquivo se não existir)
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # Cria tabela de posts
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS posts (
                id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                scheduled_time TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                approved_at TEXT,
                scheduled_at TEXT,
                posted_at TEXT,
                edited_at TEXT
            )
            ''')
            
            # Cria tabela de tendências
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS trends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                volume INTEGER,
                timestamp TEXT NOT NULL
            )
            ''')
            
            # Cria tabela de estatísticas
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                daily_posts INTEGER DEFAULT 0,
                monthly_posts INTEGER DEFAULT 0,
                timestamp TEXT NOT NULL
            )
            ''')
            
            # Commit e fechamento
            conn.commit()
            conn.close()
            
            logger.info("Banco de dados inicializado com sucesso.")
        except Exception as e:
            logger.error(f"Erro ao inicializar banco de dados: {e}")
            raise
    
    def execute(self, query, params=None):
        """
        Executa uma consulta SQL com proteção contra race conditions.
        
        Args:
            query (str): Consulta SQL a ser executada
            params (tuple, optional): Parâmetros para a consulta
            
        Returns:
            sqlite3.Cursor: Cursor com resultados da consulta
        """
        with self.lock:
            try:
                if params:
                    return self.cursor.execute(query, params)
                else:
                    return self.cursor.execute(query)
            except sqlite3.Error as e:
                logger.error(f"Erro ao executar consulta SQL: {e}")
                logger.error(f"Consulta: {query}")
                logger.error(f"Parâmetros: {params}")
                
                # Tenta reconectar em caso de erro de banco de dados
                try:
                    self.connect()
                    # Tenta novamente após reconexão
                    if params:
                        return self.cursor.execute(query, params)
                    else:
                        return self.cursor.execute(query)
                except Exception as reconnect_error:
                    logger.error(f"Erro ao reconectar: {reconnect_error}")
                    raise
            except Exception as e:
                logger.error(f"Erro inesperado ao executar consulta SQL: {e}")
                raise
    
    def commit(self):
        """Commit das alterações no banco de dados."""
        with self.lock:
            try:
                self.connection.commit()
            except Exception as e:
                logger.error(f"Erro ao fazer commit: {e}")
                try:
                    self.connect()
                    self.connection.commit()
                except Exception as reconnect_error:
                    logger.error(f"Erro ao reconectar para commit: {reconnect_error}")
                    raise
    
    def fetchall(self):
        """
        Recupera todos os resultados da última consulta.
        
        Returns:
            list: Lista de resultados
        """
        return self.cursor.fetchall()
    
    def fetchone(self):
        """
        Recupera um resultado da última consulta.
        
        Returns:
            dict or None: Resultado ou None se não houver resultados
        """
        return self.cursor.fetchone()

class PostManager:
    """
    Gerencia todas as operações relacionadas às postagens.
    """
    
    def __init__(self, db_manager):
        """
        Inicializa o gerenciador de posts.
        
        Args:
            db_manager (DatabaseManager): Gerenciador de banco de dados
        """
        self.db = db_manager
        
        # Migra posts do arquivo JSON para o SQLite (se existir)
        self._migrate_from_json()
    
    def _migrate_from_json(self):
        """
        Migra posts do arquivo JSON para o banco de dados SQLite.
        """
        if os.path.exists(POSTS_FILE) and os.path.getsize(POSTS_FILE) > 0:
            try:
                with open(POSTS_FILE, "r", encoding="utf-8") as f:
                    posts_data = json.load(f)
                
                # Verifica estrutura do JSON
                if not all(key in posts_data for key in ["pending", "approved", "scheduled", "history"]):
                    logger.warning(f"Estrutura inválida em {POSTS_FILE}. Ignorando migração.")
                    return
                
                # Verifica se já existem posts no banco de dados
                self.db.execute("SELECT COUNT(*) FROM posts")
                count = self.db.fetchone()[0]
                
                if count > 0:
                    logger.info("Banco de dados já contém posts. Ignorando migração de JSON.")
                    return
                
                # Migra posts
                for status in ["pending", "approved", "scheduled", "history"]:
                    for post in posts_data[status]:
                        # Verifica se o post tem ID
                        if "id" not in post:
                            import uuid
                            post["id"] = str(uuid.uuid4())
                        
                        # Define o status correto
                        post["status"] = "posted" if status == "history" else status
                        
                        # Insere o post no banco de dados
                        self.db.execute(
                            """
                            INSERT INTO posts (
                                id, text, scheduled_time, status, created_at,
                                approved_at, scheduled_at, posted_at, edited_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                post["id"],
                                post["text"],
                                post.get("time", "now"),
                                post["status"],
                                post.get("created_at", datetime.now().isoformat()),
                                post.get("approved_at"),
                                post.get("scheduled_at"),
                                post.get("posted_at"),
                                post.get("edited_at")
                            )
                        )
                
                self.db.commit()
                
                # Renomeia o arquivo JSON original para backup
                backup_file = f"{POSTS_FILE}.bak.{int(time.time())}"
                os.rename(POSTS_FILE, backup_file)
                logger.info(f"Posts migrados com sucesso de {POSTS_FILE} para SQLite.")
                logger.info(f"Backup do arquivo JSON salvo em {backup_file}.")
                
            except Exception as e:
                logger.error(f"Erro ao migrar posts de JSON para SQLite: {e}")
    
    def create_post(self, text, scheduled_time="now"):
        """
        Cria uma nova postagem.
        
        Args:
            text (str): Texto da postagem
            scheduled_time (str): Horário agendado (formato HH:MM) ou "now"
            
        Returns:
            tuple: (bool, str, dict) - Sucesso, mensagem e dados do post
        """
        try:
            # Validação de texto
            if not text or not text.strip():
                return False, "O texto da postagem não pode estar vazio.", None
            
            # Limita o texto ao tamanho máximo
            if len(text) > MAX_TWEET_LENGTH:
                text = text[:MAX_TWEET_LENGTH]
            
            # Validação de horário
            if scheduled_time != "now":
                import re
                time_pattern = re.compile(r'^([01]\d|2[0-3]):([0-5]\d)$')
                if not time_pattern.match(scheduled_time):
                    return False, "Formato de horário inválido. Use HH:MM ou 'now'.", None
            
            # Gera ID único para o post
            import uuid
            post_id = str(uuid.uuid4())
            now = datetime.now().isoformat()
            
            # Insere o post no banco de dados
            self.db.execute(
                """
                INSERT INTO posts (
                    id, text, scheduled_time, status, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (post_id, text, scheduled_time, "pending", now)
            )
            self.db.commit()
            
            logger.info(f"Post criado [ID:{post_id[:8]}]: '{text[:30]}...'")
            return True, f"Postagem criada com sucesso.", {
                "id": post_id,
                "text": text,
                "scheduled_time": scheduled_time,
                "status": "pending",
                "created_at": now
            }
        except Exception as e:
            logger.error(f"Erro ao criar post: {e}")
            return False, f"Erro ao criar postagem: {e}", None
    
    def edit_post(self, post_id, new_text=None, new_time=None):
        """
        Edita uma postagem existente.
        
        Args:
            post_id (str): ID do post
            new_text (str, optional): Novo texto
            new_time (str, optional): Novo horário
            
        Returns:
            tuple: (bool, str, dict) - Sucesso, mensagem e dados do post
        """
        try:
            # Verifica se o post existe
            self.db.execute("SELECT * FROM posts WHERE id = ?", (post_id,))
            post = self.db.fetchone()
            
            if not post:
                return False, f"Post com ID {post_id} não encontrado.", None
            
            # Converte para dicionário
            post_dict = dict(post)
            
            # Verifica se o post pode ser editado
            if post_dict["status"] == "posted":
                return False, "Não é possível editar um post já publicado.", None
            
            # Preparação para update
            update_fields = []
            params = []
            
            # Atualiza texto se fornecido
            if new_text is not None:
                if not new_text.strip():
                    return False, "O texto da postagem não pode estar vazio.", None
                
                if len(new_text) > MAX_TWEET_LENGTH:
                    new_text = new_text[:MAX_TWEET_LENGTH]
                
                update_fields.append("text = ?")
                params.append(new_text)
                post_dict["text"] = new_text
            
            # Atualiza horário se fornecido
            if new_time is not None:
                if new_time != "now":
                    import re
                    time_pattern = re.compile(r'^([01]\d|2[0-3]):([0-5]\d)$')
                    if not time_pattern.match(new_time):
                        return False, "Formato de horário inválido. Use HH:MM ou 'now'.", None
                
                update_fields.append("scheduled_time = ?")
                params.append(new_time)
                post_dict["scheduled_time"] = new_time
            
            # Se não há nada para atualizar, retorna
            if not update_fields:
                return True, "Nenhuma alteração realizada.", post_dict
            
            # Adiciona timestamp de edição
            now = datetime.now().isoformat()
            update_fields.append("edited_at = ?")
            params.append(now)
            post_dict["edited_at"] = now
            
            # Adiciona ID para o WHERE
            params.append(post_id)
            
            # Executa a atualização
            self.db.execute(
                f"UPDATE posts SET {', '.join(update_fields)} WHERE id = ?",
                tuple(params)
            )
            self.db.commit()
            
            logger.info(f"Post editado [ID:{post_id[:8]}]")
            return True, "Postagem atualizada com sucesso.", post_dict
        except Exception as e:
            logger.error(f"Erro ao editar post: {e}")
            return False, f"Erro ao editar postagem: {e}", None
    
    def delete_post(self, post_id):
        """
        Exclui uma postagem.
        
        Args:
            post_id (str): ID do post
            
        Returns:
            tuple: (bool, str) - Sucesso e mensagem
        """
        try:
            # Verifica se o post existe
            self.db.execute("SELECT * FROM posts WHERE id = ?", (post_id,))
            post = self.db.fetchone()
            
            if not post:
                return False, f"Post com ID {post_id} não encontrado."
            
            # Verifica se o post pode ser excluído
            if post["status"] == "posted":
                return False, "Não é possível excluir um post já publicado."
            
            # Exclui o post
            self.db.execute("DELETE FROM posts WHERE id = ?", (post_id,))
            self.db.commit()
            
            logger.info(f"Post excluído [ID:{post_id[:8]}]")
            return True, "Postagem excluída com sucesso."
        except Exception as e:
            logger.error(f"Erro ao excluir post: {e}")
            return False, f"Erro ao excluir postagem: {e}"
    
    def approve_post(self, post_id, approve=True, new_time=None):
        """
        Aprova ou rejeita uma postagem.
        
        Args:
            post_id (str): ID do post
            approve (bool): True para aprovar, False para rejeitar
            new_time (str, optional): Novo horário para o post
            
        Returns:
            tuple: (bool, str, dict) - Sucesso, mensagem e dados do post
        """
        try:
            # Verifica se o post existe
            self.db.execute("SELECT * FROM posts WHERE id = ? AND status = 'pending'", (post_id,))
            post = self.db.fetchone()
            
            if not post:
                return False, f"Post pendente com ID {post_id} não encontrado.", None
            
            # Converte para dicionário
            post_dict = dict(post)
            
            # Se não aprovar, exclui o post
            if not approve:
                self.db.execute("DELETE FROM posts WHERE id = ?", (post_id,))
                self.db.commit()
                logger.info(f"Post rejeitado [ID:{post_id[:8]}]")
                return True, "Postagem rejeitada.", None
            
            # Atualiza horário se fornecido
            if new_time is not None:
                if new_time != "now":
                    import re
                    time_pattern = re.compile(r'^([01]\d|2[0-3]):([0-5]\d)$')
                    if not time_pattern.match(new_time):
                        return False, "Formato de horário inválido. Use HH:MM ou 'now'.", None
                
                post_dict["scheduled_time"] = new_time
            
            # Aprova o post
            now = datetime.now().isoformat()
            post_dict["status"] = "approved"
            post_dict["approved_at"] = now
            
            # Atualiza o post no banco de dados
            self.db.execute(
                """
                UPDATE posts SET
                    status = ?, approved_at = ?, scheduled_time = ?
                WHERE id = ?
                """,
                ("approved", now, post_dict["scheduled_time"], post_id)
            )
            self.db.commit()
            
            logger.info(f"Post aprovado [ID:{post_id[:8]}]")
            return True, "Postagem aprovada.", post_dict
        except Exception as e:
            logger.error(f"Erro ao aprovar/rejeitar post: {e}")
            return False, f"Erro ao aprovar/rejeitar postagem: {e}", None
    
    def schedule_post(self, post_id, schedule=True):
        """
        Agenda ou desagenda uma postagem.
        
        Args:
            post_id (str): ID do post
            schedule (bool): True para agendar, False para desagendar
            
        Returns:
            tuple: (bool, str, dict) - Sucesso, mensagem e dados do post
        """
        try:
            # Verifica se o post existe
            if schedule:
                status_query = "approved"
            else:
                status_query = "scheduled"
            
            self.db.execute(f"SELECT * FROM posts WHERE id = ? AND status = ?", (post_id, status_query))
            post = self.db.fetchone()
            
            if not post:
                return False, f"Post {status_query} com ID {post_id} não encontrado.", None
            
            # Converte para dicionário
            post_dict = dict(post)
            
            # Verifica se o post pode ser agendado
            if post_dict["scheduled_time"].lower() == "now" and schedule:
                return False, "Não é possível agendar um post com horário 'now'.", None
            
            # Atualiza o status do post
            now = datetime.now().isoformat()
            
            if schedule:
                new_status = "scheduled"
                post_dict["status"] = new_status
                post_dict["scheduled_at"] = now
                logger.info(f"Post agendado [ID:{post_id[:8]}] para {post_dict['scheduled_time']}")
                message = "Postagem agendada com sucesso."
            else:
                new_status = "approved"
                post_dict["status"] = new_status
                post_dict["scheduled_at"] = None
                logger.info(f"Post desagendado [ID:{post_id[:8]}]")
                message = "Agendamento removido com sucesso."
            
            # Atualiza o post no banco de dados
            self.db.execute(
                """
                UPDATE posts SET
                    status = ?, scheduled_at = ?
                WHERE id = ?
                """,
                (new_status, now if schedule else None, post_id)
            )
            self.db.commit()
            
            return True, message, post_dict
        except Exception as e:
            logger.error(f"Erro ao agendar/desagendar post: {e}")
            return False, f"Erro ao agendar/desagendar postagem: {e}", None
    
    def mark_as_posted(self, post_id):
        """
        Marca um post como publicado.
        
        Args:
            post_id (str): ID do post
            
        Returns:
            tuple: (bool, str) - Sucesso e mensagem
        """
        try:
            # Verifica se o post existe
            self.db.execute("SELECT * FROM posts WHERE id = ?", (post_id,))
            post = self.db.fetchone()
            
            if not post:
                return False, f"Post com ID {post_id} não encontrado."
            
            # Atualiza o status do post
            now = datetime.now().isoformat()
            
            self.db.execute(
                """
                UPDATE posts SET
                    status = ?, posted_at = ?
                WHERE id = ?
                """,
                ("posted", now, post_id)
            )
            self.db.commit()
            
            logger.info(f"Post marcado como publicado [ID:{post_id[:8]}]")
            return True, "Postagem marcada como publicada."
        except Exception as e:
            logger.error(f"Erro ao marcar post como publicado: {e}")
            return False, f"Erro ao marcar postagem como publicada: {e}"
    
    def get_posts(self, status=None, limit=None):
        """
        Obtém posts do banco de dados.
        
        Args:
            status (str, optional): Status dos posts a serem obtidos
            limit (int, optional): Limite de posts a serem retornados
            
        Returns:
            list: Lista de posts
        """
        try:
            query = "SELECT * FROM posts"
            params = []
            
            if status:
                if status == "history":
                    status = "posted"
                
                if status != "all":
                    query += " WHERE status = ?"
                    params.append(status)
            
            query += " ORDER BY "
            
            if status == "posted":
                query += "posted_at DESC"
            elif status == "scheduled":
                query += "scheduled_time ASC"
            else:
                query += "created_at DESC"
            
            if limit:
                query += " LIMIT ?"
                params.append(limit)
            
            self.db.execute(query, tuple(params) if params else None)
            posts = self.db.fetchall()
            
            # Converte para lista de dicionários
            return [dict(post) for post in posts]
        except Exception as e:
            logger.error(f"Erro ao obter posts: {e}")
            return []
    
    def get_pending_now_posts(self):
        """
        Obtém posts aprovados com horário 'now'.
        
        Returns:
            list: Lista de posts
        """
        try:
            self.db.execute(
                "SELECT * FROM posts WHERE status = 'approved' AND scheduled_time = 'now'"
            )
            posts = self.db.fetchall()
            
            # Converte para lista de dicionários
            return [dict(post) for post in posts]
        except Exception as e:
            logger.error(f"Erro ao obter posts 'now': {e}")
            return []
    
    def get_scheduled_posts_for_recovery(self):
        """
        Obtém posts agendados para recuperação após reinício.
        
        Returns:
            list: Lista de posts
        """
        try:
            self.db.execute("SELECT * FROM posts WHERE status = 'scheduled'")
            posts = self.db.fetchall()
            
            # Converte para lista de dicionários
            return [dict(post) for post in posts]
        except Exception as e:
            logger.error(f"Erro ao obter posts agendados para recuperação: {e}")
            return []
    
    def get_stats(self):
        """
        Obtém estatísticas dos posts.
        
        Returns:
            dict: Estatísticas dos posts
        """
        try:
            stats = {}
            
            # Total de posts por status
            for status in ["pending", "approved", "scheduled", "posted"]:
                self.db.execute(f"SELECT COUNT(*) FROM posts WHERE status = ?", (status,))
                result = self.db.fetchone()
                count = result[0] if result else 0
                
                # Para compatibilidade com a versão anterior
                if status == "posted":
                    status_key = "total_posted"
                else:
                    status_key = f"total_{status}"
                
                stats[status_key] = count
            
            # Total de todos os posts
            self.db.execute("SELECT COUNT(*) FROM posts")
            stats["total_all"] = self.db.fetchone()[0]
            
            # Posts de hoje
            today = datetime.now().date().isoformat()
            self.db.execute(
                "SELECT COUNT(*) FROM posts WHERE status = 'posted' AND date(posted_at) = ?",
                (today,)
            )
            stats["posts_today"] = self.db.fetchone()[0]
            
            # Posts deste mês
            current_month = datetime.now().strftime("%Y-%m")
            self.db.execute(
                "SELECT COUNT(*) FROM posts WHERE status = 'posted' AND substr(posted_at, 1, 7) = ?",
                (current_month,)
            )
            stats["posts_this_month"] = self.db.fetchone()[0]
            
            return stats
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas: {e}")
            return {
                "total_pending": 0,
                "total_approved": 0,
                "total_scheduled": 0,
                "total_posted": 0,
                "total_all": 0,
                "posts_today": 0,
                "posts_this_month": 0
            }
            
class TrendManager:
    """
    Gerencia as tendências do Twitter/X.
    """
    
    def __init__(self, db_manager):
        """
        Inicializa o gerenciador de tendências.
        
        Args:
            db_manager (DatabaseManager): Gerenciador de banco de dados
        """
        self.db = db_manager
        self.trends = []
        self.last_updated = None
    
    def update_trends(self):
        """
        Atualiza as tendências do Twitter/X.
        
        Returns:
            bool: True se as tendências foram atualizadas com sucesso, False caso contrário
        """
        try:
            logger.info("Atualizando tendências...")
            trends_data, timestamp = get_trends()
            
            if not trends_data or "error" in trends_data[0].get("name", "").lower():
                logger.error(f"Falha ao atualizar tendências: {trends_data[0]['name'] if trends_data else 'Sem dados'}")
                return False
            
            # Atualiza as tendências em memória
            self.trends = trends_data
            self.last_updated = timestamp
            
            # Salva as tendências no banco de dados
            for trend in trends_data:
                self.db.execute(
                    """
                    INSERT INTO trends (name, volume, timestamp)
                    VALUES (?, ?, ?)
                    """,
                    (
                        trend.get("name", "N/A"),
                        trend.get("volume", None),
                        timestamp.isoformat()
                    )
                )
            
            self.db.commit()
            
            trend_names = [t.get('name', 'N/A') for t in trends_data]
            logger.info(f"Tendências atualizadas: {', '.join(trend_names)}")
            return True
        except Exception as e:
            logger.error(f"Erro ao atualizar tendências: {e}")
            return False
    
    def get_trends(self, limit=None):
        """
        Obtém as tendências atuais.
        
        Args:
            limit (int, optional): Limite de tendências a serem retornadas
            
        Returns:
            tuple: (list, datetime) - Lista de tendências e timestamp de atualização
        """
        # Se não temos tendências em memória ou se passaram mais de 3 horas, atualiza
        if not self.trends or not self.last_updated or \
           (datetime.now() - self.last_updated > timedelta(hours=3)):
            self.update_trends()
        
        if limit and limit < len(self.trends):
            return self.trends[:limit], self.last_updated
        
        return self.trends, self.last_updated

# =============================================================================
# Classe principal do Bot
# =============================================================================

class BotX:
    """
    Classe principal que gerencia o Bot do Twitter/X.
    """
    
    def __init__(self):
        """
        Inicializa o bot.
        """
        # Configuração de logging
        self._setup_logging()
        
        # Inicializa variáveis de estado
        self.bot_running = True
        self.web_server = None
        self.web_thread = None
        
        # Estatísticas de posts
        self.monthly_posts = 0
        self.daily_posts = 0
        
        # Instancia gerenciadores
        self.db_manager = DatabaseManager(DB_FILE)
        self.post_manager = PostManager(self.db_manager)
        self.trend_manager = TrendManager(self.db_manager)
        
        # Configura scheduler
        self._setup_scheduler()
        
        # Registra handlers para graceful shutdown
        self._register_shutdown_handlers()
    
    def _setup_logging(self):
        """
        Configura o logging do bot.
        """
        try:
            # Cria diretório de logs se não existir
            os.makedirs(LOG_DIR, exist_ok=True)
            
            # Configuração do logger principal
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.FileHandler(LOG_FILE),
                    logging.StreamHandler()
                ]
            )
            
            logger.info("Logging configurado com sucesso.")
        except Exception as e:
            print(f"ERRO: Não foi possível configurar o log: {e}")
            # Configuração mínima para console
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
    
    def _setup_scheduler(self):
        """
        Configura o scheduler para tarefas agendadas.
        """
        try:
            # Configura job stores e executors
            job_stores = {
                'default': SQLAlchemyJobStore(url=f'sqlite:///{DB_FILE}')
            }
            
            executors = {
                'default': ThreadPoolExecutor(20)
            }
            
            job_defaults = {
                'coalesce': SCHEDULER_COALESCE,
                'max_instances': SCHEDULER_MAX_INSTANCES,
                'misfire_grace_time': SCHEDULER_MISFIRE_GRACE_TIME
            }
            
            # Cria e configura o scheduler
            self.scheduler = BackgroundScheduler(
                jobstores=job_stores,
                executors=executors,
                job_defaults=job_defaults
            )
            
            # Agenda tarefas periódicas
            self.scheduler.add_job(
                self._reset_daily_count,
                'cron',
                hour=0,
                minute=0,
                id='reset_daily_count',
                replace_existing=True
            )
            
            self.scheduler.add_job(
                self._check_month_reset,
                'cron',
                hour=0,
                minute=0,
                day=1,
                id='reset_monthly_count',
                replace_existing=True
            )
            
            self.scheduler.add_job(
                self._process_pending_now_posts,
                'interval',
                minutes=5,
                id='process_now_posts',
                replace_existing=True
            )
            
            if TREND_UPDATE_HOUR:
                hour, minute = TREND_UPDATE_HOUR.split(':')
                self.scheduler.add_job(
                    self.trend_manager.update_trends,
                    'cron',
                    hour=int(hour),
                    minute=int(minute),
                    id='update_trends',
                    replace_existing=True
                )
            
            # Recupera posts agendados
            self._recover_scheduled_posts()
            
            logger.info("Scheduler configurado com sucesso.")
        except Exception as e:
            logger.error(f"Erro ao configurar scheduler: {e}")
            raise
    
    def _register_shutdown_handlers(self):
        """
        Registra handlers para capturar sinais de desligamento e finalizar graciosamente.
        """
        def shutdown_handler(signum, frame):
            logger.info(f"Sinal de desligamento recebido ({signum}). Finalizando graciosamente...")
            self.stop()
        
        # Registra para SIGINT (Ctrl+C) e SIGTERM
        signal.signal(signal.SIGINT, shutdown_handler)
        signal.signal(signal.SIGTERM, shutdown_handler)
    
    def _recover_scheduled_posts(self):
        """
        Recupera posts agendados do banco de dados e os agenda no scheduler.
        """
        try:
            scheduled_posts = self.post_manager.get_scheduled_posts_for_recovery()
            
            if not scheduled_posts:
                logger.info("Nenhum post agendado para recuperar.")
                return
            
            count = 0
            for post in scheduled_posts:
                # Ignora posts com horário 'now'
                if post["scheduled_time"].lower() == "now":
                    continue
                
                # Agenda o post no scheduler
                hour, minute = post["scheduled_time"].split(':')
                
                self.scheduler.add_job(
                    self._post_scheduled_tweet,
                    'cron',
                    hour=int(hour),
                    minute=int(minute),
                    id=f"post_{post['id']}",
                    args=[post["id"]],
                    replace_existing=True
                )
                count += 1
            
            logger.info(f"Recuperados {count} posts agendados.")
        except Exception as e:
            logger.error(f"Erro ao recuperar posts agendados: {e}")
    
    def _load_post_counts(self):
        """
        Carrega a contagem de posts mensais e diários do banco de dados.
        """
        try:
            stats = self.post_manager.get_stats()
            self.daily_posts = stats["posts_today"]
            self.monthly_posts = stats["posts_this_month"]
            
            logger.info(f"Contagens carregadas: {self.monthly_posts} este mês, {self.daily_posts} hoje")
        except Exception as e:
            logger.error(f"Erro ao carregar contagens de posts: {e}")
            self.daily_posts = 0
            self.monthly_posts = 0
    
    def _can_post_today(self):
        """
        Verifica se ainda podemos postar hoje (limite diário).
        
        Returns:
            bool: True se ainda podemos postar, False caso contrário
        """
        if self.daily_posts >= DAILY_POST_LIMIT:
            logger.warning(f"Limite diário de {DAILY_POST_LIMIT} posts atingido")
            return False
        return True
    
    def _can_post_this_month(self):
        """
        Verifica se ainda podemos postar este mês (limite mensal).
        
        Returns:
            bool: True se ainda podemos postar, False caso contrário
        """
        if self.monthly_posts >= MONTHLY_POST_LIMIT:
            logger.warning(f"Limite mensal de {MONTHLY_POST_LIMIT} posts atingido")
            return False
        return True
    
    def _reset_daily_count(self):
        """
        Reseta o contador diário de posts à meia-noite.
        """
        self.daily_posts = 0
        logger.info("Contador diário de posts resetado")
    
    def _reset_monthly_count(self):
        """
        Reseta o contador mensal de posts no primeiro dia do mês.
        """
        self.monthly_posts = 0
        logger.info("Contador mensal de posts resetado")
    
    def _check_month_reset(self):
        """
        Verifica se é o primeiro dia do mês e reseta o contador mensal.
        """
        current_date = datetime.now()
        if current_date.day == 1 and current_date.hour == 0:
            self._reset_monthly_count()
    
    def _post_scheduled_tweet(self, post_id):
        """
        Publica um tweet agendado.
        
        Args:
            post_id (str): ID do post a ser publicado
        
        Returns:
            bool: True se publicado com sucesso, False caso contrário
        """
        if not self._can_post_today() or not self._can_post_this_month():
            logger.warning(f"Post {post_id} não publicado devido aos limites da API")
            return False
        
        try:
            # Obtém o post do banco de dados
            self.db_manager.execute("SELECT * FROM posts WHERE id = ?", (post_id,))
            post = self.db_manager.fetchone()
            
            if not post:
                logger.error(f"Post {post_id} não encontrado para publicação agendada")
                return False
            
            # Converte para dicionário
            post_dict = dict(post)
            
            logger.info(f"Publicando post agendado [ID:{post_id[:8]}]: '{post_dict['text'][:50]}...'")
            
            # Publica o tweet
            success, message, tweet_data = post_tweet(post_dict["text"])
            
            if success:
                # Atualiza contadores
                self.monthly_posts += 1
                self.daily_posts += 1
                
                # Marca como publicado
                self.post_manager.mark_as_posted(post_id)
                
                logger.info(f"Post [ID:{post_id[:8]}] publicado com sucesso: {message}")
                return True
            else:
                logger.error(f"Falha ao publicar post [ID:{post_id[:8]}]: {message}")
                return False
        except Exception as e:
            logger.error(f"Erro ao publicar post agendado [ID:{post_id[:8] if post_id else 'N/A'}]: {e}")
            return False
    
    def _process_pending_now_posts(self):
        """
        Processa posts aprovados com horário 'now'.
        """
        if not self._can_post_today() or not self._can_post_this_month():
            logger.warning("Não é possível processar posts 'now' devido aos limites da API")
            return
        
        try:
            now_posts = self.post_manager.get_pending_now_posts()
            
            if not now_posts:
                return
            
            logger.info(f"Processando {len(now_posts)} posts com horário 'now'")
            
            for post in now_posts:
                if not self._can_post_today() or not self._can_post_this_month():
                    logger.warning("Limite de posts atingido durante o processamento de posts 'now'")
                    break
                
                post_id = post["id"]
                logger.info(f"Publicando post imediato [ID:{post_id[:8]}]: '{post['text'][:50]}...'")
                
                success, message, tweet_data = post_tweet(post["text"])
                
                if success:
                    # Atualiza contadores
                    self.monthly_posts += 1
                    self.daily_posts += 1
                    
                    # Marca como publicado
                    self.post_manager.mark_as_posted(post_id)
                    
                    logger.info(f"Post 'now' [ID:{post_id[:8]}] publicado com sucesso: {message}")
                else:
                    logger.error(f"Falha ao publicar post 'now' [ID:{post_id[:8]}]: {message}")
        except Exception as e:
            logger.error(f"Erro ao processar posts 'now': {e}")
    
    def start(self, web_mode=False, web_host=WEB_HOST, web_port=WEB_PORT, open_browser=True):
        """
        Inicia o bot.
        
        Args:
            web_mode (bool): True para iniciar com interface web, False para CLI
            web_host (str): Host para a interface web
            web_port (int): Porta para a interface web
            open_browser (bool): True para abrir navegador automaticamente
        """
        try:
            # Inicializa a API do Twitter
            success, message = initialize_api()
            
            if not success:
                print(COLOR_ERROR + f"Erro ao conectar com a API do Twitter: {message}" + COLOR_RESET)
                print(COLOR_INFO + "Verifique suas credenciais no arquivo .env" + COLOR_RESET)
                print(COLOR_INFO + "Execute 'python setup.py' para configurar" + COLOR_RESET)
                return
            
            print(COLOR_SUCCESS + message + COLOR_RESET)
            
            # Carrega contagens de posts
            self._load_post_counts()
            
            # Atualiza tendências
            self.trend_manager.update_trends()
            
            # Inicia o scheduler
            if not self.scheduler.running:
                self.scheduler.start()
                logger.info("Scheduler iniciado.")
            
            # Decide entre modo web ou modo CLI
            if web_mode:
                self._start_web_server(web_host, web_port, open_browser)
            else:
                # Inicia a interface CLI
                self._start_cli()
        except Exception as e:
            logger.error(f"Erro ao iniciar o bot: {e}")
            print(COLOR_ERROR + f"Erro ao iniciar o bot: {e}" + COLOR_RESET)
    
    def _start_web_server(self, host, port, open_browser):
        """
        Inicia o servidor web para interface gráfica.
        
        Args:
            host (str): Host para o servidor web
            port (int): Porta para o servidor web
            open_browser (bool): True para abrir navegador automaticamente
        """
        try:
            # Tenta importar Flask
            try:
                import flask # type: ignore
            except ImportError:
                print(COLOR_ERROR + "Flask não está instalado. Não é possível iniciar o servidor web." + COLOR_RESET)
                print(COLOR_INFO + "Execute 'pip install flask' ou 'python setup.py' para instalar." + COLOR_RESET)
                
                # Fallback para CLI
                print(COLOR_INFO + "Iniciando em modo CLI..." + COLOR_RESET)
                self._start_cli()
                return
            
            # Carrega o módulo server.py dinamicamente
            try:
                server_module = importlib.import_module("server")
                
                # Verifica se o módulo tem a função start_server
                if not hasattr(server_module, "start_server"):
                    raise ImportError("Módulo server.py não tem a função start_server")
                
                # Inicia o servidor web em uma thread separada
                self.web_thread = threading.Thread(
                    target=server_module.start_server,
                    args=(self, host, port, open_browser),
                    daemon=True
                )
                self.web_thread.start()
                
                print(COLOR_SUCCESS + f"Servidor web iniciado em http://{host}:{port}" + COLOR_RESET)
                
                # Mantém o processo principal vivo
                try:
                    while self.bot_running:
                        time.sleep(1)
                except KeyboardInterrupt:
                    self.stop()
            except ImportError as e:
                print(COLOR_ERROR + f"Não foi possível iniciar o servidor web: {e}" + COLOR_RESET)
                print(COLOR_INFO + "Certifique-se de que o arquivo server.py está no mesmo diretório." + COLOR_RESET)
                
                # Fallback para CLI
                print(COLOR_INFO + "Iniciando em modo CLI..." + COLOR_RESET)
                self._start_cli()
        except Exception as e:
            logger.error(f"Erro ao iniciar servidor web: {e}")
            print(COLOR_ERROR + f"Erro ao iniciar servidor web: {e}" + COLOR_RESET)
            
            # Fallback para CLI
            print(COLOR_INFO + "Iniciando em modo CLI..." + COLOR_RESET)
            self._start_cli()
    
    def stop(self):
        """
        Para o bot graciosamente.
        """
        try:
            logger.info("Parando o bot...")
            
            # Marca como não rodando
            self.bot_running = False
            
            # Para o scheduler
            if self.scheduler and self.scheduler.running:
                self.scheduler.shutdown()
                logger.info("Scheduler parado.")
            
            # Fecha conexão com o banco de dados
            if self.db_manager:
                self.db_manager.close()
                logger.info("Conexão com o banco de dados fechada.")
            
            logger.info("Bot parado com sucesso.")
        except Exception as e:
            logger.error(f"Erro ao parar o bot: {e}")
    
    # =============================================================================
    # Funções da interface CLI
    # =============================================================================
    
    def _start_cli(self):
        """
        Inicia a interface de linha de comando.
        """
        try:
            while self.bot_running:
                self._display_dashboard()
                choice = input(COLOR_INFO + "\nEscolha uma opção: " + COLOR_RESET).strip()
                
                if choice == "1":
                    self._create_new_post()
                elif choice == "2":
                    self._list_posts()
                elif choice == "3":
                    self._approve_posts()
                elif choice == "4":
                    self._schedule_approved_posts()
                elif choice == "5":
                    self._update_trends()
                elif choice == "6":
                    self._display_stats()
                elif choice == "7":
                    self._display_help()
                elif choice == "8":
                    print(COLOR_INFO + "Encerrando o bot..." + COLOR_RESET)
                    self.stop()
                    break
                else:
                    print(COLOR_WARNING + "Opção inválida!" + COLOR_RESET)
        except KeyboardInterrupt:
            print("\n" + COLOR_INFO + "Encerrando o bot..." + COLOR_RESET)
            self.stop()
        except Exception as e:
            logger.error(f"Erro na interface CLI: {e}")
            print(COLOR_ERROR + f"Erro na interface CLI: {e}" + COLOR_RESET)
            self.stop()
    
    def _clear_screen(self):
        """Limpa a tela do terminal."""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def _display_dashboard(self):
        """Exibe o dashboard principal do bot."""
        self._clear_screen()
        
        print(COLOR_HEADER + "\n===== BOT X - DASHBOARD =====" + COLOR_RESET)
        print(COLOR_INFO + "\n1. Criar Nova Postagem")
        print("2. Listar Postagens")
        print("3. Aprovar Postagens Pendentes")
        print("4. Agendar Postagens Aprovadas")
        print("5. Atualizar Tendências")
        print("6. Exibir Estatísticas")
        print("7. Ajuda")
        print("8. Sair" + COLOR_RESET)
    
    def _format_trend_list(self, max_trends=None):
        """
        Formata a lista de tendências para exibição.
        
        Args:
            max_trends (int, optional): Número máximo de tendências a exibir
            
        Returns:
            list: Lista de strings formatadas com as tendências
        """
        trends, last_updated = self.trend_manager.get_trends()
        result = []
        
        if not trends:
            result.append(COLOR_WARNING + "Nenhuma tendência disponível. Use a opção 'Atualizar tendências' para buscar." + COLOR_RESET)
            return result
        
        result.append(COLOR_INFO + f"Tendências globais (atualizado em: {last_updated.strftime(DATE_FORMAT) if last_updated else 'N/A'}):" + COLOR_RESET)
        
        # Limita o número de tendências se necessário
        if max_trends and max_trends < len(trends):
            trends = trends[:max_trends]
        
        for i, trend in enumerate(trends, 1):
            name = trend.get("name", "N/A")
            volume = trend.get("volume", "N/A")
            volume_str = f"{volume:,}".replace(',', '.') if isinstance(volume, int) else "N/A"
            result.append(f"{i}. {name} | Volume: {volume_str}")
        
        return result
    
    def _update_trends(self):
        """Atualiza as tendências do Twitter/X."""
        print(COLOR_INFO + "\nAtualizando tendências globais..." + COLOR_RESET)
        
        if self.trend_manager.update_trends():
            print(COLOR_SUCCESS + "Tendências atualizadas com sucesso!" + COLOR_RESET)
        else:
            print(COLOR_ERROR + "Falha ao atualizar tendências. Verifique a conexão e as credenciais." + COLOR_RESET)
        
        for line in self._format_trend_list():
            print(line)
        
        input(COLOR_INFO + "\nPressione ENTER para continuar..." + COLOR_RESET)
    
    def _display_stats(self):
        """Exibe estatísticas do bot."""
        self._clear_screen()
        stats = self.post_manager.get_stats()
        
        print(COLOR_HEADER + "\n===== ESTATÍSTICAS =====" + COLOR_RESET)
        print(COLOR_INFO + f"Pendentes: {stats['total_pending']}")
        print(f"Aprovadas: {stats['total_approved']}")
        print(f"Agendadas: {stats['total_scheduled']}")
        print(f"Publicadas: {stats['total_posted']}")
        print(f"Total de Posts: {stats['total_all']}")
        print(f"Posts Hoje: {stats['posts_today']}")
        print(f"Posts Este Mês: {stats['posts_this_month']}")
        
        # Obtém status da API
        api_status = check_api_limits()
        
        print(COLOR_HEADER + "\n===== STATUS DA API =====" + COLOR_RESET)
        print(COLOR_INFO + f"Autenticado: {COLOR_SUCCESS if api_status.get('authenticated') else COLOR_ERROR}{api_status.get('authenticated', False)}{COLOR_RESET}")
        print(f"Usuário: {api_status.get('username', 'N/A')}")
        
        if 'last_error' in api_status:
            print(COLOR_WARNING + f"Último erro: {api_status['last_error']}" + COLOR_RESET)
        
        input(COLOR_INFO + "\nPressione ENTER para continuar..." + COLOR_RESET)
    
    def _display_help(self):
        """Exibe a tela de ajuda do bot."""
        self._clear_screen()
        
        print(COLOR_HEADER + "\n===== AJUDA DO BOT X =====" + COLOR_RESET)
        
        print(COLOR_INFO + "\n=== Visão Geral ===" + COLOR_RESET)
        print("O Bot X é uma ferramenta para automação de postagens no Twitter/X.")
        print("Ele permite criar, agendar e publicar tweets de forma organizada.")
        
        print(COLOR_INFO + "\n=== Funções Principais ===" + COLOR_RESET)
        print("1. Criar Postagem - Crie novos tweets para publicar")
        print("2. Listar Postagens - Visualize e gerencie suas postagens")
        print("3. Aprovar Postagens - Revise e aprove postagens pendentes")
        print("4. Agendar Postagens - Defina horários para publicação automática")
        print("5. Atualizar Tendências - Veja os tópicos em alta no Twitter/X")
        print("6. Estatísticas - Veja métricas de uso e limites da API")
        
        print(COLOR_INFO + "\n=== Fluxo de Trabalho ===" + COLOR_RESET)
        print("1. Crie postagens (ficam com status 'pendente')")
        print("2. Aprove as postagens pendentes")
        print("3. Agende postagens aprovadas ou publique-as imediatamente")
        print("4. As postagens agendadas serão publicadas automaticamente")
        
        print(COLOR_INFO + "\n=== Limitações da API ===" + COLOR_RESET)
        print(f"- Limite diário: {DAILY_POST_LIMIT} tweets")
        print(f"- Limite mensal: {MONTHLY_POST_LIMIT} tweets")
        print("- O bot controla automaticamente esses limites")
        
        print(COLOR_INFO + "\n=== Dicas ===" + COLOR_RESET)
        print("- Use as tendências para inspiração ao criar posts")
        print("- Você pode editar posts antes de aprová-los")
        print("- Posts podem ser agendados para qualquer horário (formato HH:MM)")
        print("- Use 'now' como horário para postar assim que aprovado")
        
        print(COLOR_INFO + "\n=== Para Mais Informações ===" + COLOR_RESET)
        print("Visite o repositório: github.com/uillenmachado/botx")
        
        input(COLOR_INFO + "\nPressione ENTER para voltar ao menu principal..." + COLOR_RESET)
    
    def _create_new_post(self):
        """Interface para criar uma nova postagem."""
        self._clear_screen()
        
        print(COLOR_HEADER + "\n===== CRIAR NOVA POSTAGEM =====" + COLOR_RESET)
        
        # Exibe tendências para inspiração
        print(COLOR_INFO + "\nTendências atuais para inspiração:" + COLOR_RESET)
        for line in self._format_trend_list(max_trends=5):
            print(line)
        
        # Solicita o texto da postagem
        print(COLOR_INFO + "\nDigite o texto da sua postagem:" + COLOR_RESET)
        text = input("> ").strip()
        
        if not text:
            print(COLOR_ERROR + "Texto vazio! A postagem não foi criada." + COLOR_RESET)
            input(COLOR_INFO + "\nPressione ENTER para continuar..." + COLOR_RESET)
            return
        
        # Informações sobre o limite de caracteres
        if len(text) > MAX_TWEET_LENGTH:
            print(COLOR_WARNING + f"O texto excede o limite de {MAX_TWEET_LENGTH} caracteres e será truncado." + COLOR_RESET)
            text = text[:MAX_TWEET_LENGTH]
            print(COLOR_INFO + f"Texto truncado: {text}" + COLOR_RESET)
        
        # Solicita o horário da postagem
        print(COLOR_INFO + "\nDigite o horário para a postagem (HH:MM) ou 'now' para postar assim que aprovado:" + COLOR_RESET)
        time_str = input("> ").strip()
        
        if not time_str:
            time_str = "now"
            print(COLOR_INFO + "Usando 'now' como horário padrão." + COLOR_RESET)
        
        # Cria a postagem
        success, message, post = self.post_manager.create_post(text, time_str)
        
        if success:
            print(COLOR_SUCCESS + f"\nSucesso! {message}" + COLOR_RESET)
        else:
            print(COLOR_ERROR + f"\nErro! {message}" + COLOR_RESET)
        
        input(COLOR_INFO + "\nPressione ENTER para continuar..." + COLOR_RESET)
    
    def _list_posts(self):
        """Interface para listar e gerenciar postagens."""
        while True:
            self._clear_screen()
            
            print(COLOR_HEADER + "\n===== LISTAR POSTAGENS =====" + COLOR_RESET)
            print(COLOR_INFO + "\n1. Pendentes")
            print("2. Aprovadas")
            print("3. Agendadas")
            print("4. Histórico de publicações")
            print("5. Todas")
            print("0. Voltar" + COLOR_RESET)
            
            choice = input(COLOR_INFO + "\nEscolha uma opção: " + COLOR_RESET).strip()
            
            if choice == "0":
                break
            
            status_map = {
                "1": "pending",
                "2": "approved",
                "3": "scheduled",
                "4": "posted",
                "5": "all"
            }
            
            if choice in status_map:
                status = status_map[choice]
                self._display_post_list(status)
            else:
                print(COLOR_WARNING + "Opção inválida!" + COLOR_RESET)
                time.sleep(0.5)
    
    def _display_post_list(self, status):
        """
        Exibe lista de posts com opções de gerenciamento.
        
        Args:
            status (str): Status dos posts a serem exibidos
        """
        self._clear_screen()
        
        # Título baseado no status
        status_title = {
            "pending": "PENDENTES",
            "approved": "APROVADAS",
            "scheduled": "AGENDADAS",
            "posted": "PUBLICADAS",
            "all": "TODAS"
        }
        
        print(COLOR_HEADER + f"\n===== POSTAGENS {status_title.get(status, '').upper()} =====" + COLOR_RESET)
        
        # Obtém os posts
        posts = self.post_manager.get_posts(status)
        
        if not posts:
            print(COLOR_INFO + "\nNenhuma postagem encontrada." + COLOR_RESET)
            input(COLOR_INFO + "\nPressione ENTER para continuar..." + COLOR_RESET)
            return
        
        # Exibe os posts com formatação bonita
        for i, post in enumerate(posts, 1):
            post_time = post.get("scheduled_time", "N/A")
            created_at = self._format_datetime(post.get("created_at"))
            
            # Determina a cor baseada no status
            color = COLOR_INFO
            if post["status"] == "approved":
                color = COLOR_SUCCESS
            elif post["status"] == "scheduled":
                color = Fore.BLUE if HAS_COLORS else ""
            elif post["status"] == "posted":
                color = Fore.MAGENTA if HAS_COLORS else ""
            
            # Formata o texto para exibição (quebra linhas longas)
            text = textwrap.shorten(post["text"], width=60, placeholder="...")
            
            # Monta a string de exibição
            post_str = f"{i}. [ID:{post['id'][:8]}] {text}"
            post_str += f" | Horário: {post_time}"
            post_str += f" | Criado: {created_at}"
            
            print(color + post_str + COLOR_RESET)
        
        # Opções para posts não publicados
        if status != "posted" and status != "all":
            print(COLOR_INFO + "\nOpções:" + COLOR_RESET)
            print(COLOR_INFO + "E - Editar uma postagem")
            print("D - Deletar uma postagem")
            print("V - Voltar" + COLOR_RESET)
            
            action = input(COLOR_INFO + "\nEscolha uma ação: " + COLOR_RESET).upper().strip()
            
            if action == "E":
                self._edit_post(posts)
            elif action == "D":
                self._delete_post(posts)
        else:
            input(COLOR_INFO + "\nPressione ENTER para continuar..." + COLOR_RESET)
    
    def _format_datetime(self, datetime_str):
        """
        Formata uma string de data/hora ISO para exibição.
        
        Args:
            datetime_str (str): String de data/hora em formato ISO
            
        Returns:
            str: Data/hora formatada
        """
        if not datetime_str:
            return "N/A"
        
        try:
            dt = datetime.fromisoformat(datetime_str)
            return dt.strftime(DATE_FORMAT)
        except (ValueError, TypeError):
            return datetime_str
    
    def _edit_post(self, posts):
        """
        Interface para editar uma postagem.
        
        Args:
            posts (list): Lista de posts disponíveis para edição
        """
        try:
            post_index = int(input(COLOR_INFO + "\nDigite o número da postagem para editar: " + COLOR_RESET)) - 1
            
            if post_index < 0 or post_index >= len(posts):
                print(COLOR_ERROR + "Número inválido!" + COLOR_RESET)
                input(COLOR_INFO + "\nPressione ENTER para continuar..." + COLOR_RESET)
                return
            
            post = posts[post_index]
            
            # Exibe o post atual
            print(COLOR_INFO + f"\nEditando postagem: {post['text']}" + COLOR_RESET)
            print(COLOR_INFO + f"Horário atual: {post['scheduled_time']}" + COLOR_RESET)
            
            # Solicita o novo texto
            print(COLOR_INFO + "\nDigite o novo texto (deixe em branco para manter o atual):" + COLOR_RESET)
            new_text = input("> ").strip()
            
            # Solicita o novo horário
            print(COLOR_INFO + "\nDigite o novo horário (deixe em branco para manter o atual):" + COLOR_RESET)
            new_time = input("> ").strip()
            
            # Edita o post
            success, message, updated_post = self.post_manager.edit_post(
                post["id"],
                new_text=new_text if new_text else None,
                new_time=new_time if new_time else None
            )
            
            if success:
                print(COLOR_SUCCESS + f"\nSucesso! {message}" + COLOR_RESET)
            else:
                print(COLOR_ERROR + f"\nErro! {message}" + COLOR_RESET)
        except ValueError:
            print(COLOR_ERROR + "Entrada inválida! Digite apenas números." + COLOR_RESET)
        except Exception as e:
            print(COLOR_ERROR + f"Erro ao editar postagem: {e}" + COLOR_RESET)
        
        input(COLOR_INFO + "\nPressione ENTER para continuar..." + COLOR_RESET)
    
    def _delete_post(self, posts):
        """
        Interface para excluir uma postagem.
        
        Args:
            posts (list): Lista de posts disponíveis para exclusão
        """
        try:
            post_index = int(input(COLOR_INFO + "\nDigite o número da postagem para deletar: " + COLOR_RESET)) - 1
            
            if post_index < 0 or post_index >= len(posts):
                print(COLOR_ERROR + "Número inválido!" + COLOR_RESET)
                input(COLOR_INFO + "\nPressione ENTER para continuar..." + COLOR_RESET)
                return
            
            post = posts[post_index]
            
            # Confirmação de exclusão
            confirm = input(COLOR_WARNING + f"Tem certeza que deseja deletar a postagem #{post_index+1}? (S/N): " + COLOR_RESET).upper().strip()
            
            if confirm == "S":
                success, message = self.post_manager.delete_post(post["id"])
                
                if success:
                    print(COLOR_SUCCESS + f"\nSucesso! {message}" + COLOR_RESET)
                else:
                    print(COLOR_ERROR + f"\nErro! {message}" + COLOR_RESET)
            else:
                print(COLOR_INFO + "Operação cancelada." + COLOR_RESET)
        except ValueError:
            print(COLOR_ERROR + "Entrada inválida! Digite apenas números." + COLOR_RESET)
        except Exception as e:
            print(COLOR_ERROR + f"Erro ao deletar postagem: {e}" + COLOR_RESET)
        
        input(COLOR_INFO + "\nPressione ENTER para continuar..." + COLOR_RESET)
    
    def _approve_posts(self):
        """Interface para aprovar ou rejeitar postagens pendentes."""
        self._clear_screen()
        
        print(COLOR_HEADER + "\n===== APROVAR POSTAGENS =====" + COLOR_RESET)
        
        # Obtém posts pendentes
        posts = self.post_manager.get_posts("pending")
        
        if not posts:
            print(COLOR_INFO + "\nNão há postagens pendentes para aprovação." + COLOR_RESET)
            input(COLOR_INFO + "\nPressione ENTER para continuar..." + COLOR_RESET)
            return
        
        # Contadores para timeout
        timeout_count = 0
        max_consecutive_timeouts = 3
        
        for i, post in enumerate(posts):
            self._clear_screen()
            print(COLOR_HEADER + "\n===== APROVAR POSTAGENS =====" + COLOR_RESET)
            print(COLOR_INFO + f"\nPostagem {i+1} de {len(posts)}" + COLOR_RESET)
            
            # Exibe o post
            print(COLOR_INFO + f"\nID: {post['id'][:8]}" + COLOR_RESET)
            print(COLOR_INFO + f"Criado em: {self._format_datetime(post['created_at'])}" + COLOR_RESET)
            print(COLOR_INFO + f"Horário agendado: {post['scheduled_time']}" + COLOR_RESET)
            print(COLOR_INFO + f"\nTexto: {post['text']}" + COLOR_RESET)
            
            print(COLOR_INFO + "\nOpções:" + COLOR_RESET)
            print(COLOR_SUCCESS + "A - Aprovar" + COLOR_RESET)
            print(COLOR_ERROR + "R - Rejeitar" + COLOR_RESET)
            print(COLOR_INFO + "S - Pular")
            print("E - Editar antes de aprovar")
            print("C - Cancelar aprovações" + COLOR_RESET)
            
            # Lê a ação com timeout
            action = self._get_user_action_with_timeout(APPROVE_TIMEOUT)
            
            if not action:
                print(COLOR_WARNING + "Timeout! Pulando para a próxima postagem." + COLOR_RESET)
                timeout_count += 1
                
                if timeout_count >= max_consecutive_timeouts:
                    print(COLOR_WARNING + f"\nMuitos timeouts consecutivos ({max_consecutive_timeouts}). Encerrando processo de aprovação." + COLOR_RESET)
                    break
                
                time.sleep(1)
                continue
            else:
                timeout_count = 0
                action = action.strip().upper()[:1]  # Considera apenas primeiro caractere
            
            if action == "A":
                # Opção para alterar o horário
                new_time = None
                time_change = input(COLOR_INFO + "Deseja alterar o horário? (S/N): " + COLOR_RESET).upper().strip()
                
                if time_change == "S":
                    new_time = input(COLOR_INFO + "Digite o novo horário (HH:MM ou 'now'): " + COLOR_RESET).strip()
                
                # Aprova o post
                success, message, post = self.post_manager.approve_post(post["id"], True, new_time)
                
                if success and post:
                    print(COLOR_SUCCESS + f"Sucesso! {message}" + COLOR_RESET)
                    
                    # Se o horário for 'now', pergunta se deseja postar agora
                    if post["scheduled_time"].lower() == "now":
                        post_now = input(COLOR_INFO + "Deseja postar agora? (S/N): " + COLOR_RESET).upper().strip()
                        
                        if post_now == "S":
                            if self._can_post_today() and self._can_post_this_month():
                                pub_success, pub_message, tweet_data = post_tweet(post["text"])
                                
                                if pub_success:
                                    print(COLOR_SUCCESS + f"Post publicado! {pub_message}" + COLOR_RESET)
                                    
                                    # Atualiza contadores
                                    self.monthly_posts += 1
                                    self.daily_posts += 1
                                    
                                    # Marca como publicado
                                    self.post_manager.mark_as_posted(post["id"])
                                else:
                                    print(COLOR_ERROR + f"Erro ao publicar! {pub_message}" + COLOR_RESET)
                            else:
                                print(COLOR_WARNING + "Não é possível postar devido aos limites da API!" + COLOR_RESET)
                    else:
                        print(COLOR_INFO + "Post aprovado e pronto para agendamento." + COLOR_RESET)
                else:
                    print(COLOR_ERROR + f"Erro! {message}" + COLOR_RESET)
            
            elif action == "R":
                # Rejeita o post
                success, message, _ = self.post_manager.approve_post(post["id"], False)
                
                if success:
                    print(COLOR_SUCCESS + f"Sucesso! {message}" + COLOR_RESET)
                else:
                    print(COLOR_ERROR + f"Erro! {message}" + COLOR_RESET)
            
            elif action == "S":
                print(COLOR_INFO + "Postagem ignorada (pulada)." + COLOR_RESET)
            
            elif action == "E":
                # Edita o post
                print(COLOR_INFO + "\nDigite o novo texto (deixe em branco para manter o atual):" + COLOR_RESET)
                new_text = input("> ").strip()
                
                print(COLOR_INFO + "\nDigite o novo horário (deixe em branco para manter o atual):" + COLOR_RESET)
                new_time = input("> ").strip()
                
                edit_ok, edit_msg, edited_post = self.post_manager.edit_post(
                    post["id"],
                    new_text=new_text if new_text else None,
                    new_time=new_time if new_time else None
                )
                
                if edit_ok:
                    print(COLOR_SUCCESS + f"Sucesso! {edit_msg}" + COLOR_RESET)
                    
                    # Pergunta se deseja aprovar após edição
                    approve_after_edit = input(COLOR_INFO + "Deseja aprovar esta postagem agora? (S/N): " + COLOR_RESET).upper().strip()
                    
                    if approve_after_edit == "S":
                        final_ok, final_msg, _ = self.post_manager.approve_post(post["id"], True)
                        
                        if final_ok:
                            print(COLOR_SUCCESS + f"Sucesso! {final_msg}" + COLOR_RESET)
                        else:
                            print(COLOR_ERROR + f"Erro! {final_msg}" + COLOR_RESET)
                else:
                    print(COLOR_ERROR + f"Erro! {edit_msg}" + COLOR_RESET)
            
            elif action == "C":
                print(COLOR_INFO + "Processo de aprovação cancelado." + COLOR_RESET)
                break
            
            input(COLOR_INFO + "\nPressione ENTER para continuar..." + COLOR_RESET)
        
        print(COLOR_INFO + "\nProcesso de aprovação concluído." + COLOR_RESET)
        input(COLOR_INFO + "\nPressione ENTER para voltar ao menu principal..." + COLOR_RESET)
    
    def _get_user_action_with_timeout(self, timeout_seconds):
        """
        Lê uma tecla do usuário com timeout.
        
        Args:
            timeout_seconds (int): Tempo de timeout em segundos
            
        Returns:
            str: Ação do usuário ou None se timeout
        """
        print(COLOR_INFO + f"Aguardando resposta... (timeout em {timeout_seconds} segundos)" + COLOR_RESET)
        
        # Caso especial para Windows
        if os.name == 'nt':
            import msvcrt
            start = time.time()
            action = None
            
            while time.time() - start < timeout_seconds and action is None:
                if msvcrt.kbhit():
                    tecla = msvcrt.getch()
                    try:
                        action = tecla.decode('utf-8', errors='ignore').upper()
                    except:
                        action = None
                time.sleep(0.05)
            
            return action
        else:
            # Em outros sistemas, use select
            import select
            start = time.time()
            action = None
            
            while time.time() - start < timeout_seconds and action is None:
                rlist, _, _ = select.select([sys.stdin], [], [], 0.1)
                if rlist:
                    action = sys.stdin.readline().strip().upper()
            
            return action
    
    def _schedule_approved_posts(self):
        """Interface para agendar postagens aprovadas."""
        self._clear_screen()
        
        print(COLOR_HEADER + "\n===== AGENDAR POSTAGENS =====" + COLOR_RESET)
        
        # Obtém posts aprovados
        posts = self.post_manager.get_posts("approved")
        
        if not posts:
            print(COLOR_INFO + "\nNão há postagens aprovadas para agendar." + COLOR_RESET)
            input(COLOR_INFO + "\nPressione ENTER para continuar..." + COLOR_RESET)
            return
        
        for i, post in enumerate(posts):
            # Ignora posts com horário 'now'
            if post["scheduled_time"].lower() == "now":
                continue
            
            self._clear_screen()
            print(COLOR_HEADER + "\n===== AGENDAR POSTAGENS =====" + COLOR_RESET)
            print(COLOR_INFO + f"\nPostagem {i+1} de {len(posts)}" + COLOR_RESET)
            
            # Exibe o post
            print(COLOR_INFO + f"\nID: {post['id'][:8]}" + COLOR_RESET)
            print(COLOR_INFO + f"Aprovado em: {self._format_datetime(post['approved_at'])}" + COLOR_RESET)
            print(COLOR_INFO + f"Horário agendado: {post['scheduled_time']}" + COLOR_RESET)
            print(COLOR_INFO + f"\nTexto: {post['text']}" + COLOR_RESET)
            
            print(COLOR_INFO + "\nOpções:" + COLOR_RESET)
            print(COLOR_SUCCESS + "A - Agendar para o horário definido" + COLOR_RESET)
            print(COLOR_INFO + "P - Postar agora")
            print("S - Pular")
            print("C - Cancelar agendamentos" + COLOR_RESET)
            
            action = input(COLOR_INFO + "\nEscolha uma opção: " + COLOR_RESET).upper().strip()
            
            if action == "A":
                # Agenda o post
                success, message, scheduled_post = self.post_manager.schedule_post(post["id"], True)
                
                if success and scheduled_post:
                    print(COLOR_SUCCESS + f"Sucesso! {message}" + COLOR_RESET)
                    
                    # Agenda no scheduler
                    hour, minute = scheduled_post["scheduled_time"].split(':')
                    
                    self.scheduler.add_job(
                        self._post_scheduled_tweet,
                        'cron',
                        hour=int(hour),
                        minute=int(minute),
                        id=f"post_{scheduled_post['id']}",
                        args=[scheduled_post["id"]],
                        replace_existing=True
                    )
                    
                    print(COLOR_INFO + f"Post agendado para {scheduled_post['scheduled_time']}" + COLOR_RESET)
                else:
                    print(COLOR_ERROR + f"Erro! {message}" + COLOR_RESET)
            
            elif action == "P":
                # Posta imediatamente
                if self._can_post_today() and self._can_post_this_month():
                    print(COLOR_INFO + "Publicando post imediatamente..." + COLOR_RESET)
                    
                    success, message, tweet_data = post_tweet(post["text"])
                    
                    if success:
                        print(COLOR_SUCCESS + f"Post publicado! {message}" + COLOR_RESET)
                        
                        # Atualiza contadores
                        self.monthly_posts += 1
                        self.daily_posts += 1
                        
                        # Marca como publicado
                        self.post_manager.mark_as_posted(post["id"])
                    else:
                        print(COLOR_ERROR + f"Erro ao publicar! {message}" + COLOR_RESET)
                else:
                    print(COLOR_WARNING + "Não é possível postar devido aos limites da API!" + COLOR_RESET)
            
            elif action == "C":
                print(COLOR_INFO + "Processo de agendamento cancelado." + COLOR_RESET)
                break
            
            input(COLOR_INFO + "\nPressione ENTER para continuar..." + COLOR_RESET)
        
        print(COLOR_INFO + "\nProcesso de agendamento concluído." + COLOR_RESET)
        input(COLOR_INFO + "\nPressione ENTER para voltar ao menu principal..." + COLOR_RESET)

# =============================================================================
# Função principal
# =============================================================================

def main():
    """Função principal que inicia o bot."""
    try:
        # Analisa argumentos de linha de comando
        args = parse_arguments()
        
        # Inicializa o bot
        bot = BotX()
        
        # Inicia o bot no modo apropriado
        bot.start(
            web_mode=args.web,
            web_host=args.host,
            web_port=args.port,
            open_browser=not args.no_browser
        )
    except KeyboardInterrupt:
        print("\n" + COLOR_INFO + "Bot encerrado pelo usuário." + COLOR_RESET)
    except Exception as e:
        print("\n" + COLOR_ERROR + f"Erro ao iniciar o bot: {e}" + COLOR_RESET)
        logger.error(f"Erro ao iniciar o bot: {e}", exc_info=True)
        
        # Espera um pouco antes de sair para o usuário ler as mensagens
        try:
            if os.name == 'nt':
                print("\nPressione qualquer tecla para sair...")
                import msvcrt
                msvcrt.getch()
            else:
                input("\nPressione Enter para sair...")
        except:
            pass

if __name__ == "__main__":
    main()
# post_manager.py
"""
Gerenciador de Postagens para Bot do X (Twitter)

Este módulo contém funções para gerenciar todas as operações relacionadas
às postagens, incluindo a criação, aprovação, agendamento e listagem de posts.
Também gerencia a persistência dos dados em arquivo JSON.

Versão modificada para debug adicional.
"""

import json
import os
import logging
import re
import uuid
from datetime import datetime
import time
import threading
from config import (
    POSTS_FILE, MAX_TWEET_LENGTH, 
    DATE_FORMAT, TIME_PATTERN
)

DEFAULT_POSTS_DATA = {
    "pending": [],
    "approved": [],
    "scheduled": [],
    "history": []
}

file_lock = threading.Lock()

def load_posts():
    """
    Carrega as postagens do arquivo posts.json ou inicializa um novo arquivo.
    Em caso de erro ao ler o arquivo, cria um novo com a estrutura padrão.
    """
    logging.info("DEBUG -> load_posts() chamado.")
    with file_lock:
        try:
            if not os.path.exists(POSTS_FILE):
                # Arquivo não existe: cria um vazio
                logging.info(f"DEBUG -> {POSTS_FILE} não existe. Criando arquivo novo.")
                posts_data = DEFAULT_POSTS_DATA.copy()
                save_posts(posts_data)
                return posts_data

            # Se existe, checar tamanho
            size = os.path.getsize(POSTS_FILE)
            logging.info(f"DEBUG -> {POSTS_FILE} existe, tamanho = {size} bytes.")
            if size == 0:
                logging.warning(f"Arquivo {POSTS_FILE} está vazio. Criando nova estrutura.")
                return DEFAULT_POSTS_DATA.copy()
            
            with open(POSTS_FILE, "r", encoding="utf-8") as f:
                file_content = f.read()
                logging.info(f"DEBUG -> Conteúdo lido de {POSTS_FILE} (len={len(file_content)}). Iniciando json.loads.")
                
                if not file_content.strip():
                    logging.warning(f"Arquivo {POSTS_FILE} está vazio após leitura.")
                    return DEFAULT_POSTS_DATA.copy()
                
                try:
                    posts_data = json.loads(file_content)
                    logging.info("DEBUG -> JSON decodificado com sucesso.")
                except (json.JSONDecodeError, ValueError) as e:
                    logging.error(f"Erro ao decodificar {POSTS_FILE}: {e}. Criando backup e novo arquivo.")
                    # Cria backup
                    try:
                        backup_file = f"{POSTS_FILE}.corrupted.{int(time.time())}"
                        with open(backup_file, "w", encoding="utf-8") as target:
                            target.write(file_content)
                        logging.info(f"Backup do arquivo corrompido criado em {backup_file}")
                    except Exception as backup_err:
                        logging.error(f"Erro ao criar backup do arquivo corrompido: {backup_err}")
                    
                    posts_data = DEFAULT_POSTS_DATA.copy()
                    save_posts(posts_data)
                    return posts_data
                
                required_keys = ["pending", "approved", "scheduled", "history"]
                missing_keys = [key for key in required_keys if key not in posts_data]
                if missing_keys:
                    logging.warning(f"Estrutura incorreta em {POSTS_FILE}. Faltam: {missing_keys}")
                    for mk in missing_keys:
                        posts_data[mk] = []

                # Garante que cada chave seja lista
                for key in required_keys:
                    if not isinstance(posts_data.get(key, []), list):
                        logging.warning(f"A chave '{key}' não é lista. Corrigindo para [].")
                        posts_data[key] = []
                
                # Verifica IDs
                for status in required_keys:
                    for post in posts_data[status]:
                        if "id" not in post:
                            logging.warning(f"Post sem ID em {status}. Adicionando ID.")
                            post["id"] = str(uuid.uuid4())
                
                logging.info("DEBUG -> load_posts() finalizado com sucesso.")
                return posts_data
        
        except Exception as e:
            logging.error(f"Erro inesperado em load_posts(): {e}")
            return DEFAULT_POSTS_DATA.copy()

def save_posts(posts_data):
    """
    Salva as postagens no arquivo posts.json.
    Inclui tratamento de erros para garantir que os dados não sejam perdidos.
    """
    logging.info("DEBUG -> save_posts() chamado.")
    with file_lock:
        try:
            if not isinstance(posts_data, dict):
                logging.error("Estrutura inválida: posts_data não é um dicionário.")
                return False
            
            required_keys = ["pending", "approved", "scheduled", "history"]
            for key in required_keys:
                if key not in posts_data or not isinstance(posts_data[key], list):
                    logging.warning(f"Corrigindo chave {key} para lista vazia.")
                    posts_data[key] = []
            
            for status in required_keys:
                for post in posts_data[status]:
                    if "id" not in post:
                        post["id"] = str(uuid.uuid4())
            
            with open(POSTS_FILE, "w", encoding="utf-8") as f:
                json.dump(posts_data, f, indent=4, ensure_ascii=False)
            
            logging.info("DEBUG -> save_posts() concluiu gravação com sucesso.")
            return True
        
        except Exception as e:
            logging.error(f"Erro em save_posts(): {e}")
            # Tenta salvar backup
            try:
                backup_file = f"{POSTS_FILE}.backup.{int(time.time())}.json"
                with open(backup_file, "w", encoding="utf-8") as f:
                    json.dump(posts_data, f, indent=4, ensure_ascii=False)
                logging.info(f"Backup salvo em {backup_file}")
                
                # Tenta restaurar
                try:
                    with open(backup_file, "r", encoding="utf-8") as f_in:
                        with open(POSTS_FILE, "w", encoding="utf-8") as f_out:
                            f_out.write(f_in.read())
                    logging.info("Arquivo principal restaurado do backup com sucesso.")
                    return True
                except Exception as restore_err:
                    logging.critical(f"Falha ao restaurar arquivo principal: {restore_err}")
                    return False
            except Exception as backup_err:
                logging.critical(f"Falha ao criar backup: {backup_err}")
                return False

def validate_time(time_str):
    if time_str.lower() == "now":
        return True
    return bool(TIME_PATTERN.match(time_str))

def sanitize_text(text):
    if not isinstance(text, str):
        return ""
    sanitized = ' '.join(text.strip().split())
    if len(sanitized) > MAX_TWEET_LENGTH:
        sanitized = sanitized[:MAX_TWEET_LENGTH]
    return sanitized

def create_post(text, time="now", posts_data=None):
    text = sanitize_text(text)
    if not text:
        return False, "O texto da postagem não pode estar vazio."
    if not validate_time(time):
        return False, "Formato de horário inválido."
    
    if posts_data is None:
        logging.info("DEBUG -> create_post() vai chamar load_posts().")
        posts_data = load_posts()
    
    post = {
        "id": str(uuid.uuid4()),
        "text": text,
        "time": time,
        "status": "pending",
        "created_at": datetime.now().isoformat()
    }
    posts_data["pending"].append(post)
    
    if save_posts(posts_data):
        return True, f"Postagem criada pendente: '{text[:30]}'"
    return False, "Erro ao salvar a postagem."

def edit_post(post_index, new_text=None, new_time=None, status="pending", posts_data=None):
    if posts_data is None:
        logging.info("DEBUG -> edit_post() vai chamar load_posts().")
        posts_data = load_posts()
    
    if status not in ["pending", "approved", "scheduled"]:
        return False, "Status inválido."
    
    if post_index < 0 or post_index >= len(posts_data[status]):
        return False, f"Índice {post_index} inválido para status '{status}'."
    
    post = posts_data[status][post_index]
    
    if new_text is not None:
        new_text = sanitize_text(new_text)
        if not new_text:
            return False, "O texto não pode ficar vazio."
        post["text"] = new_text
        post["edited_at"] = datetime.now().isoformat()
    
    if new_time is not None:
        if not validate_time(new_time):
            return False, "Formato de horário inválido."
        post["time"] = new_time
        post["edited_at"] = datetime.now().isoformat()
    
    if save_posts(posts_data):
        return True, f"Postagem {post_index+1} editada."
    return False, "Erro ao salvar alterações."

def delete_post(post_index, status="pending", posts_data=None):
    if posts_data is None:
        logging.info("DEBUG -> delete_post() vai chamar load_posts().")
        posts_data = load_posts()
    
    if status not in ["pending", "approved", "scheduled"]:
        return False, "Status inválido."
    if post_index < 0 or post_index >= len(posts_data[status]):
        return False, f"Índice {post_index} inválido para status '{status}'."
    
    removed = posts_data[status].pop(post_index)
    if save_posts(posts_data):
        return True, f"Postagem removida: '{removed['text'][:30]}'"
    return False, "Erro ao salvar após exclusão."

def approve_post(post_index, approve=True, new_time=None, posts_data=None):
    if posts_data is None:
        logging.info("DEBUG -> approve_post() vai chamar load_posts().")
        posts_data = load_posts()
    
    if post_index < 0 or post_index >= len(posts_data["pending"]):
        return False, "Índice inválido em pending.", None
    
    post = posts_data["pending"][post_index]
    
    if not approve:
        posts_data["pending"].pop(post_index)
        save_posts(posts_data)
        return True, "Postagem rejeitada.", None
    
    if new_time is not None:
        if not validate_time(new_time):
            return False, "Horário inválido.", None
        post["time"] = new_time
    
    post["status"] = "approved"
    post["approved_at"] = datetime.now().isoformat()
    posts_data["approved"].append(post)
    posts_data["pending"].pop(post_index)
    
    if save_posts(posts_data):
        return True, f"Postagem aprovada: '{post['text'][:30]}'", post
    return False, "Erro ao salvar aprovação.", None

def schedule_post(post_index, scheduled=True, posts_data=None):
    if posts_data is None:
        logging.info("DEBUG -> schedule_post() vai chamar load_posts().")
        posts_data = load_posts()
    
    if post_index < 0 or post_index >= len(posts_data["approved"]):
        return False, "Índice inválido em approved.", None
    
    post = posts_data["approved"][post_index]
    if post["time"].lower() == "now":
        return False, "Não é possível agendar horário 'now'.", None
    
    post_id = post.get("id")
    if scheduled and post_id:
        for sp in posts_data["scheduled"]:
            if sp.get("id") == post_id:
                return False, "Já está agendado.", None
    
    post["status"] = "scheduled" if scheduled else "approved"
    if scheduled:
        post["scheduled_at"] = datetime.now().isoformat()
        posts_data["scheduled"].append(post.copy())
        posts_data["approved"].pop(post_index)
        msg = f"Postagem agendada: '{post['text'][:30]}'"
    else:
        post["scheduled_at"] = None
        posts_data["approved"].append(post.copy())
        # remove da lista scheduled
        for i, p in enumerate(posts_data["scheduled"]):
            if p.get("id") == post_id:
                posts_data["scheduled"].pop(i)
                break
        msg = f"Agendamento removido: '{post['text'][:30]}'"
    
    if save_posts(posts_data):
        return True, msg, post
    return False, "Erro ao salvar agendamento.", None

def mark_as_posted(post, posts_data=None):
    if posts_data is None:
        logging.info("DEBUG -> mark_as_posted() vai chamar load_posts().")
        posts_data = load_posts()
    
    post["posted_at"] = datetime.now().isoformat()
    post["status"] = "posted"
    posts_data["history"].append(post.copy())
    
    pid = post.get("id")
    if pid:
        posts_data["scheduled"] = [p for p in posts_data["scheduled"] if p.get("id") != pid]
        posts_data["approved"] = [p for p in posts_data["approved"] if p.get("id") != pid]
    
    return save_posts(posts_data)

def get_scheduled_posts_for_recovery(posts_data=None):
    if posts_data is None:
        logging.info("DEBUG -> get_scheduled_posts_for_recovery() chamando load_posts().")
        posts_data = load_posts()
    return [post.copy() for post in posts_data["scheduled"]]

def get_post_by_id(post_id, status=None, posts_data=None):
    if posts_data is None:
        logging.info("DEBUG -> get_post_by_id() chama load_posts().")
        posts_data = load_posts()
    
    if status and status in posts_data:
        for i, p in enumerate(posts_data[status]):
            if p.get("id") == post_id:
                return p, status, i
        return None, None, -1
    
    for s in ["pending", "approved", "scheduled", "history"]:
        for i, p in enumerate(posts_data[s]):
            if p.get("id") == post_id:
                return p, s, i
    return None, None, -1

def get_post_list(status="all", posts_data=None):
    if posts_data is None:
        logging.info("DEBUG -> get_post_list() chamando load_posts().")
        posts_data = load_posts()
    
    result = []
    def fmt_text(t):
        return f"'{t[:50]}{'...' if len(t)>50 else ''}'"
    
    if status == "all" or status == "pending":
        for i, post in enumerate(posts_data["pending"]):
            ctime = post.get("created_at","N/A")
            try:
                ctime = datetime.fromisoformat(ctime).strftime(DATE_FORMAT)
            except:
                pass
            pid = post.get("id","N/A")[:8]
            result.append(f"Pendente #{i+1} [ID:{pid}]: {fmt_text(post['text'])} | Horário:{post['time']} | Criado:{ctime}")
    
    if status == "all" or status == "approved":
        for i, post in enumerate(posts_data["approved"]):
            atime = post.get("approved_at","N/A")
            try:
                atime = datetime.fromisoformat(atime).strftime(DATE_FORMAT)
            except:
                pass
            pid = post.get("id","N/A")[:8]
            result.append(f"Aprovado #{i+1} [ID:{pid}]: {fmt_text(post['text'])} | Horário:{post['time']} | Aprovado:{atime}")
    
    if status == "all" or status == "scheduled":
        for i, post in enumerate(posts_data["scheduled"]):
            stime = post.get("scheduled_at","N/A")
            try:
                stime = datetime.fromisoformat(stime).strftime(DATE_FORMAT)
            except:
                pass
            pid = post.get("id","N/A")[:8]
            result.append(f"Agendado #{i+1} [ID:{pid}]: {fmt_text(post['text'])} | Horário:{post['time']} | Agendado:{stime}")
    
    if status == "all" or status == "history":
        for i, post in enumerate(posts_data["history"]):
            ptime = post.get("posted_at","N/A")
            try:
                ptime = datetime.fromisoformat(ptime).strftime(DATE_FORMAT)
            except:
                pass
            pid = post.get("id","N/A")[:8]
            result.append(f"Publicado #{i+1} [ID:{pid}]: {fmt_text(post['text'])} | Horário:{post['time']} | Publicado:{ptime}")
    
    return result

def get_pending_now_posts(posts_data=None):
    if posts_data is None:
        logging.info("DEBUG -> get_pending_now_posts() chamando load_posts().")
        posts_data = load_posts()
    return [p.copy() for p in posts_data["approved"] if p.get("time","").lower() == "now"]

def get_stats(posts_data=None):
    if posts_data is None:
        logging.info("DEBUG -> get_stats() chamando load_posts().")
        posts_data = load_posts()
    
    stats = {
        "total_pending": len(posts_data["pending"]),
        "total_approved": len(posts_data["approved"]),
        "total_scheduled": len(posts_data["scheduled"]),
        "total_posted": len(posts_data["history"]),
        "total_all": sum(len(posts_data[s]) for s in ["pending","approved","scheduled","history"])
    }
    today = datetime.now().date()
    posts_today = 0
    for post in posts_data["history"]:
        if "posted_at" in post:
            try:
                posted_date = datetime.fromisoformat(post["posted_at"]).date()
                if posted_date == today:
                    posts_today += 1
            except (ValueError, TypeError):
                logging.warning(f"Data inválida no post ID:{post.get('id','')}")
    stats["posts_today"] = posts_today
    return stats

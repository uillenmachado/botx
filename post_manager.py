"""
Gerenciador de Postagens para Bot do X (Twitter)

Este módulo contém funções para gerenciar todas as operações relacionadas
às postagens, incluindo a criação, aprovação, agendamento e listagem de posts.
Também gerencia a persistência dos dados em arquivo JSON.

Autor: Uillen Machado
Repositório: github.com/uillenmachado/botx
"""

import json
import os
import logging
import re
import uuid
from datetime import datetime
import time
from config import (
    POSTS_FILE, MAX_TWEET_LENGTH, 
    DATE_FORMAT, TIME_PATTERN
)

# Estrutura básica do arquivo de posts
DEFAULT_POSTS_DATA = {
    "pending": [],    # Posts criados mas não aprovados
    "approved": [],   # Posts aprovados mas não agendados
    "scheduled": [],  # Posts aprovados e agendados
    "history": []     # Histórico de posts publicados
}

def load_posts():
    """
    Carrega as postagens do arquivo posts.json ou inicializa um novo arquivo.
    Em caso de erro ao ler o arquivo, cria um novo com a estrutura padrão.
    
    Returns:
        dict: Dicionário com as listas de posts pendentes, aprovados e agendados.
    """
    try:
        if os.path.exists(POSTS_FILE):
            # Verificação adicional do tamanho do arquivo para prevenir falhas
            if os.path.getsize(POSTS_FILE) == 0:
                logging.error(f"Arquivo {POSTS_FILE} está vazio. Criando nova estrutura.")
                return DEFAULT_POSTS_DATA.copy()
                
            with open(POSTS_FILE, "r", encoding="utf-8") as f:
                try:
                    file_content = f.read()
                    if not file_content.strip():
                        logging.error(f"Arquivo {POSTS_FILE} está vazio. Criando nova estrutura.")
                        return DEFAULT_POSTS_DATA.copy()
                    
                    posts_data = json.loads(file_content)
                    
                    # Verifica se o arquivo tem a estrutura correta
                    required_keys = ["pending", "approved", "scheduled", "history"]
                    missing_keys = [key for key in required_keys if key not in posts_data]
                    
                    if missing_keys:
                        logging.warning(f"Estrutura incorreta no arquivo posts.json. Chaves ausentes: {missing_keys}")
                        for key in missing_keys:
                            posts_data[key] = []
                    
                    # Verifica se as chaves são listas
                    for key in required_keys:
                        if not isinstance(posts_data.get(key, []), list):
                            logging.warning(f"A chave '{key}' em posts.json não é uma lista. Corrigindo...")
                            posts_data[key] = []
                    
                    # Retorna os dados carregados
                    return posts_data
                    
                except (json.JSONDecodeError, ValueError) as e:
                    logging.error(f"Erro ao decodificar {POSTS_FILE}: {e}. Criando backup e novo arquivo.")
                    
                    # Tenta criar um backup do arquivo corrompido
                    try:
                        backup_file = f"{POSTS_FILE}.corrupted.{int(time.time())}"
                        with open(POSTS_FILE, "r", encoding="utf-8") as source:
                            with open(backup_file, "w", encoding="utf-8") as target:
                                target.write(source.read())
                        logging.info(f"Backup do arquivo corrompido criado em {backup_file}")
                    except Exception as backup_err:
                        logging.error(f"Erro ao criar backup do arquivo corrompido: {backup_err}")
                    
                    return DEFAULT_POSTS_DATA.copy()
        else:
            # Arquivo não existe, cria um novo com a estrutura padrão
            posts_data = DEFAULT_POSTS_DATA.copy()
            save_posts(posts_data)
            logging.info(f"Arquivo {POSTS_FILE} criado.")
            return posts_data
            
    except Exception as e:
        logging.error(f"Erro ao carregar posts: {e}")
        return DEFAULT_POSTS_DATA.copy()

def save_posts(posts_data):
    """
    Salva as postagens no arquivo posts.json.
    Inclui tratamento de erros para garantir que os dados não sejam perdidos.
    
    Args:
        posts_data (dict): Dicionário com as listas de posts.
        
    Returns:
        bool: True se o arquivo foi salvo com sucesso, False caso contrário.
    """
    try:
        # Verificação adicional da estrutura antes de salvar
        if not isinstance(posts_data, dict):
            logging.error(f"Erro ao salvar posts: a estrutura não é um dicionário")
            return False
            
        required_keys = ["pending", "approved", "scheduled", "history"]
        for key in required_keys:
            if key not in posts_data:
                posts_data[key] = []
            elif not isinstance(posts_data[key], list):
                posts_data[key] = []
        
        with open(POSTS_FILE, "w", encoding="utf-8") as f:
            json.dump(posts_data, f, indent=4, ensure_ascii=False)
        return True
        
    except Exception as e:
        logging.error(f"Erro ao salvar posts: {e}")
        
        # Tenta salvar em um arquivo alternativo em caso de erro
        try:
            backup_file = f"{POSTS_FILE}.backup.{int(time.time())}.json"
            with open(backup_file, "w", encoding="utf-8") as f:
                json.dump(posts_data, f, indent=4, ensure_ascii=False)
            logging.info(f"Backup dos posts salvo em {backup_file}")
            
            # Tenta restaurar o arquivo principal a partir do backup
            try:
                with open(backup_file, "r", encoding="utf-8") as f_in:
                    with open(POSTS_FILE, "w", encoding="utf-8") as f_out:
                        f_out.write(f_in.read())
                logging.info(f"Arquivo principal restaurado a partir do backup")
                return True
            except Exception as restore_err:
                logging.critical(f"Falha ao restaurar arquivo principal: {restore_err}")
                return False
        except Exception as backup_err:
            logging.critical(f"Falha ao criar backup dos posts: {backup_err}")
            return False

def validate_time(time_str):
    """
    Valida se o horário está no formato correto (HH:MM).
    Aceita qualquer horário válido entre 00:00 e 23:59.
    
    Args:
        time_str (str): Horário no formato HH:MM ou "now".
        
    Returns:
        bool: True se o horário é válido, False caso contrário.
    """
    try:
        # Caso especial para postagem imediata
        if time_str == "now":
            return True
        
        # Verifica o formato usando expressão regular (HH:MM)
        if not TIME_PATTERN.match(time_str):
            return False
        
        return True
            
    except ValueError:
        return False

def sanitize_text(text):
    """
    Sanitiza o texto da postagem para evitar problemas com caracteres especiais.
    
    Args:
        text (str): Texto original da postagem.
        
    Returns:
        str: Texto sanitizado.
    """
    # Remove caracteres de controle e normaliza espaços em branco
    sanitized = ' '.join(text.strip().split())
    
    # Limita ao tamanho máximo permitido
    if len(sanitized) > MAX_TWEET_LENGTH:
        sanitized = sanitized[:MAX_TWEET_LENGTH]
        
    return sanitized

def create_post(text, time="now", posts_data=None):
    """
    Cria uma nova postagem e a adiciona à lista de pendentes.
    
    Args:
        text (str): Texto da postagem.
        time (str, optional): Horário para postagem (HH:MM) ou "now" para postar assim
                              que aprovado. Padrão é "now".
        posts_data (dict, optional): Dicionário com as listas de posts.
                                    Se None, carrega do arquivo.
    
    Returns:
        tuple: (bool, str) - Sucesso (True/False) e mensagem explicativa.
    """
    # Sanitização e validação do texto
    text = sanitize_text(text)
    
    if not text:
        return False, "O texto da postagem não pode estar vazio."
    
    if len(text) > MAX_TWEET_LENGTH:
        return False, f"O texto excede o limite de {MAX_TWEET_LENGTH} caracteres. Atual: {len(text)}"
    
    # Validação do horário
    if not validate_time(time):
        return False, f"Formato de horário inválido. Use o formato HH:MM ou 'now'."
    
    # Carrega os posts se não foram fornecidos
    if posts_data is None:
        posts_data = load_posts()
    
    # Cria o post com metadados e ID único
    post = {
        "id": str(uuid.uuid4()),  # Adiciona um ID único
        "text": text,
        "time": time,
        "status": "pending",
        "created_at": datetime.now().isoformat()
    }
    
    # Adiciona à lista de pendentes
    posts_data["pending"].append(post)
    
    # Salva as alterações
    if save_posts(posts_data):
        return True, f"Postagem criada e adicionada à lista de pendentes: '{text[:30]}{'...' if len(text) > 30 else ''}' às {time}"
    else:
        return False, "Erro ao salvar a postagem. Verifique o log para mais detalhes."

def edit_post(post_index, new_text=None, new_time=None, status="pending", posts_data=None):
    """
    Edita uma postagem existente.
    
    Args:
        post_index (int): Índice da postagem na lista.
        new_text (str, optional): Novo texto para a postagem.
        new_time (str, optional): Novo horário para a postagem.
        status (str, optional): Status da postagem a ser editada 
                               ("pending", "approved", "scheduled").
        posts_data (dict, optional): Dicionário com as listas de posts.
    
    Returns:
        tuple: (bool, str) - Sucesso (True/False) e mensagem explicativa.
    """
    # Carrega os posts se não foram fornecidos
    if posts_data is None:
        posts_data = load_posts()
    
    # Verifica se o status é válido
    if status not in ["pending", "approved", "scheduled"]:
        return False, "Status inválido."
    
    # Verifica se o índice é válido
    if post_index < 0 or post_index >= len(posts_data[status]):
        return False, f"Índice {post_index} de postagem inválido para status '{status}'."
    
    # Obtém o post
    post = posts_data[status][post_index]
    
    # Atualiza o texto se fornecido
    if new_text is not None:
        new_text = sanitize_text(new_text)
        if not new_text:
            return False, "O texto da postagem não pode estar vazio."
        if len(new_text) > MAX_TWEET_LENGTH:
            return False, f"O texto excede o limite de {MAX_TWEET_LENGTH} caracteres."
        post["text"] = new_text
        post["edited_at"] = datetime.now().isoformat()
    
    # Atualiza o horário se fornecido
    if new_time is not None:
        if not validate_time(new_time):
            return False, f"Formato de horário inválido. Use o formato HH:MM ou 'now'."
        post["time"] = new_time
        post["edited_at"] = datetime.now().isoformat()
    
    # Salva as alterações
    if save_posts(posts_data):
        return True, f"Postagem {post_index+1} editada com sucesso."
    else:
        return False, "Erro ao salvar as alterações. Verifique o log para mais detalhes."

def delete_post(post_index, status="pending", posts_data=None):
    """
    Exclui uma postagem.
    
    Args:
        post_index (int): Índice da postagem na lista.
        status (str, optional): Status da postagem a ser excluída 
                               ("pending", "approved", "scheduled").
        posts_data (dict, optional): Dicionário com as listas de posts.
    
    Returns:
        tuple: (bool, str) - Sucesso (True/False) e mensagem explicativa.
    """
    # Carrega os posts se não foram fornecidos
    if posts_data is None:
        posts_data = load_posts()
    
    # Verifica se o status é válido
    if status not in ["pending", "approved", "scheduled"]:
        return False, "Status inválido."
    
    # Verifica se o índice é válido
    if post_index < 0 or post_index >= len(posts_data[status]):
        return False, f"Índice {post_index} de postagem inválido para status '{status}'."
    
    # Remove o post
    removed_post = posts_data[status].pop(post_index)
    
    # Salva as alterações
    if save_posts(posts_data):
        return True, f"Postagem removida com sucesso: '{removed_post['text'][:30]}{'...' if len(removed_post['text']) > 30 else ''}'."
    else:
        return False, "Erro ao salvar as alterações após exclusão. Verifique o log para mais detalhes."

def approve_post(post_index, approve=True, new_time=None, posts_data=None):
    """
    Aprova ou rejeita uma postagem pendente.
    
    Args:
        post_index (int): Índice da postagem na lista de pendentes.
        approve (bool, optional): True para aprovar, False para rejeitar. Padrão é True.
        new_time (str, optional): Novo horário para postagem, se diferente do original.
        posts_data (dict, optional): Dicionário com as listas de posts.
                                    Se None, carrega do arquivo.
    
    Returns:
        tuple: (bool, str, dict) - Sucesso (True/False), mensagem explicativa e post afetado (ou None).
    """
    # Carrega os posts se não foram fornecidos
    if posts_data is None:
        posts_data = load_posts()
    
    # Verifica se o índice é válido
    if post_index < 0 or post_index >= len(posts_data["pending"]):
        return False, "Índice de postagem inválido.", None
    
    # Obtém o post
    post = posts_data["pending"][post_index]
    
    # Se rejeitado, simplesmente remove da lista de pendentes
    if not approve:
        posts_data["pending"].pop(post_index)
        save_posts(posts_data)
        return True, "Postagem rejeitada e removida da lista.", None
    
    # Se aprovado, atualiza o horário se fornecido
    if new_time is not None:
        if not validate_time(new_time):
            return False, f"Formato de horário inválido. Use o formato HH:MM ou 'now'.", None
        post["time"] = new_time
    
    # Atualiza status e timestamp
    post["status"] = "approved"
    post["approved_at"] = datetime.now().isoformat()
    
    # Move para a lista de aprovados
    posts_data["approved"].append(post)
    posts_data["pending"].pop(post_index)
    
    # Salva as alterações
    if save_posts(posts_data):
        return True, f"Postagem aprovada: '{post['text'][:30]}{'...' if len(post['text']) > 30 else ''}' para {post['time']}", post
    else:
        return False, "Erro ao salvar as alterações após aprovação. Verifique o log para mais detalhes.", None

def schedule_post(post_index, scheduled=True, posts_data=None):
    """
    Marca uma postagem aprovada como agendada.
    
    Args:
        post_index (int): Índice da postagem na lista de aprovados.
        scheduled (bool, optional): True para agendar, False para desagendar. Padrão é True.
        posts_data (dict, optional): Dicionário com as listas de posts.
                                    Se None, carrega do arquivo.
    
    Returns:
        tuple: (bool, str, dict) - Sucesso (True/False), mensagem explicativa e post afetado (ou None).
    """
    # Carrega os posts se não foram fornecidos
    if posts_data is None:
        posts_data = load_posts()
    
    # Verifica se o índice é válido
    if post_index < 0 or post_index >= len(posts_data["approved"]):
        return False, "Índice de postagem inválido.", None
    
    # Obtém o post
    post = posts_data["approved"][post_index]
    
    # Verifica se o horário é válido para agendamento
    if post["time"] == "now":
        return False, "Não é possível agendar uma postagem com horário 'now'.", None
    
    # Verificar se já não está agendado (usando ID único)
    post_id = post.get("id", None)
    if scheduled and post_id:
        # Verifica se já existe um post agendado com o mesmo ID
        for scheduled_post in posts_data["scheduled"]:
            if scheduled_post.get("id", None) == post_id:
                return False, f"Esta postagem já está agendada para {scheduled_post['time']}.", None
    
    # Atualiza status e timestamp
    post["status"] = "scheduled" if scheduled else "approved"
    post["scheduled_at"] = datetime.now().isoformat() if scheduled else None
    
    # Move para a lista apropriada
    if scheduled:
        posts_data["scheduled"].append(post)
        posts_data["approved"].pop(post_index)
        message = f"Postagem agendada: '{post['text'][:30]}{'...' if len(post['text']) > 30 else ''}' para {post['time']}"
    else:
        posts_data["approved"].append(post)
        # Encontra e remove da lista de agendados usando o ID único
        for i, p in enumerate(posts_data["scheduled"]):
            if p.get("id", None) == post_id:
                posts_data["scheduled"].pop(i)
                break
        message = f"Agendamento removido: '{post['text'][:30]}{'...' if len(post['text']) > 30 else ''}'"
    
    # Salva as alterações
    if save_posts(posts_data):
        return True, message, post
    else:
        return False, "Erro ao salvar as alterações após agendamento. Verifique o log para mais detalhes.", None

def mark_as_posted(post, posts_data=None):
    """
    Marca uma postagem como publicada e a remove da lista de agendados.
    
    Args:
        post (dict): Postagem a ser marcada como publicada.
        posts_data (dict, optional): Dicionário com as listas de posts.
                                    Se None, carrega do arquivo.
    
    Returns:
        bool: True se a operação foi bem-sucedida, False caso contrário.
    """
    # Carrega os posts se não foram fornecidos
    if posts_data is None:
        posts_data = load_posts()
    
    # Adiciona timestamp de publicação
    post["posted_at"] = datetime.now().isoformat()
    post["status"] = "posted"
    
    # Adiciona ao histórico
    posts_data["history"].append(post)
    
    # Remove da lista de agendados se estiver lá, usando o ID único
    post_id = post.get("id", None)
    if post_id:
        posts_data["scheduled"] = [p for p in posts_data["scheduled"] 
                                if p.get("id", None) != post_id]
    
    # Salva as alterações
    return save_posts(posts_data)

def get_scheduled_posts_for_recovery(posts_data=None):
    """
    Retorna a lista de posts agendados para recuperação de agendamentos.
    Útil para recriar agendamentos após reiniciar o bot.
    
    Args:
        posts_data (dict, optional): Dicionário com as listas de posts.
                                    Se None, carrega do arquivo.
    
    Returns:
        list: Lista de posts agendados.
    """
    # Carrega os posts se não foram fornecidos
    if posts_data is None:
        posts_data = load_posts()
        
    return posts_data["scheduled"]

def get_post_list(status="all", posts_data=None):
    """
    Retorna uma lista formatada de postagens de acordo com o status.
    
    Args:
        status (str, optional): Status das postagens ("pending", "approved", 
                               "scheduled", "history" ou "all"). Padrão é "all".
        posts_data (dict, optional): Dicionário com as listas de posts.
                                    Se None, carrega do arquivo.
    
    Returns:
        list: Lista de strings formatadas com as informações das postagens.
    """
    # Carrega os posts se não foram fornecidos
    if posts_data is None:
        posts_data = load_posts()
    
    result = []
    
    if status == "all" or status == "pending":
        for i, post in enumerate(posts_data["pending"]):
            created_at = datetime.fromisoformat(post["created_at"]).strftime(DATE_FORMAT) if "created_at" in post else "N/A"
            post_id = post.get("id", "N/A")[:8]  # Exibe apenas os primeiros 8 caracteres do ID
            result.append(f"Pendente #{i+1} [ID:{post_id}]: '{post['text'][:50]}{'...' if len(post['text']) > 50 else ''}' | Horário: {post['time']} | Criado em: {created_at}")
    
    if status == "all" or status == "approved":
        for i, post in enumerate(posts_data["approved"]):
            approved_at = datetime.fromisoformat(post["approved_at"]).strftime(DATE_FORMAT) if "approved_at" in post else "N/A"
            post_id = post.get("id", "N/A")[:8]
            result.append(f"Aprovado #{i+1} [ID:{post_id}]: '{post['text'][:50]}{'...' if len(post['text']) > 50 else ''}' | Horário: {post['time']} | Aprovado em: {approved_at}")
    
    if status == "all" or status == "scheduled":
        for i, post in enumerate(posts_data["scheduled"]):
            scheduled_at = datetime.fromisoformat(post["scheduled_at"]).strftime(DATE_FORMAT) if "scheduled_at" in post else "N/A"
            post_id = post.get("id", "N/A")[:8]
            result.append(f"Agendado #{i+1} [ID:{post_id}]: '{post['text'][:50]}{'...' if len(post['text']) > 50 else ''}' | Horário: {post['time']} | Agendado em: {scheduled_at}")
    
    if status == "all" or status == "history":
        for i, post in enumerate(posts_data["history"]):
            posted_at = datetime.fromisoformat(post["posted_at"]).strftime(DATE_FORMAT) if "posted_at" in post else "N/A"
            post_id = post.get("id", "N/A")[:8]
            result.append(f"Publicado #{i+1} [ID:{post_id}]: '{post['text'][:50]}{'...' if len(post['text']) > 50 else ''}' | Horário: {post['time']} | Publicado em: {posted_at}")
    
    return result

def get_stats(posts_data=None):
    """
    Retorna estatísticas sobre as postagens.
    
    Args:
        posts_data (dict, optional): Dicionário com as listas de posts.
                                    Se None, carrega do arquivo.
    
    Returns:
        dict: Dicionário com as estatísticas.
    """
    # Carrega os posts se não foram fornecidos
    if posts_data is None:
        posts_data = load_posts()
    
    stats = {
        "total_pending": len(posts_data["pending"]),
        "total_approved": len(posts_data["approved"]),
        "total_scheduled": len(posts_data["scheduled"]),
        "total_posted": len(posts_data["history"]),
        "total_all": len(posts_data["pending"]) + len(posts_data["approved"]) + 
                     len(posts_data["scheduled"]) + len(posts_data["history"])
    }
    
    # Estatísticas por dia (posts publicados)
    today = datetime.now().date()
    posts_today = 0
    
    for post in posts_data["history"]:
        if "posted_at" in post:
            posted_date = datetime.fromisoformat(post["posted_at"]).date()
            if posted_date == today:
                posts_today += 1
    
    stats["posts_today"] = posts_today
    
    return stats
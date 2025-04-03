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
from datetime import datetime
import time
from config import (
    POSTS_FILE, START_HOUR, END_HOUR, MAX_TWEET_LENGTH, 
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
            with open(POSTS_FILE, "r", encoding="utf-8") as f:
                try:
                    posts_data = json.load(f)
                    
                    # Verifica se o arquivo tem a estrutura correta
                    required_keys = ["pending", "approved", "scheduled"]
                    if not all(key in posts_data for key in required_keys):
                        logging.warning("Estrutura incorreta no arquivo posts.json. Adicionando chaves ausentes.")
                        for key in required_keys:
                            if key not in posts_data:
                                posts_data[key] = []
                    
                    # Adiciona a chave history se não existir
                    if "history" not in posts_data:
                        posts_data["history"] = []
                    
                    # Retorna os dados carregados
                    return posts_data
                    
                except (json.JSONDecodeError, ValueError) as e:
                    logging.error(f"Erro ao ler {POSTS_FILE}: {e}. Criando novo arquivo.")
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
        except Exception as backup_err:
            logging.critical(f"Falha ao criar backup dos posts: {backup_err}")
        
        return False

def validate_time(time_str):
    """
    Valida se o horário está no formato correto e dentro do intervalo permitido.
    Usa expressão regular para validar o formato HH:MM.
    
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
            
        # Verifica se está dentro do intervalo permitido
        horario_dt = datetime.strptime(time_str, "%H:%M")
        start_dt = datetime.strptime(START_HOUR, "%H:%M")
        end_dt = datetime.strptime(END_HOUR, "%H:%M")
        
        return start_dt.time() <= horario_dt.time() <= end_dt.time()
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
        return False, f"Formato de horário inválido ou fora do intervalo permitido ({START_HOUR}-{END_HOUR})."
    
    # Carrega os posts se não foram fornecidos
    if posts_data is None:
        posts_data = load_posts()
    
    # Cria o post com metadados
    post = {
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
            return False, f"Formato de horário inválido ou fora do intervalo permitido ({START_HOUR}-{END_HOUR})."
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
            return False, f"Formato de horário inválido ou fora do intervalo permitido ({START_HOUR}-{END_HOUR}).", None
        post["time"] = new_time
    
    # Atualiza status e timestamp
    post["status"] = "approved"
    post["approved_at"] = datetime.now().isoformat()
    
    # Move para a lista de aprovados
    posts_data["approved"].append(post)
    posts_data["pending"].pop(post_index)
    
    # Salva as alterações
    save_posts(posts_data)
    
    return True, f"Postagem aprovada: '{post['text'][:30]}{'...' if len(post['text']) > 30 else ''}' para {post['time']}", post

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
        # Encontra e remove da lista de agendados
        for i, p in enumerate(posts_data["scheduled"]):
            if p["text"] == post["text"] and p["time"] == post["time"]:
                posts_data["scheduled"].pop(i)
                break
        message = f"Agendamento removido: '{post['text'][:30]}{'...' if len(post['text']) > 30 else ''}'"
    
    # Salva as alterações
    save_posts(posts_data)
    
    return True, message, post

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
    
    # Remove da lista de agendados se estiver lá
    posts_data["scheduled"] = [p for p in posts_data["scheduled"] 
                             if p["text"] != post["text"] or p["time"] != post["time"]]
    
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
            result.append(f"Pendente #{i+1}: '{post['text'][:50]}{'...' if len(post['text']) > 50 else ''}' | Horário: {post['time']} | Criado em: {created_at}")
    
    if status == "all" or status == "approved":
        for i, post in enumerate(posts_data["approved"]):
            approved_at = datetime.fromisoformat(post["approved_at"]).strftime(DATE_FORMAT) if "approved_at" in post else "N/A"
            result.append(f"Aprovado #{i+1}: '{post['text'][:50]}{'...' if len(post['text']) > 50 else ''}' | Horário: {post['time']} | Aprovado em: {approved_at}")
    
    if status == "all" or status == "scheduled":
        for i, post in enumerate(posts_data["scheduled"]):
            scheduled_at = datetime.fromisoformat(post["scheduled_at"]).strftime(DATE_FORMAT) if "scheduled_at" in post else "N/A"
            result.append(f"Agendado #{i+1}: '{post['text'][:50]}{'...' if len(post['text']) > 50 else ''}' | Horário: {post['time']} | Agendado em: {scheduled_at}")
    
    if status == "all" or status == "history":
        for i, post in enumerate(posts_data["history"]):
            posted_at = datetime.fromisoformat(post["posted_at"]).strftime(DATE_FORMAT) if "posted_at" in post else "N/A"
            result.append(f"Publicado #{i+1}: '{post['text'][:50]}{'...' if len(post['text']) > 50 else ''}' | Horário: {post['time']} | Publicado em: {posted_at}")
    
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
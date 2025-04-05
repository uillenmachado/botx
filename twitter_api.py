"""
Interface com a API do X (Twitter) para Bot

Este módulo gerencia toda a comunicação com a API do X (Twitter),
incluindo autenticação, busca de tendências e publicação de tweets.

Recursos principais:
- Autenticação com a API v1.1 e v2 do X (Twitter)
- Sistema robusto de retry com backoff exponencial
- Tratamento abrangente de erros com mensagens amigáveis
- Funções para postar tweets, buscar tendências e obter informações do usuário

Autor: Uillen Machado (com melhorias)
Repositório: github.com/uillenmachado/botx
"""

import tweepy # type: ignore
import logging
import time
import sys
import re
from functools import wraps
from datetime import datetime
import json

from config import (
    API_KEY, API_KEY_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET, 
    BEARER_TOKEN, WOEID_GLOBAL, NUM_TRENDS, MAX_RETRIES, INITIAL_BACKOFF,
    LOG_DIR, TIMEZONE_OBJ  # Importando o objeto timezone configurado
)

# Configuração de logging específica para este módulo
logger = logging.getLogger(__name__)

# Variáveis globais para armazenar clientes da API
client = None  # Cliente da API v2
api_v1 = None  # Cliente da API v1.1

# Status de autenticação
auth_status = {
    "authenticated": False,
    "username": None,
    "last_error": None,
    "last_auth_attempt": None
}

# =============================================================================
# Funções de utilidade para retry e tratamento de erros
# =============================================================================

def retry_with_backoff(max_retries=MAX_RETRIES, initial_backoff=INITIAL_BACKOFF):
    """
    Decorator para tentar executar uma função várias vezes com backoff exponencial em caso de falha.
    
    Args:
        max_retries (int): Número máximo de tentativas
        initial_backoff (int): Tempo inicial de espera entre tentativas em segundos
        
    Returns:
        function: Função decorada com retry
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            backoff = initial_backoff
            last_exception = None
            
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except tweepy.TweepyException as e:
                    last_exception = e
                    error_msg = str(e)
                    retries += 1
                    
                    # Tratamento especial para erros de limite de taxa
                    if "rate limit" in error_msg.lower() or "429" in error_msg:
                        wait_time = backoff * 2  # Espera mais para rate limits
                        logger.warning(f"Limite de taxa atingido. Aguardando {wait_time} segundos.")
                    else:
                        wait_time = backoff
                    
                    if retries == max_retries:
                        logger.error(f"Falha após {max_retries} tentativas: {e}")
                        break
                        
                    logger.warning(f"Tentativa {retries}/{max_retries} falhou: {e}. "
                                   f"Tentando novamente em {wait_time} segundos.")
                    time.sleep(wait_time)
                    backoff *= 2  # Backoff exponencial
                    
                except Exception as e:
                    last_exception = e
                    retries += 1
                    logger.error(f"Erro não esperado: {e}")
                    if retries == max_retries:
                        break
                    logger.warning(f"Tentativa {retries}/{max_retries}. "
                                   f"Tentando novamente em {backoff} segundos.")
                    time.sleep(backoff)
                    backoff *= 2
            
            # Se chegamos aqui, todas as tentativas falharam
            if last_exception:
                error_type = type(last_exception).__name__
                error_message = str(last_exception)
                logger.error(f"Todas as tentativas falharam. Último erro ({error_type}): {error_message}")
                
                # Criamos um retorno amigável baseado no tipo de erro
                if isinstance(last_exception, tweepy.TweepyException):
                    error_msg = str(last_exception).lower()
                    if "rate limit" in error_msg or "429" in error_msg:
                        return False, "Limite de taxa da API excedido. Tente novamente mais tarde.", None
                    elif "authentication" in error_msg or "401" in error_msg:
                        return False, "Erro de autenticação. Verifique suas credenciais da API.", None
                    else:
                        return False, f"Erro da API do X: {error_message}", None
                else:
                    return False, f"Erro inesperado: {error_message}", None
            
            return False, "Erro desconhecido durante a operação.", None
            
        return wrapper
    return decorator

def parse_api_error(e):
    """
    Analisa a exceção da API e retorna uma mensagem de erro amigável.
    
    Args:
        e (Exception): Exceção capturada
        
    Returns:
        str: Mensagem de erro amigável
    """
    error_msg = str(e).lower()
    
    # Erros de autenticação
    if "authentication" in error_msg or "401" in error_msg:
        return "Erro de autenticação. Verifique suas credenciais da API."
    
    # Erros de limite de taxa
    elif "rate limit" in error_msg or "429" in error_msg:
        return "Limite de taxa excedido. Aguarde alguns minutos e tente novamente."
    
    # Erros de conteúdo
    elif "duplicate content" in error_msg:
        return "O X não permite postar o mesmo texto duas vezes seguidas."
    elif "text is too long" in error_msg:
        return "O texto excede o limite de caracteres permitido pelo X."
    
    # Erros de aplicação
    elif "application suspended" in error_msg:
        return "Sua aplicação do X foi suspensa. Visite o portal de desenvolvedores para mais informações."
    elif "verification required" in error_msg:
        return "Verifique seu e-mail ou telefone na sua conta do X."
    
    # Erro genérico
    else:
        return f"Erro da API do X: {str(e)}"

# =============================================================================
# Funções de validação de texto para tweets
# =============================================================================

def validate_tweet_text(text):
    """
    Valida e sanitiza o texto de um tweet para evitar problemas com a API.
    
    Args:
        text (str): Texto do tweet a ser validado
        
    Returns:
        tuple: (bool, str, str) - Sucesso, mensagem e texto sanitizado
    """
    if not text or not text.strip():
        return False, "O texto do tweet não pode estar vazio.", ""
    
    # Limita o tamanho do texto
    if len(text) > 280:
        return False, f"O texto excede o limite de 280 caracteres. Atual: {len(text)}", text[:280]
    
    # Sanitiza o texto removendo caracteres problemáticos e controlando emojis
    sanitized_text = sanitize_tweet_text(text)
    
    # Verifica se o texto foi alterado significativamente após a sanitização
    if len(sanitized_text.strip()) == 0:
        return False, "O texto contém apenas caracteres inválidos.", ""
    
    # Verifica se o texto foi reduzido em mais de 10% após a sanitização
    reduction_percent = (len(text) - len(sanitized_text)) / len(text) * 100
    if reduction_percent > 10:
        return True, f"Aviso: {reduction_percent:.1f}% do texto foi removido durante a sanitização.", sanitized_text
    
    return True, "Texto válido para publicação.", sanitized_text

def sanitize_tweet_text(text):
    """
    Sanitiza o texto do tweet removendo caracteres problemáticos e controlando emojis.
    
    Args:
        text (str): Texto original do tweet
        
    Returns:
        str: Texto sanitizado
    """
    # Primeiro, remove caracteres de controle exceto quebras de linha e tabs
    sanitized = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    
    # Substitui múltiplas quebras de linha consecutivas por apenas uma
    sanitized = re.sub(r'(\r\n|\n|\r){3,}', '\n\n', sanitized)
    
    # Trata caracteres unicode específicos que podem causar problemas
    # Mantém emojis válidos, mas remove caracteres inválidos
    
    # Remove Zero Width Joiners extras que poderiam corromper emojis
    sanitized = re.sub(r'\u200D{2,}', '\u200D', sanitized)
    
    # Remove caracteres de formatação raros que podem causar problemas
    sanitized = re.sub(r'[\u2060\u200B\u200C\u200E\u200F\u061C]', '', sanitized)
    
    # Trata combinações potencialmente problemáticas de emojis
    # Este é um enfoque conservador. Se necessário, podemos ser mais específicos.
    emoji_combining_sequences = [
        # Exemplos de sequências que podem causar problemas em algumas plataformas
        r'\uFE0F\u20E3',  # Keycap sequence
        r'[\U0001F1E6-\U0001F1FF]{3,}',  # Limita bandeiras a no máximo 2 caracteres
    ]
    
    for sequence in emoji_combining_sequences:
        sanitized = re.sub(sequence, '', sanitized)
    
    # Remove espaços extras no início e fim
    sanitized = sanitized.strip()
    
    return sanitized

# =============================================================================
# Funções de API
# =============================================================================

def initialize_api():
    """
    Inicializa a conexão com a API do X, tanto a versão 1.1 (para tendências)
    quanto a versão 2 (para postagens).
    
    Returns:
        tuple: (bool, str) - Sucesso (True/False) e mensagem explicativa.
    """
    global client, api_v1, auth_status
    
    auth_status["last_auth_attempt"] = datetime.now(TIMEZONE_OBJ)
    
    try:
        # Verifica se temos todas as credenciais necessárias
        if not all([API_KEY, API_KEY_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET, BEARER_TOKEN]):
            missing_creds = []
            if not API_KEY: missing_creds.append("API_KEY")
            if not API_KEY_SECRET: missing_creds.append("API_KEY_SECRET")
            if not ACCESS_TOKEN: missing_creds.append("ACCESS_TOKEN")
            if not ACCESS_TOKEN_SECRET: missing_creds.append("ACCESS_TOKEN_SECRET")
            if not BEARER_TOKEN: missing_creds.append("BEARER_TOKEN")
            
            missing_str = ", ".join(missing_creds)
            error_msg = f"Credenciais ausentes: {missing_str}. Verifique seu arquivo .env."
            logger.error(error_msg)
            
            auth_status["authenticated"] = False
            auth_status["last_error"] = error_msg
            
            return False, error_msg
        
        # Inicializa cliente da API v2 (para postagens)
        client = tweepy.Client(
            bearer_token=BEARER_TOKEN,
            consumer_key=API_KEY,
            consumer_secret=API_KEY_SECRET,
            access_token=ACCESS_TOKEN,
            access_token_secret=ACCESS_TOKEN_SECRET
        )
        
        # Inicializa cliente da API v1.1 (para tendências)
        auth = tweepy.OAuth1UserHandler(
            API_KEY, API_KEY_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET
        )
        api_v1 = tweepy.API(auth)
        
        # Teste de conexão com tratamento de erros aprimorado
        try:
            # Verifica se consegue obter as informações do usuário
            user_info = client.get_me()
            if not user_info or not hasattr(user_info, "data"):
                error_msg = "Erro ao obter informações do usuário. Verifique suas credenciais."
                logger.error(error_msg)
                
                auth_status["authenticated"] = False
                auth_status["last_error"] = error_msg
                
                return False, error_msg
                
            username = user_info.data.username
            
            # Atualiza o status de autenticação
            auth_status["authenticated"] = True
            auth_status["username"] = username
            auth_status["last_error"] = None
            
            logger.info(f"Conexão com a API do X estabelecida com sucesso. Usuário: @{username}")
            return True, f"Conectado à API do X como @{username}"
        
        except tweepy.TweepyException as e:
            error_msg = parse_api_error(e)
            logger.error(f"Erro ao verificar autenticação: {error_msg}")
            
            auth_status["authenticated"] = False
            auth_status["last_error"] = error_msg
            
            return False, error_msg
            
    except tweepy.TweepyException as e:
        error_msg = parse_api_error(e)
        logger.error(f"Erro ao conectar com a API do X: {error_msg}")
        
        auth_status["authenticated"] = False
        auth_status["last_error"] = error_msg
        
        return False, error_msg
    except Exception as e:
        error_msg = f"Erro inesperado ao inicializar API: {e}"
        logger.error(error_msg)
        
        auth_status["authenticated"] = False
        auth_status["last_error"] = error_msg
        
        return False, error_msg

def ensure_auth():
    """
    Garante que a API está autenticada antes de executar uma operação.
    Tenta reconectar se necessário.
    
    Returns:
        bool: True se autenticado, False caso contrário
    """
    global auth_status
    
    # Se já estamos autenticados, retorne True
    if auth_status["authenticated"] and client is not None and api_v1 is not None:
        return True
    
    # Tenta inicializar a API
    success, _ = initialize_api()
    return success

@retry_with_backoff()
def get_trends():
    """
    Busca as tendências globais do X usando a API v1.1.
    
    Returns:
        tuple: (list, datetime) - Lista com as tendências globais e timestamp da consulta.
              Em caso de erro, retorna uma lista com mensagem de erro.
    """
    global api_v1
    
    # Garante que estamos autenticados
    if not ensure_auth():
        return [{"name": "Erro de autenticação. Verifique suas credenciais.", "volume": "N/A"}], datetime.now(TIMEZONE_OBJ)
        
    try:
        trends = api_v1.get_place_trends(id=WOEID_GLOBAL)
        timestamp = datetime.now(TIMEZONE_OBJ)
        
        # Validação mais robusta da resposta da API
        if not trends:
            logger.warning("API retornou resposta vazia para tendências.")
            return [{"name": "Não foi possível obter tendências", "volume": "N/A"}], timestamp
            
        if not isinstance(trends, list) or len(trends) == 0:
            logger.warning(f"API retornou resposta em formato inesperado: {type(trends)}")
            return [{"name": "Resposta da API em formato inesperado", "volume": "N/A"}], timestamp
            
        if not isinstance(trends[0], dict) or "trends" not in trends[0]:
            logger.warning(f"Formato de tendências inesperado: {trends}")
            return [{"name": "Formato de tendências inesperado", "volume": "N/A"}], timestamp
        
        # Extrai e filtra as tendências
        trend_list = []
        for trend in trends[0]["trends"][:NUM_TRENDS]:
            name = trend.get("name", "N/A")
            volume = trend.get("tweet_volume", "N/A")
            trend_list.append({
                "name": name,
                "volume": volume
            })
        
        # Verifica se realmente conseguimos extrair tendências
        if not trend_list:
            logger.warning("Nenhuma tendência encontrada na resposta da API.")
            return [{"name": "Nenhuma tendência disponível", "volume": "N/A"}], timestamp
        
        # Registra as tendências encontradas
        trend_names = [t["name"] for t in trend_list]
        logger.info(f"Tendências atualizadas: {', '.join(trend_names)}")
        
        # Tenta salvar as tendências em um arquivo para análise histórica
        try:
            trends_file = f"{LOG_DIR}/trends_{datetime.now(TIMEZONE_OBJ).strftime('%Y%m%d')}.json"
            with open(trends_file, 'a', encoding='utf-8') as f:
                json.dump({
                    "timestamp": timestamp.isoformat(),
                    "trends": trend_list
                }, f, ensure_ascii=False)
                f.write('\n')  # Adiciona uma quebra de linha
        except Exception as e:
            logger.warning(f"Não foi possível salvar tendências no arquivo: {e}")
        
        return trend_list, timestamp
            
    except tweepy.TweepyException as e:
        error_msg = parse_api_error(e)
        logger.error(f"Erro ao buscar tendências: {error_msg}")
        return [{"name": f"Erro ao buscar tendências: {error_msg}", "volume": "N/A"}], datetime.now(TIMEZONE_OBJ)
            
    except Exception as e:
        logger.error(f"Erro inesperado ao buscar tendências: {e}")
        return [{"name": "Erro inesperado ao buscar tendências", "volume": "N/A"}], datetime.now(TIMEZONE_OBJ)

@retry_with_backoff()
def post_tweet(text):
    """
    Publica um tweet.
    
    Args:
        text (str): Texto do tweet a ser publicado.
    
    Returns:
        tuple: (bool, str, dict) - Sucesso (True/False), mensagem explicativa e dados do tweet.
    """
    global client
    
    # Garante que estamos autenticados
    if not ensure_auth():
        return False, "Erro de autenticação. Verifique suas credenciais.", None
    
    try:
        # Valida e sanitiza o texto do tweet
        valid, message, sanitized_text = validate_tweet_text(text)
        
        if not valid:
            return False, message, None
        
        # Se o texto foi sanitizado e modificado, registra o aviso
        if sanitized_text != text:
            logger.warning(f"Texto do tweet sanitizado: {message}")
            # Usa o texto sanitizado para a postagem
            text = sanitized_text
        
        # Publica o tweet
        response = client.create_tweet(text=text)
        
        # Verifica se a resposta é válida
        if not response or not hasattr(response, "data"):
            return False, "Resposta da API inválida ao tentar publicar tweet.", None
            
        # Extrai o ID do tweet
        tweet_id = response.data['id']
        
        logger.info(f"Tweet publicado com sucesso. ID: {tweet_id}")
        return True, f"Tweet publicado com sucesso. ID: {tweet_id}", {
            "id": tweet_id,
            "text": text,
            "posted_at": datetime.now(TIMEZONE_OBJ).isoformat()
        }
        
    except tweepy.TweepyException as e:
        error_msg = parse_api_error(e)
        logger.error(f"Erro ao publicar tweet: {error_msg}")
        return False, error_msg, None
            
    except Exception as e:
        error_msg = f"Erro inesperado ao publicar tweet: {e}"
        logger.error(error_msg)
        return False, error_msg, None

@retry_with_backoff()
def get_user_info():
    """
    Obtém informações do usuário autenticado.
    
    Returns:
        tuple: (bool, dict) - Sucesso (True/False) e dicionário com informações do usuário.
    """
    global client
    
    # Garante que estamos autenticados
    if not ensure_auth():
        return False, {"error": "Erro de autenticação. Verifique suas credenciais."}
        
    try:
        user_info = client.get_me(user_fields=["name", "username", "description", "public_metrics"])
        
        if user_info and hasattr(user_info, "data"):
            data = user_info.data
            
            user_data = {
                "id": data.id,
                "name": data.name if hasattr(data, "name") else "N/A",
                "username": data.username if hasattr(data, "username") else "N/A",
                "description": data.description if hasattr(data, "description") else "N/A"
            }
            
            # Adiciona métricas públicas se disponíveis
            if hasattr(data, "public_metrics") and data.public_metrics is not None:
                metrics = data.public_metrics
                user_data["followers"] = metrics.get("followers_count", 0)
                user_data["following"] = metrics.get("following_count", 0)
                user_data["tweets"] = metrics.get("tweet_count", 0)
            
            return True, user_data
        else:
            return False, {"error": "Não foi possível obter informações do usuário"}
            
    except tweepy.TweepyException as e:
        error_msg = parse_api_error(e)
        logger.error(f"Erro ao obter informações do usuário: {error_msg}")
        return False, {"error": error_msg}
            
    except Exception as e:
        error_msg = f"Erro inesperado ao obter informações do usuário: {e}"
        logger.error(error_msg)
        return False, {"error": error_msg}

def check_api_limits():
    """
    Verifica os limites atuais da API.
    
    Returns:
        dict: Dicionário com informações sobre os limites da API.
    """
    # Nota: A API v2 do Twitter ainda não oferece um endpoint fácil para 
    # verificar os limites restantes como a v1.1 fazia com get_rate_limit_status
    
    status = {
        "authenticated": auth_status["authenticated"],
        "username": auth_status["username"],
        "last_auth_attempt": auth_status["last_auth_attempt"],
        "limits": {
            "post_tweets": {
                "limit": 500,
                "remaining": "Desconhecido",
                "reset": "Mensal"
            },
            "trends": {
                "limit": 75,
                "period": "15 minutos",
                "note": "O bot busca tendências apenas 1 vez por dia, muito abaixo do limite."
            }
        }
    }
    
    if auth_status["last_error"]:
        status["last_error"] = auth_status["last_error"]
    
    return status

def health_check():
    """
    Executa uma verificação de saúde da API.
    
    Returns:
        dict: Estado de saúde da API.
    """
    # Garante que estamos autenticados
    authenticated = ensure_auth()
    
    # Constrói o status de saúde
    health = {
        "authenticated": authenticated,
        "username": auth_status["username"] if authenticated else None,
        "timestamp": datetime.now(TIMEZONE_OBJ).isoformat(),
        "status": "online" if authenticated else "offline"
    }
    
    if auth_status["last_error"]:
        health["last_error"] = auth_status["last_error"]
    
    return health
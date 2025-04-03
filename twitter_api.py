"""
Interface com a API do X (Twitter) para Bot

Este módulo gerencia toda a comunicação com a API do X (Twitter),
incluindo autenticação, busca de tendências e publicação de tweets.

Separar as funções de API em um módulo específico facilita a manutenção
e permite testar o bot sem precisar se conectar à API real.

Autor: Uillen Machado
Repositório: github.com/uillenmachado/botx
"""

import tweepy # type: ignore
import logging
import time
from functools import wraps
from datetime import datetime

from config import (
    API_KEY, API_KEY_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET, 
    BEARER_TOKEN, WOEID_GLOBAL, NUM_TRENDS, MAX_RETRIES, INITIAL_BACKOFF
)

# Variáveis globais para armazenar clientes da API
client = None  # Cliente da API v2
api_v1 = None  # Cliente da API v1.1

# Função para retry com backoff
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
                except Exception as e:
                    last_exception = e
                    retries += 1
                    if retries == max_retries:
                        logging.error(f"Falha após {max_retries} tentativas: {e}")
                        break
                    logging.warning(f"Tentativa {retries} falhou: {e}. Tentando novamente em {backoff} segundos.")
                    time.sleep(backoff)
                    backoff *= 2  # Backoff exponencial
            
            # Se chegamos aqui, todas as tentativas falharam
            if last_exception:
                raise last_exception
            return None
            
        return wrapper
    return decorator

def initialize_api():
    """
    Inicializa a conexão com a API do X, tanto a versão 1.1 (para tendências)
    quanto a versão 2 (para postagens).
    
    Returns:
        tuple: (bool, str) - Sucesso (True/False) e mensagem explicativa.
    """
    global client, api_v1
    
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
            logging.error(error_msg)
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
        
        # Teste de conexão
        # Verifica se consegue obter as informações do usuário
        user_info = client.get_me()
        if not user_info or not hasattr(user_info, "data"):
            return False, "Erro ao obter informações do usuário. Verifique suas credenciais."
            
        username = user_info.data.username
        
        logging.info(f"Conexão com a API do X estabelecida com sucesso. Usuário: @{username}")
        return True, f"Conectado à API do X como @{username}"
        
    except tweepy.TweepyException as e:
        error_msg = str(e)
        logging.error(f"Erro ao conectar com a API do X: {error_msg}")
        
        # Tratamento mais específico de erros de autenticação
        if "authentication" in error_msg.lower() or "401" in error_msg:
            return False, "Erro de autenticação. Verifique suas credenciais da API."
        elif "rate limit" in error_msg.lower() or "429" in error_msg:
            return False, "Limite de taxa excedido ao conectar com a API. Tente novamente mais tarde."
        else:
            return False, f"Erro ao conectar com a API do X: {error_msg}"
    except Exception as e:
        logging.error(f"Erro inesperado ao inicializar API: {e}")
        return False, f"Erro inesperado ao inicializar API: {e}"

@retry_with_backoff()
def get_trends():
    """
    Busca as tendências globais do X usando a API v1.1.
    
    Returns:
        tuple: (list, datetime) - Lista com as tendências globais e timestamp da consulta.
              Em caso de erro, retorna uma lista com mensagem de erro.
    """
    global api_v1
    
    if api_v1 is None:
        success, message = initialize_api()
        if not success:
            return [{"name": message, "volume": "N/A"}], datetime.now()
        
    try:
        trends = api_v1.get_place_trends(id=WOEID_GLOBAL)
        timestamp = datetime.now()
        
        # Validação mais robusta da resposta da API
        if not trends:
            logging.warning("API retornou resposta vazia para tendências.")
            return [{"name": "Não foi possível obter tendências", "volume": "N/A"}], timestamp
            
        if not isinstance(trends, list) or len(trends) == 0:
            logging.warning(f"API retornou resposta em formato inesperado: {type(trends)}")
            return [{"name": "Resposta da API em formato inesperado", "volume": "N/A"}], timestamp
            
        if not isinstance(trends[0], dict) or "trends" not in trends[0]:
            logging.warning(f"Formato de tendências inesperado: {trends}")
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
            logging.warning("Nenhuma tendência encontrada na resposta da API.")
            return [{"name": "Nenhuma tendência disponível", "volume": "N/A"}], timestamp
        
        trend_names = [t["name"] for t in trend_list]
        logging.info(f"Tendências atualizadas: {', '.join(trend_names)}")
        return trend_list, timestamp
            
    except tweepy.TweepyException as e:
        error_msg = str(e)
        logging.error(f"Erro ao buscar tendências: {error_msg}")
        
        # Trata diferentes tipos de erros da API
        if "rate limit" in error_msg.lower() or "429" in error_msg:
            return [{"name": "Limite de taxa excedido ao buscar tendências", "volume": "N/A"}], datetime.now()
        elif "authentication" in error_msg.lower() or "401" in error_msg:
            return [{"name": "Erro de autenticação ao buscar tendências", "volume": "N/A"}], datetime.now()
        else:
            return [{"name": f"Erro ao buscar tendências: {error_msg}", "volume": "N/A"}], datetime.now()
            
    except Exception as e:
        logging.error(f"Erro inesperado ao buscar tendências: {e}")
        return [{"name": "Erro inesperado ao buscar tendências", "volume": "N/A"}], datetime.now()

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
    
    if client is None:
        success, message = initialize_api()
        if not success:
            return False, message, None
        
    try:
        # Verifica se o texto está dentro do limite
        if len(text) > 280:
            return False, f"Texto excede o limite de 280 caracteres. Atual: {len(text)}", None
        
        # Publica o tweet
        response = client.create_tweet(text=text)
        
        # Verifica se a resposta é válida
        if not response or not hasattr(response, "data"):
            return False, "Resposta da API inválida ao tentar publicar tweet.", None
            
        # Extrai o ID do tweet
        tweet_id = response.data['id']
        
        logging.info(f"Tweet publicado com sucesso. ID: {tweet_id}")
        return True, f"Tweet publicado com sucesso. ID: {tweet_id}", {
            "id": tweet_id,
            "text": text,
            "posted_at": datetime.now().isoformat()
        }
        
    except tweepy.TweepyException as e:
        error_msg = str(e)
        logging.error(f"Erro ao publicar tweet: {error_msg}")
        
        # Trata erros específicos da API
        if "duplicate content" in error_msg.lower():
            return False, "Erro: Conteúdo duplicado. O X não permite postar o mesmo texto duas vezes seguidas.", None
        elif "authorization" in error_msg.lower() or "authentication" in error_msg.lower() or "401" in error_msg:
            return False, "Erro de autorização. Verifique suas credenciais da API.", None
        elif "rate limit" in error_msg.lower() or "429" in error_msg:
            return False, "Limite de taxa excedido. Aguarde alguns minutos e tente novamente.", None
        elif "text is too long" in error_msg.lower():
            return False, f"O texto excede o limite de caracteres permitido pelo X.", None
        else:
            return False, f"Erro ao publicar tweet: {error_msg}", None
            
    except Exception as e:
        logging.error(f"Erro inesperado ao publicar tweet: {e}")
        return False, f"Erro inesperado ao publicar tweet: {e}", None

@retry_with_backoff()
def get_user_info():
    """
    Obtém informações do usuário autenticado.
    
    Returns:
        tuple: (bool, dict) - Sucesso (True/False) e dicionário com informações do usuário.
    """
    global client
    
    if client is None:
        success, message = initialize_api()
        if not success:
            return False, {"error": message}
        
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
        error_msg = str(e)
        logging.error(f"Erro ao obter informações do usuário: {error_msg}")
        
        # Tratamento mais específico de erros
        if "authentication" in error_msg.lower() or "401" in error_msg:
            return False, {"error": "Erro de autenticação ao obter informações do usuário"}
        elif "rate limit" in error_msg.lower() or "429" in error_msg:
            return False, {"error": "Limite de taxa excedido ao obter informações do usuário"}
        else:
            return False, {"error": f"Erro ao obter informações do usuário: {error_msg}"}
            
    except Exception as e:
        logging.error(f"Erro inesperado ao obter informações do usuário: {e}")
        return False, {"error": f"Erro inesperado ao obter informações do usuário: {e}"}

def check_api_limits():
    """
    Verifica os limites atuais da API.
    
    Returns:
        dict: Dicionário com informações sobre os limites da API.
    """
    # Nota: A API v2 do Twitter ainda não oferece um endpoint fácil para 
    # verificar os limites restantes como a v1.1 fazia com get_rate_limit_status
    
    # Por enquanto, retornamos informações estáticas sobre os limites
    return {
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
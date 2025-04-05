"""
Arquivo de Configurações para Bot do X (Twitter)

Este arquivo contém todas as configurações necessárias para o funcionamento
do bot, como limites da API, intervalos de postagem, caminhos de arquivos,
e configurações gerais do sistema.

Recursos principais:
- Carregamento automático de variáveis de ambiente do arquivo .env
- Validação de configurações críticas
- Configurações para SQLite e APScheduler
- Valores padrão para execução segura

Autor: Uillen Machado (com melhorias)
Repositório: github.com/uillenmachado/botx
"""

import os
import logging
import re
import sys
import json
from pathlib import Path
from datetime import datetime

# ============================================================================
# Configuração de log
# ============================================================================
logger = logging.getLogger(__name__)

# ============================================================================
# Verificação e carregamento de dependências
# ============================================================================
DEPENDENCIES = {
    'python-dotenv': 'python-dotenv',
    'tweepy': 'tweepy',
    'apscheduler': 'APScheduler',
    'colorama': 'colorama',
}

# Verificar dependências críticas
missing_deps = []
for module, package in DEPENDENCIES.items():
    try:
        __import__(module)
    except ImportError:
        missing_deps.append(package)

if missing_deps:
    print("\nERRO: Dependências ausentes:")
    for dep in missing_deps:
        print(f" - {dep}")
    print("\nExecute o seguinte comando para instalar as dependências:")
    print(f"pip install {' '.join(missing_deps)}")
    print("\nOu execute 'python setup.py' para configuração automática.")
    sys.exit(1)

# Agora que sabemos que python-dotenv está instalado, podemos importá-lo
from dotenv import load_dotenv  # type: ignore

# ============================================================================
# Carregamento do arquivo .env
# ============================================================================
def load_env_file():
    """Carrega variáveis de ambiente do arquivo .env com tratamento de erros."""
    try:
        dotenv_path = Path('.env')
        if not dotenv_path.exists():
            logger.warning("Arquivo .env não encontrado. Usando variáveis de ambiente do sistema.")
            return False
        
        result = load_dotenv(override=True)
        if not result:
            logger.warning("Arquivo .env vazio ou mal formatado. Verifique seu conteúdo.")
        return result
    except Exception as e:
        logger.error(f"Erro ao carregar arquivo .env: {e}")
        logger.warning("Prosseguindo com variáveis de ambiente do sistema, se disponíveis.")
        return False

load_env_file()

# ============================================================================
# Diretórios e caminhos de arquivos
# ============================================================================
# Diretório base do projeto (onde o config.py está localizado)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Diretório de logs
LOG_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# Arquivo de log
LOG_FILE = os.path.join(LOG_DIR, 'bot_log.txt')

# Banco de dados SQLite (substitui o arquivo JSON)
DB_FILE = os.path.join(BASE_DIR, 'botx.db')

# Caminho para o arquivo de interface web
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')
STATIC_DIR = os.path.join(BASE_DIR, 'static')

# ============================================================================
# Credenciais da API do X (Twitter)
# ============================================================================
API_KEY = os.getenv("API_KEY", "")
API_KEY_SECRET = os.getenv("API_KEY_SECRET", "")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN", "")
ACCESS_TOKEN_SECRET = os.getenv("ACCESS_TOKEN_SECRET", "")
BEARER_TOKEN = os.getenv("BEARER_TOKEN", "")

# ============================================================================
# Configurações da Aplicação
# ============================================================================
# Servidor Web Flask
WEB_HOST = os.getenv("WEB_HOST", "127.0.0.1")
WEB_PORT = int(os.getenv("WEB_PORT", "5000"))
DEBUG_MODE = os.getenv("DEBUG_MODE", "False").lower() in ('true', '1', 't')

# SQLite
DB_TIMEOUT = 30  # Timeout para operações no banco de dados em segundos

# Scheduler
SCHEDULER_MISFIRE_GRACE_TIME = 60  # Tempo de tolerância para tarefas atrasadas (segundos)
SCHEDULER_COALESCE = True  # Combinar execuções perdidas
SCHEDULER_MAX_INSTANCES = 3  # Número máximo de instâncias para um mesmo job

# ============================================================================
# Configurações de Tendências
# ============================================================================
WOEID_GLOBAL = 1  # ID para tendências globais (1 = Global)
NUM_TRENDS = int(os.getenv("NUM_TRENDS", "5"))  # Número de tendências para buscar e exibir

# ============================================================================
# Limites da API
# ============================================================================
DAILY_POST_LIMIT = int(os.getenv("DAILY_POST_LIMIT", "16"))  # Máximo de posts por dia
MONTHLY_POST_LIMIT = int(os.getenv("MONTHLY_POST_LIMIT", "496"))  # Limite mensal (~500 é o limite real)
API_USER_LEVEL_LIMIT = int(os.getenv("API_USER_LEVEL_LIMIT", "1500"))  # Limite mensal da API (nível do usuário)

# ============================================================================
# Configurações de Horários e Intervalos
# ============================================================================
# Agora podemos usar qualquer horário do dia (00:00-23:59)
START_HOUR = os.getenv("START_HOUR", "00:00")
END_HOUR = os.getenv("END_HOUR", "23:59")
POST_INTERVAL_MINUTES = int(os.getenv("POST_INTERVAL_MINUTES", "60"))
TREND_UPDATE_HOUR = os.getenv("TREND_UPDATE_HOUR", "07:00")
STATS_UPDATE_INTERVAL = int(os.getenv("STATS_UPDATE_INTERVAL", "30"))  # Minutos entre atualizações de estatísticas

# Padrão para validação de horários (formato HH:MM, entre 00:00 e 23:59)
TIME_PATTERN = re.compile(r'^([01]\d|2[0-3]):([0-5]\d)$')

# ============================================================================
# Configurações de Timeout e Retry
# ============================================================================
APPROVE_TIMEOUT = int(os.getenv("APPROVE_TIMEOUT", "30"))  # Timeout para aprovação em segundos
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))  # Número máximo de tentativas para API
INITIAL_BACKOFF = int(os.getenv("INITIAL_BACKOFF", "5"))  # Tempo inicial entre tentativas (segundos)

# ============================================================================
# Configurações de Formatação
# ============================================================================
DATE_FORMAT = os.getenv("DATE_FORMAT", "%d/%m/%Y %H:%M")  # Formato de data para exibição
MAX_TWEET_LENGTH = int(os.getenv("MAX_TWEET_LENGTH", "280"))  # Limite de caracteres para um tweet

# ============================================================================
# Validação de Configurações
# ============================================================================
def validate_credentials():
    """
    Verifica se todas as credenciais necessárias estão presentes.
    
    Returns:
        tuple: (bool, list) - True se todas as credenciais estão presentes e
               lista vazia, ou False e lista de chaves ausentes.
    """
    required_keys = ["API_KEY", "API_KEY_SECRET", "ACCESS_TOKEN", 
                    "ACCESS_TOKEN_SECRET", "BEARER_TOKEN"]
    missing_keys = [key for key in required_keys if not os.getenv(key)]
    
    return (len(missing_keys) == 0, missing_keys)

def validate_time_format(time_str):
    """
    Verifica se uma string de tempo está no formato HH:MM.
    
    Args:
        time_str (str): String de tempo para validar
        
    Returns:
        bool: True se o formato é válido, False caso contrário.
    """
    if time_str.lower() == "now":
        return True
    return bool(TIME_PATTERN.match(time_str))

def validate_configs():
    """
    Valida as configurações importantes e retorna avisos/erros.
    
    Returns:
        list: Lista de mensagens de aviso/erro.
    """
    warnings = []
    
    # Validação de horários
    if not validate_time_format(START_HOUR):
        warnings.append(f"START_HOUR inválido: {START_HOUR}. Usando '00:00'.")
    
    if not validate_time_format(END_HOUR):
        warnings.append(f"END_HOUR inválido: {END_HOUR}. Usando '23:59'.")
    
    if TREND_UPDATE_HOUR and not validate_time_format(TREND_UPDATE_HOUR):
        warnings.append(f"TREND_UPDATE_HOUR inválido: {TREND_UPDATE_HOUR}. Definido para '07:00'.")
    
    # Validação de limites
    if DAILY_POST_LIMIT <= 0 or DAILY_POST_LIMIT > 50:
        warnings.append(f"DAILY_POST_LIMIT inválido: {DAILY_POST_LIMIT}. Deve estar entre 1 e 50.")
    
    if MONTHLY_POST_LIMIT <= 0 or MONTHLY_POST_LIMIT > 500:
        warnings.append(f"MONTHLY_POST_LIMIT inválido: {MONTHLY_POST_LIMIT}. Deve estar entre 1 e 500.")
    
    # Validação de porta web
    if WEB_PORT < 1024 or WEB_PORT > 65535:
        warnings.append(f"WEB_PORT inválido: {WEB_PORT}. Deve estar entre 1024 e 65535.")
    
    return warnings

# Executar validação de configurações
config_warnings = validate_configs()
for warning in config_warnings:
    logger.warning(warning)

# Verifica credenciais na importação do módulo
has_credentials, missing_credentials = validate_credentials()
if not has_credentials:
    logger.warning(f"Credenciais ausentes ou vazias: {', '.join(missing_credentials)}")
    logger.warning("O bot pode não funcionar corretamente sem as credenciais adequadas.")

# ============================================================================
# Configurações para interface de cores (CLI)
# ============================================================================
# Cores para CLI (usando colorama)
COLOR_INFO = "cyan"        # Para informações gerais
COLOR_SUCCESS = "green"    # Para operações bem-sucedidas
COLOR_WARNING = "yellow"   # Para avisos
COLOR_ERROR = "red"        # Para erros
COLOR_HEADER = "magenta"   # Para cabeçalhos
COLOR_NORMAL = "white"     # Cor padrão

# ============================================================================
# Informações da versão
# ============================================================================
VERSION = "2.0.0"
UPDATED_AT = "Abril 2025"
#!/usr/bin/env python3
"""
Script de configuração para o BotX

Este script interativo guia o usuário pelo processo de instalação e configuração 
do BotX, automatizando tarefas como:
- Instalação de dependências
- Criação e configuração do arquivo .env
- Inicialização do banco de dados SQLite
- Verificação de credenciais da API do Twitter/X

Uso:
    python setup.py

Autor: Uillen Machado (com melhorias)
Repositório: github.com/uillenmachado/botx
"""

import os
import sys
import subprocess
import platform
import sqlite3
import getpass
import re
import time
import json
from pathlib import Path
from datetime import datetime

# Determina o diretório base (onde o setup.py está localizado)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Variáveis de configuração
REQUIREMENTS_FILE = os.path.join(BASE_DIR, "requirements.txt")
ENV_FILE = os.path.join(BASE_DIR, ".env")
DB_FILE = os.path.join(BASE_DIR, "botx.db")
LOG_DIR = os.path.join(BASE_DIR, "logs")
VERSION = "2.0.0"

# Lista de dependências principais
DEPENDENCIES = [
    "tweepy",          # API do Twitter/X
    "flask",           # Servidor web
    "python-dotenv",   # Carregamento de variáveis de ambiente
    "apscheduler",     # Agendamento de tarefas
    "colorama",        # Cores no terminal
]

# Cores para o terminal (compatível com Windows)
try:
    from colorama import init, Fore, Style # type: ignore
    init()  # Inicializa o colorama (necessário no Windows)
    
    # Define cores
    COLOR_INFO = Fore.CYAN
    COLOR_SUCCESS = Fore.GREEN
    COLOR_WARNING = Fore.YELLOW
    COLOR_ERROR = Fore.RED
    COLOR_HEADER = Fore.MAGENTA
    COLOR_RESET = Style.RESET_ALL
    
except ImportError:
    # Fallback se colorama não estiver disponível
    COLOR_INFO = ""
    COLOR_SUCCESS = ""
    COLOR_WARNING = ""
    COLOR_ERROR = ""
    COLOR_HEADER = ""
    COLOR_RESET = ""

# ==============================================================================
# Funções utilitárias
# ==============================================================================

def print_header(text):
    """Imprime um cabeçalho formatado."""
    width = 70
    print("\n" + COLOR_HEADER + "=" * width + COLOR_RESET)
    print(COLOR_HEADER + text.center(width) + COLOR_RESET)
    print(COLOR_HEADER + "=" * width + COLOR_RESET + "\n")

def print_info(text):
    """Imprime uma mensagem informativa."""
    print(COLOR_INFO + f"[INFO] {text}" + COLOR_RESET)

def print_success(text):
    """Imprime uma mensagem de sucesso."""
    print(COLOR_SUCCESS + f"[SUCESSO] {text}" + COLOR_RESET)

def print_warning(text):
    """Imprime uma mensagem de aviso."""
    print(COLOR_WARNING + f"[AVISO] {text}" + COLOR_RESET)

def print_error(text):
    """Imprime uma mensagem de erro."""
    print(COLOR_ERROR + f"[ERRO] {text}" + COLOR_RESET)

def clear_screen():
    """Limpa a tela do terminal."""
    os.system('cls' if os.name == 'nt' else 'clear')

def yes_no_prompt(question, default="sim"):
    """
    Apresenta uma pergunta sim/não ao usuário.
    
    Args:
        question (str): A pergunta a ser feita
        default (str): Resposta padrão se o usuário apenas pressionar Enter
        
    Returns:
        bool: True para sim, False para não
    """
    valid = {"sim": True, "s": True, "yes": True, "y": True,
             "não": False, "nao": False, "n": False, "no": False}
    
    if default.lower() in ["sim", "s", "yes", "y"]:
        prompt = " [S/n] "
    elif default.lower() in ["não", "nao", "n", "no"]:
        prompt = " [s/N] "
    else:
        prompt = " [s/n] "
    
    while True:
        sys.stdout.write(COLOR_INFO + question + prompt + COLOR_RESET)
        choice = input().lower()
        
        if choice == '':
            return valid[default.lower()]
        elif choice in valid:
            return valid[choice]
        else:
            print_warning("Por favor, responda com 'sim' ou 'não' (ou 's' ou 'n').")

def input_with_validation(prompt, validation_func=None, error_msg=None, default=None):
    """
    Solicita entrada do usuário com validação.
    
    Args:
        prompt (str): O prompt a ser exibido
        validation_func (callable, optional): Função para validar a entrada
        error_msg (str, optional): Mensagem de erro para entrada inválida
        default (str, optional): Valor padrão se o usuário pressionar Enter
        
    Returns:
        str: A entrada validada do usuário
    """
    prompt_text = f"{prompt}"
    if default:
        prompt_text += f" [{default}]"
    prompt_text += ": "
    
    while True:
        user_input = input(COLOR_INFO + prompt_text + COLOR_RESET)
        
        # Usa o valor padrão se fornecido e o usuário não digitou nada
        if not user_input and default is not None:
            return default
        
        # Aplica validação se fornecida
        if validation_func and not validation_func(user_input):
            print_error(error_msg or "Entrada inválida. Tente novamente.")
            continue
        
        # Se chegou aqui, a entrada é válida
        return user_input

def validate_time_format(time_str):
    """
    Valida se uma string está no formato HH:MM.
    
    Args:
        time_str (str): A string a ser validada
        
    Returns:
        bool: True se válido, False caso contrário
    """
    if time_str.lower() == "now":
        return True
    return bool(re.match(r'^([01]\d|2[0-3]):([0-5]\d)$', time_str))

# ==============================================================================
# Funções de instalação
# ==============================================================================

def check_python_version():
    """
    Verifica se a versão do Python é compatível.
    
    Returns:
        bool: True se compatível, False caso contrário
    """
    required_version = (3, 7)
    current_version = sys.version_info
    
    if current_version < required_version:
        print_error(f"Python {required_version[0]}.{required_version[1]} ou superior é necessário.")
        print_info(f"Sua versão atual é {current_version[0]}.{current_version[1]}.{current_version[2]}")
        return False
    
    print_success(f"Versão do Python compatível: {current_version[0]}.{current_version[1]}.{current_version[2]}")
    return True

def create_requirements_file():
    """
    Cria ou atualiza o arquivo requirements.txt com as dependências necessárias.
    
    Returns:
        bool: True se o arquivo foi criado/atualizado com sucesso, False caso contrário
    """
    try:
        with open(REQUIREMENTS_FILE, "w") as f:
            for dep in DEPENDENCIES:
                f.write(f"{dep}\n")
        print_success(f"Arquivo requirements.txt criado em {REQUIREMENTS_FILE}")
        return True
    except Exception as e:
        print_error(f"Erro ao criar arquivo requirements.txt: {e}")
        return False

def install_dependencies():
    """
    Instala as dependências necessárias usando pip.
    
    Returns:
        bool: True se todas as dependências foram instaladas com sucesso, False caso contrário
    """
    print_header("Instalando Dependências")
    
    try:
        # Verifica se pip está instalado
        subprocess.run([sys.executable, "-m", "pip", "--version"], 
                      check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError:
        print_error("pip não está instalado ou não funciona corretamente.")
        print_info("Por favor, instale pip e tente novamente.")
        return False
    
    # Atualiza o pip
    print_info("Atualizando pip...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], 
                      check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print_success("pip atualizado com sucesso.")
    except subprocess.CalledProcessError as e:
        print_warning(f"Não foi possível atualizar o pip: {e}")
        print_info("Continuando mesmo assim...")
    
    # Cria o arquivo requirements.txt
    if not create_requirements_file():
        return False
    
    # Instala as dependências
    print_info("Instalando dependências do requirements.txt...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", REQUIREMENTS_FILE], 
                      check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print_success("Dependências instaladas com sucesso.")
        
        # Importa colorama agora que está instalado (se não foi importado antes)
        if not COLOR_INFO:
            global COLOR_INFO, COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR, COLOR_HEADER, COLOR_RESET
            try:
                from colorama import init, Fore, Style # type: ignore
                init()
                COLOR_INFO = Fore.CYAN
                COLOR_SUCCESS = Fore.GREEN
                COLOR_WARNING = Fore.YELLOW
                COLOR_ERROR = Fore.RED
                COLOR_HEADER = Fore.MAGENTA
                COLOR_RESET = Style.RESET_ALL
                clear_screen()  # Limpa a tela para começar a usar as cores
            except ImportError:
                pass  # Se ainda não conseguir importar, continuamos sem cores
        
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Erro ao instalar dependências: {e}")
        print_info("Tente executar manualmente: pip install -r requirements.txt")
        return False

def setup_directory_structure():
    """
    Cria a estrutura de diretórios necessária para o BotX.
    
    Returns:
        bool: True se os diretórios foram criados com sucesso, False caso contrário
    """
    print_header("Configurando Estrutura de Diretórios")
    
    directories = [
        LOG_DIR,  # Diretório de logs
        os.path.join(BASE_DIR, "templates"),  # Diretório de templates para o Flask
        os.path.join(BASE_DIR, "static"),  # Diretório de arquivos estáticos para o Flask
    ]
    
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            print_success(f"Diretório criado: {directory}")
        except Exception as e:
            print_error(f"Erro ao criar diretório {directory}: {e}")
            return False
    
    return True

def create_database():
    """
    Cria e inicializa o banco de dados SQLite.
    
    Returns:
        bool: True se o banco de dados foi criado com sucesso, False caso contrário
    """
    print_header("Configurando Banco de Dados SQLite")
    
    # Verifica se o banco de dados já existe
    if os.path.exists(DB_FILE):
        if yes_no_prompt(f"Banco de dados já existe em {DB_FILE}. Deseja recriá-lo?", "não"):
            try:
                os.remove(DB_FILE)
                print_info("Banco de dados existente removido.")
            except Exception as e:
                print_error(f"Erro ao remover banco de dados existente: {e}")
                return False
        else:
            print_info("Mantendo banco de dados existente.")
            return True
    
    try:
        # Conecta ao banco de dados (será criado se não existir)
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Cria tabelas
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
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS trends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            volume INTEGER,
            timestamp TEXT NOT NULL
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            daily_posts INTEGER DEFAULT 0,
            monthly_posts INTEGER DEFAULT 0,
            timestamp TEXT NOT NULL
        )
        ''')
        
        # Commit e fechamento da conexão
        conn.commit()
        conn.close()
        
        print_success("Banco de dados criado e inicializado com sucesso.")
        return True
    except Exception as e:
        print_error(f"Erro ao criar banco de dados: {e}")
        return False

def configure_env_file():
    """
    Cria ou atualiza o arquivo .env com as configurações do usuário.
    
    Returns:
        bool: True se o arquivo foi criado/atualizado com sucesso, False caso contrário
    """
    print_header("Configurando Arquivo .env")
    
    # Verificar se o arquivo .env já existe
    env_exists = os.path.exists(ENV_FILE)
    current_env = {}
    
    if env_exists:
        try:
            # Lê o arquivo .env existente
            with open(ENV_FILE, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        current_env[key.strip()] = value.strip().strip('"\'')
            
            if yes_no_prompt(f"Arquivo .env já existe. Deseja modificá-lo?", "sim"):
                print_info("Atualizando arquivo .env existente...")
            else:
                print_info("Mantendo arquivo .env existente.")
                return True
        except Exception as e:
            print_error(f"Erro ao ler arquivo .env existente: {e}")
            if not yes_no_prompt("Deseja criar um novo arquivo .env?", "sim"):
                return False
            current_env = {}
    
    # Configurações da API do Twitter/X
    print_info("\n--- Configuração da API do Twitter/X ---")
    print_info("Você precisa ter uma conta de desenvolvedor do Twitter/X para usar este bot.")
    print_info("Se você ainda não tem as credenciais, visite: https://developer.twitter.com/")
    
    api_key = input_with_validation(
        "API Key",
        default=current_env.get("API_KEY", "")
    )
    
    api_key_secret = input_with_validation(
        "API Key Secret",
        default=current_env.get("API_KEY_SECRET", "")
    )
    
    access_token = input_with_validation(
        "Access Token",
        default=current_env.get("ACCESS_TOKEN", "")
    )
    
    access_token_secret = input_with_validation(
        "Access Token Secret",
        default=current_env.get("ACCESS_TOKEN_SECRET", "")
    )
    
    bearer_token = input_with_validation(
        "Bearer Token",
        default=current_env.get("BEARER_TOKEN", "")
    )
    
    # Configurações do bot
    print_info("\n--- Configurações do Bot ---")
    
    daily_limit = input_with_validation(
        "Limite diário de posts (recomendado: 16)",
        lambda x: x.isdigit() and 1 <= int(x) <= 50,
        "O valor deve ser um número entre 1 e 50.",
        current_env.get("DAILY_POST_LIMIT", "16")
    )
    
    monthly_limit = input_with_validation(
        "Limite mensal de posts (recomendado: 496)",
        lambda x: x.isdigit() and 1 <= int(x) <= 500,
        "O valor deve ser um número entre 1 e 500.",
        current_env.get("MONTHLY_POST_LIMIT", "496")
    )
    
    trend_update_hour = input_with_validation(
        "Horário para atualização diária das tendências (formato HH:MM)",
        validate_time_format,
        "Formato inválido. Use HH:MM (ex: 07:00).",
        current_env.get("TREND_UPDATE_HOUR", "07:00")
    )
    
    # Configurações do servidor web
    print_info("\n--- Configurações do Servidor Web ---")
    
    web_host = input_with_validation(
        "Host para o servidor web (recomendado: 127.0.0.1 para local)",
        lambda x: re.match(r'^[\w\-\.]+$', x) or re.match(r'^(\d{1,3}\.){3}\d{1,3}$', x),
        "Formato de host inválido.",
        current_env.get("WEB_HOST", "127.0.0.1")
    )
    
    web_port = input_with_validation(
        "Porta para o servidor web (recomendado: 5000)",
        lambda x: x.isdigit() and 1024 <= int(x) <= 65535,
        "A porta deve ser um número entre 1024 e 65535.",
        current_env.get("WEB_PORT", "5000")
    )
    
    debug_mode = yes_no_prompt(
        "Ativar modo de debug?",
        "sim" if current_env.get("DEBUG_MODE", "False").lower() in ("true", "1", "t") else "não"
    )
    
    # Escreve o arquivo .env
    try:
        with open(ENV_FILE, "w") as f:
            f.write("# Arquivo de configuração para o BotX\n")
            f.write(f"# Gerado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("# Credenciais da API do Twitter/X\n")
            f.write(f"API_KEY={api_key}\n")
            f.write(f"API_KEY_SECRET={api_key_secret}\n")
            f.write(f"ACCESS_TOKEN={access_token}\n")
            f.write(f"ACCESS_TOKEN_SECRET={access_token_secret}\n")
            f.write(f"BEARER_TOKEN={bearer_token}\n\n")
            
            f.write("# Configurações do Bot\n")
            f.write(f"DAILY_POST_LIMIT={daily_limit}\n")
            f.write(f"MONTHLY_POST_LIMIT={monthly_limit}\n")
            f.write(f"TREND_UPDATE_HOUR={trend_update_hour}\n\n")
            
            f.write("# Configurações do Servidor Web\n")
            f.write(f"WEB_HOST={web_host}\n")
            f.write(f"WEB_PORT={web_port}\n")
            f.write(f"DEBUG_MODE={'True' if debug_mode else 'False'}\n")
        
        print_success(f"Arquivo .env criado/atualizado em {ENV_FILE}")
        return True
    except Exception as e:
        print_error(f"Erro ao criar/atualizar arquivo .env: {e}")
        return False

# ==============================================================================
# Função principal
# ==============================================================================

def main():
    """Função principal que executa o script de configuração."""
    clear_screen()
    
    print_header(f"BotX - Assistente de Configuração v{VERSION}")
    print_info("Bem-vindo ao assistente de configuração do BotX!")
    print_info("Este script vai configurar o ambiente para executar o bot do Twitter/X.")
    print()
    
    # Verifica versão do Python
    if not check_python_version():
        if not yes_no_prompt("Deseja continuar mesmo assim?", "não"):
            print_info("Configuração cancelada.")
            return
    
    # Instala dependências
    if not install_dependencies():
        if not yes_no_prompt("Deseja continuar mesmo com erros na instalação?", "não"):
            print_info("Configuração cancelada.")
            return
    
    # Configura estrutura de diretórios
    if not setup_directory_structure():
        if not yes_no_prompt("Deseja continuar mesmo com erros na criação de diretórios?", "não"):
            print_info("Configuração cancelada.")
            return
    
    # Cria banco de dados
    if not create_database():
        if not yes_no_prompt("Deseja continuar mesmo com erros na criação do banco de dados?", "não"):
            print_info("Configuração cancelada.")
            return
    
    # Configura arquivo .env
    if not configure_env_file():
        if not yes_no_prompt("Deseja continuar mesmo com erros na configuração do arquivo .env?", "não"):
            print_info("Configuração cancelada.")
            return
    
    # Resumo da configuração
    print_header("Configuração Concluída")
    print_success("A configuração do BotX foi concluída com sucesso!")
    print_info("Você pode iniciar o bot usando o comando:")
    print(COLOR_INFO + "    python bot.py" + COLOR_RESET)
    print_info("Ou iniciar a interface web usando o comando:")
    print(COLOR_INFO + "    python server.py" + COLOR_RESET)
    print()
    print_info("Para obter ajuda, digite:")
    print(COLOR_INFO + "    python bot.py --help" + COLOR_RESET)
    print()
    
    # Verifica se o usuário deseja iniciar o bot agora
    if yes_no_prompt("Deseja iniciar o bot agora?", "sim"):
        print_info("Iniciando o bot...")
        try:
            subprocess.Popen([sys.executable, "bot.py"])
        except Exception as e:
            print_error(f"Erro ao iniciar o bot: {e}")
    else:
        print_info("Você pode iniciar o bot manualmente mais tarde.")
    
    print()
    print_info("Obrigado por usar o BotX!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n" + COLOR_WARNING + "Configuração interrompida pelo usuário." + COLOR_RESET)
    except Exception as e:
        print("\n\n" + COLOR_ERROR + f"Erro inesperado: {e}" + COLOR_RESET)
        import traceback
        traceback.print_exc()
    finally:
        # Espera um pouco antes de sair para o usuário ler as mensagens
        try:
            if sys.platform.startswith('win'):
                print("\nPressione qualquer tecla para sair...")
                import msvcrt
                msvcrt.getch()
            else:
                # No Unix, apenas pergunta se o usuário quer sair
                print("\nPressione Enter para sair...")
                input()
        except:
            pass
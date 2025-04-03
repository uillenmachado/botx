"""
Bot para X (Twitter) - Interface interativa e lógica principal

Este módulo implementa o dashboard interativo no terminal e a lógica principal
do bot, incluindo o agendamento de posts e o loop de execução.

Autor: Uillen Machado
Repositório: github.com/uillenmachado/botx
"""

import logging
import time
import os
import sys
import schedule
import threading
import select  # Adicionado import do módulo select
from datetime import datetime, timedelta, date
import calendar

from config import (
    START_HOUR, END_HOUR, POST_INTERVAL_MINUTES, LOG_FILE,
    APPROVE_TIMEOUT, DAILY_POST_LIMIT, MONTHLY_POST_LIMIT,
    TREND_UPDATE_HOUR, DATE_FORMAT, TREND_UPDATE_HOUR, WOEID_GLOBAL
)
from post_manager import (
    load_posts, save_posts, get_post_list, create_post, edit_post, delete_post,
    approve_post, schedule_post, mark_as_posted, get_scheduled_posts_for_recovery,
    get_stats, validate_time
)
from twitter_api import (
    initialize_api, get_trends, post_tweet, get_user_info
)

# Configuração do logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename=LOG_FILE,
    filemode='a'
)

# Adicionar manipulador para exibir logs no console também
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)

# Variáveis globais
trends = []
trends_last_updated = None
monthly_posts = 0
daily_posts = 0
bot_running = True
scheduler_thread = None
scheduled_jobs = {}  # Dicionário para armazenar referências aos jobs agendados

# Função para limpar a tela
def clear_screen():
    """Limpa a tela do terminal para melhor visualização."""
    os.system('cls' if os.name == 'nt' else 'clear')

def format_trend_list():
    """
    Formata a lista de tendências para exibição.
    
    Returns:
        list: Lista de strings formatadas com as tendências.
    """
    global trends, trends_last_updated
    
    result = []
    
    if not trends:
        result.append("Nenhuma tendência disponível. Use a opção 'Atualizar tendências' para buscar.")
        return result
    
    result.append(f"Tendências globais (atualizado em: {trends_last_updated.strftime(DATE_FORMAT) if trends_last_updated else 'N/A'}):")
    
    for i, trend in enumerate(trends, 1):
        volume = trend.get("volume", "N/A")
        volume_str = f"{volume:,}".replace(',', '.') if isinstance(volume, int) else "N/A"
        result.append(f"{i}. {trend.get('name', 'N/A')} | Volume: {volume_str}")
    
    return result

def update_trends():
    """
    Atualiza as tendências globais.
    
    Returns:
        bool: True se as tendências foram atualizadas com sucesso.
    """
    global trends, trends_last_updated
    
    logging.info("Atualizando tendências globais...")
    try:
        trends_data, timestamp = get_trends()
        
        if trends_data and len(trends_data) > 0 and "error" not in trends_data[0].get("name", "").lower():
            trends = trends_data
            trends_last_updated = timestamp
            logging.info(f"Tendências atualizadas: {', '.join([t['name'] for t in trends])}")
            return True
        else:
            logging.error(f"Falha ao atualizar tendências: {trends_data[0]['name']}")
            return False
    except Exception as e:
        logging.error(f"Erro ao atualizar tendências: {e}")
        return False

def load_post_counts():
    """
    Carrega as contagens de posts diários e mensais a partir do arquivo de posts.
    
    Returns:
        tuple: (int, int) - Contagem mensal e diária de posts.
    """
    posts_data = load_posts()
    today = datetime.now().date()
    current_month = today.replace(day=1)
    
    monthly_count = 0
    daily_count = 0
    
    for post in posts_data["history"]:
        if "posted_at" in post:
            posted_date = datetime.fromisoformat(post["posted_at"]).date()
            # Conta mensal
            if posted_date.replace(day=1) == current_month:
                monthly_count += 1
            # Conta diária
            if posted_date == today:
                daily_count += 1
    
    logging.info(f"Contagens carregadas: {monthly_count} posts neste mês, {daily_count} posts hoje")
    return monthly_count, daily_count

def can_post_today():
    """
    Verifica se é possível postar hoje, considerando os limites diários.
    
    Returns:
        bool: True se é possível postar hoje.
    """
    global daily_posts
    
    if daily_posts >= DAILY_POST_LIMIT:
        logging.warning(f"Limite diário de {DAILY_POST_LIMIT} posts atingido")
        return False
    return True

def can_post_this_month():
    """
    Verifica se é possível postar este mês, considerando os limites mensais.
    
    Returns:
        bool: True se é possível postar este mês.
    """
    global monthly_posts
    
    if monthly_posts >= MONTHLY_POST_LIMIT:
        logging.warning(f"Limite mensal de {MONTHLY_POST_LIMIT} posts atingido")
        return False
    return True

def reset_daily_count():
    """Reseta o contador diário de posts à meia-noite."""
    global daily_posts
    daily_posts = 0
    logging.info("Contador diário de posts resetado")

def reset_monthly_count():
    """Reseta o contador mensal de posts no primeiro dia do mês."""
    global monthly_posts
    monthly_posts = 0
    logging.info("Contador mensal de posts resetado")

def post_scheduled_tweet(post):
    """
    Publica um tweet agendado.
    
    Args:
        post (dict): Informações do post a ser publicado.
    
    Returns:
        bool: True se o post foi publicado com sucesso.
    """
    global monthly_posts, daily_posts
    
    if not can_post_today() or not can_post_this_month():
        logging.warning(f"Post '{post['text'][:30]}...' não publicado devido aos limites da API")
        return False
    
    logging.info(f"Publicando post agendado: '{post['text'][:50]}...'")
    
    try:
        success, message, tweet_data = post_tweet(post["text"])
        
        if success:
            # Atualiza contadores
            monthly_posts += 1
            daily_posts += 1
            
            # Marca como publicado
            mark_as_posted(post)
            
            logging.info(f"Post publicado com sucesso: {message}")
            return True
        else:
            logging.error(f"Falha ao publicar post: {message}")
            return False
    except Exception as e:
        logging.error(f"Erro ao publicar post agendado: {e}")
        return False

def schedule_post_at_time(post):
    """
    Agenda um post para um horário específico.
    
    Args:
        post (dict): Informações do post a ser agendado.
    
    Returns:
        bool: True se o agendamento foi bem-sucedido.
    """
    global scheduled_jobs
    
    if post["time"] == "now":
        return False
    
    try:
        # Extrai o horário
        time_parts = post["time"].split(":")
        hour = int(time_parts[0])
        minute = int(time_parts[1])
        
        # Verifica se o horário já passou hoje
        now = datetime.now()
        schedule_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        if schedule_time < now:
            logging.info(f"Horário {post['time']} já passou hoje, agendando para amanhã")
        
        # Define o horário no schedule
        job = schedule.every().day.at(post["time"]).do(post_scheduled_tweet, post)
        
        # Armazena referência ao job usando o ID do post
        if "id" in post:
            scheduled_jobs[post["id"]] = job
        
        logging.info(f"Post agendado para {post['time']}: '{post['text'][:50]}...'")
        return True
    except Exception as e:
        logging.error(f"Erro ao agendar post: {e}")
        return False

def create_new_post():
    """Interface para criar uma nova postagem."""
    clear_screen()
    print("\n===== CRIAR NOVA POSTAGEM =====\n")
    
    # Exibe tendências para inspiração
    print("\nTendências atuais para inspiração:")
    for line in format_trend_list():
        print(line)
    
    print("\nDigite o texto da sua postagem:")
    text = input("> ")
    
    if not text.strip():
        print("Texto vazio! A postagem não foi criada.")
        input("\nPressione ENTER para continuar...")
        return
    
    print("\nDigite o horário para a postagem (HH:MM) ou 'now' para postar assim que aprovado:")
    time_str = input("> ")
    
    if not time_str:
        time_str = "now"
    
    success, message = create_post(text, time_str)
    
    if success:
        print(f"\nSucesso! {message}")
    else:
        print(f"\nErro! {message}")
    
    input("\nPressione ENTER para continuar...")

def list_posts():
    """Interface para listar postagens por status."""
    while True:
        clear_screen()
        print("\n===== LISTAR POSTAGENS =====\n")
        print("1. Pendentes")
        print("2. Aprovadas")
        print("3. Agendadas")
        print("4. Histórico de publicações")
        print("5. Todas")
        print("0. Voltar")
        
        choice = input("\nEscolha uma opção: ")
        
        if choice == "0":
            break
        
        status_map = {
            "1": "pending",
            "2": "approved",
            "3": "scheduled",
            "4": "history",
            "5": "all"
        }
        
        if choice in status_map:
            status = status_map[choice]
            post_list = get_post_list(status)
            
            clear_screen()
            print(f"\n===== POSTAGENS {status.upper()} =====\n")
            
            if not post_list:
                print("Nenhuma postagem encontrada.")
            else:
                for post in post_list:
                    print(post)
                
                # Opções para gerenciar posts pendentes e aprovados
                if choice in ["1", "2", "3"]:
                    print("\nOpções:")
                    print("E - Editar uma postagem")
                    print("D - Deletar uma postagem")
                    print("V - Voltar")
                    
                    action = input("\nEscolha uma ação: ").upper()
                    
                    if action == "E":
                        edit_existing_post(status)
                    elif action == "D":
                        delete_existing_post(status)
            
            input("\nPressione ENTER para continuar...")
        else:
            print("Opção inválida!")
            time.sleep(1)

def edit_existing_post(status):
    """
    Interface para editar uma postagem existente.
    
    Args:
        status (str): Status da postagem a ser editada.
    """
    try:
        post_index = int(input("\nDigite o número da postagem para editar: ")) - 1
        
        if post_index < 0:
            print("Número inválido!")
            return
        
        print("\nDigite o novo texto (deixe em branco para manter o atual):")
        new_text = input("> ")
        
        print("\nDigite o novo horário (deixe em branco para manter o atual):")
        new_time = input("> ")
        
        success, message = edit_post(
            post_index,
            new_text=new_text if new_text.strip() else None,
            new_time=new_time if new_time.strip() else None,
            status=status
        )
        
        if success:
            print(f"\nSucesso! {message}")
        else:
            print(f"\nErro! {message}")
    except ValueError:
        print("Entrada inválida! Digite apenas números.")
    except Exception as e:
        print(f"Erro ao editar postagem: {e}")

def delete_existing_post(status):
    """
    Interface para deletar uma postagem existente.
    
    Args:
        status (str): Status da postagem a ser deletada.
    """
    try:
        post_index = int(input("\nDigite o número da postagem para deletar: ")) - 1
        
        if post_index < 0:
            print("Número inválido!")
            return
        
        confirm = input(f"Tem certeza que deseja deletar a postagem #{post_index+1}? (S/N): ").upper()
        
        if confirm == "S":
            success, message = delete_post(post_index, status=status)
            
            if success:
                print(f"\nSucesso! {message}")
            else:
                print(f"\nErro! {message}")
        else:
            print("Operação cancelada.")
    except ValueError:
        print("Entrada inválida! Digite apenas números.")
    except Exception as e:
        print(f"Erro ao deletar postagem: {e}")

def approve_posts():
    """Interface para aprovar postagens pendentes."""
    clear_screen()
    print("\n===== APROVAR POSTAGENS =====\n")
    
    # Carrega a lista de postagens pendentes
    post_list = get_post_list("pending")
    
    if not post_list:
        print("Não há postagens pendentes para aprovação.")
        input("\nPressione ENTER para continuar...")
        return
    
    timeout_count = 0
    max_consecutive_timeouts = 3  # Número máximo de timeouts consecutivos permitidos
    
    for i, post_str in enumerate(post_list):
        print(f"\n{post_str}")
        
        print("\nOpções:")
        print("A - Aprovar")
        print("R - Rejeitar")
        print("S - Pular")
        print("E - Editar antes de aprovar")
        print("C - Cancelar aprovações")
        
        # Timeout para aprovação
        print(f"\nAguardando resposta... (timeout em {APPROVE_TIMEOUT} segundos)")
        
        start_time = time.time()
        action = None
        
        while time.time() - start_time < APPROVE_TIMEOUT and action is None:
            if sys.stdin in select.select([sys.stdin], [], [], 0.1)[0]:
                action = input().upper()
        
        if action is None:
            print("Timeout! Pulando para a próxima postagem.")
            timeout_count += 1
            
            # Sai do loop após muitos timeouts consecutivos
            if timeout_count >= max_consecutive_timeouts:
                print(f"\nMuitos timeouts consecutivos ({max_consecutive_timeouts}). Encerrando processo de aprovação.")
                break
                
            continue
        else:
            # Reseta o contador de timeout se o usuário responder
            timeout_count = 0
        
        if action == "A":
            # Aprovar
            new_time = None
            time_change = input("Deseja alterar o horário? (S/N): ").upper()
            
            if time_change == "S":
                new_time = input("Digite o novo horário (HH:MM ou 'now'): ")
            
            success, message, post = approve_post(i, True, new_time)
            
            if success:
                print(f"Sucesso! {message}")
                
                # Perguntar se deseja postar agora ou agendar
                if post["time"] != "now":
                    post_now = input("Deseja postar agora em vez de agendar? (S/N): ").upper()
                    
                    if post_now == "S":
                        # Postar imediatamente
                        if can_post_today() and can_post_this_month():
                            success, message, _ = post_tweet(post["text"])
                            
                            if success:
                                print(f"Post publicado! {message}")
                                monthly_posts += 1
                                daily_posts += 1
                                
                                # Remove da lista de aprovados e adiciona ao histórico
                                posts_data = load_posts()
                                post_index = next((i for i, p in enumerate(posts_data["approved"]) 
                                                 if p.get("id") == post.get("id")), None)
                                
                                if post_index is not None:
                                    posts_data["approved"].pop(post_index)
                                    post["posted_at"] = datetime.now().isoformat()
                                    post["status"] = "posted"
                                    posts_data["history"].append(post)
                                    save_posts(posts_data)
                            else:
                                print(f"Erro ao publicar! {message}")
                        else:
                            print("Não é possível postar devido aos limites da API!")
                else:
                    print("Post aprovado para publicação imediata após aprovação.")
            else:
                print(f"Erro! {message}")
        
        elif action == "R":
            # Rejeitar
            success, message, _ = approve_post(i, False)
            
            if success:
                print(f"Sucesso! {message}")
            else:
                print(f"Erro! {message}")
        
        elif action == "E":
            # Editar
            print("\nDigite o novo texto (deixe em branco para manter o atual):")
            new_text = input("> ")
            
            print("\nDigite o novo horário (deixe em branco para manter o atual):")
            new_time = input("> ")
            
            success, message = edit_post(
                i,
                new_text=new_text if new_text.strip() else None,
                new_time=new_time if new_time.strip() else None,
                status="pending"
            )
            
            if success:
                print(f"Sucesso! {message}")
                # Perguntar se deseja aprovar após edição
                approve_after_edit = input("Deseja aprovar esta postagem agora? (S/N): ").upper()
                
                if approve_after_edit == "S":
                    success, message, _ = approve_post(i, True)
                    
                    if success:
                        print(f"Sucesso! {message}")
                    else:
                        print(f"Erro! {message}")
            else:
                print(f"Erro! {message}")
        
        elif action == "C":
            # Cancelar o processo de aprovação
            print("Processo de aprovação cancelado.")
            break
        
        # Pausa antes da próxima postagem
        input("\nPressione ENTER para continuar...")
    
    print("\nProcesso de aprovação concluído.")
    input("\nPressione ENTER para voltar ao menu principal...")

def schedule_approved_posts():
    """Interface para agendar postagens aprovadas."""
    clear_screen()
    print("\n===== AGENDAR POSTAGENS =====\n")
    
    # Carrega a lista de postagens aprovadas
    posts_data = load_posts()
    approved_posts = get_post_list("approved")
    
    if not approved_posts:
        print("Não há postagens aprovadas para agendar.")
        input("\nPressione ENTER para continuar...")
        return
    
    for i, post_str in enumerate(approved_posts):
        post = posts_data["approved"][i]
        
        # Pula posts com horário "now" pois eles serão postados imediatamente
        if post["time"] == "now":
            continue
        
        print(f"\n{post_str}")
        
        print("\nOpções:")
        print("A - Agendar para o horário definido")
        print("P - Postar agora")
        print("S - Pular")
        print("C - Cancelar agendamentos")
        
        action = input("\nEscolha uma opção: ").upper()
        
        if action == "A":
            # Agendar
            success, message, scheduled_post = schedule_post(i, True)
            
            if success:
                print(f"Sucesso! {message}")
                
                # Agenda o post utilizando o scheduler
                schedule_post_at_time(scheduled_post)
            else:
                print(f"Erro! {message}")
        
        elif action == "P":
            # Postar agora
            if can_post_today() and can_post_this_month():
                success, message, _ = post_tweet(post["text"])
                
                if success:
                    print(f"Post publicado! {message}")
                    monthly_posts += 1
                    daily_posts += 1
                    
                    # Remove da lista de aprovados e adiciona ao histórico
                    post["posted_at"] = datetime.now().isoformat()
                    post["status"] = "posted"
                    posts_data["history"].append(post)
                    posts_data["approved"].pop(i)
                    save_posts(posts_data)
                else:
                    print(f"Erro ao publicar! {message}")
            else:
                print("Não é possível postar devido aos limites da API!")
        
        elif action == "C":
            # Cancelar o processo de agendamento
            print("Processo de agendamento cancelado.")
            break
    
    print("\nProcesso de agendamento concluído.")
    input("\nPressione ENTER para voltar ao menu principal...")

def show_statistics():
    """Exibe estatísticas sobre as postagens."""
    clear_screen()
    print("\n===== ESTATÍSTICAS =====\n")
    
    stats = get_stats()
    user_success, user_info = get_user_info()
    
    print(f"Postagens pendentes: {stats['total_pending']}")
    print(f"Postagens aprovadas: {stats['total_approved']}")
    print(f"Postagens agendadas: {stats['total_scheduled']}")
    print(f"Postagens publicadas: {stats['total_posted']}")
    print(f"Total de postagens: {stats['total_all']}")
    print(f"Postagens hoje: {stats['posts_today']}")
    print(f"Postagens neste mês: {monthly_posts}")
    print(f"Limite diário: {daily_posts}/{DAILY_POST_LIMIT}")
    print(f"Limite mensal: {monthly_posts}/{MONTHLY_POST_LIMIT}")
    
    if user_success:
        print("\nInformações da conta:")
        print(f"Nome: {user_info.get('name', 'N/A')}")
        print(f"Usuário: @{user_info.get('username', 'N/A')}")
        
        if 'followers' in user_info:
            print(f"Seguidores: {user_info.get('followers', 'N/A')}")
            print(f"Seguindo: {user_info.get('following', 'N/A')}")
            print(f"Total de tweets: {user_info.get('tweets', 'N/A')}")
    
    input("\nPressione ENTER para continuar...")

def display_dashboard():
    """Exibe o dashboard interativo e processa a entrada do usuário."""
    while bot_running:
        clear_screen()
        
        # Cabeçalho
        print("\n===== BOT PARA X - DASHBOARD =====\n")
        
        # Informações rápidas
        stats = get_stats()
        print(f"Postagens pendentes: {stats['total_pending']} | "
              f"Aprovadas: {stats['total_approved']} | "
              f"Agendadas: {stats['total_scheduled']} | "
              f"Publicadas hoje: {stats['posts_today']}")
        
        print(f"Limites: Diário {daily_posts}/{DAILY_POST_LIMIT} | "
              f"Mensal {monthly_posts}/{MONTHLY_POST_LIMIT}")
        
        # Tendências
        print("\nTendências globais:")
        trend_list = format_trend_list()
        for i, trend in enumerate(trend_list[:3]):  # Mostra apenas 3 tendências no dashboard
            print(trend)
        
        # Menu principal
        print("\nMenu Principal:")
        print("1. Criar nova postagem")
        print("2. Listar postagens")
        print("3. Aprovar postagens pendentes")
        print("4. Agendar postagens aprovadas")
        print("5. Ver todas as tendências")
        print("6. Atualizar tendências")
        print("7. Ver estatísticas")
        print("0. Sair")
        
        choice = input("\nEscolha uma opção: ")
        
        if choice == "1":
            create_new_post()
        elif choice == "2":
            list_posts()
        elif choice == "3":
            approve_posts()
        elif choice == "4":
            schedule_approved_posts()
        elif choice == "5":
            clear_screen()
            print("\n===== TENDÊNCIAS GLOBAIS =====\n")
            for line in format_trend_list():
                print(line)
            input("\nPressione ENTER para continuar...")
        elif choice == "6":
            print("\nAtualizando tendências...")
            if update_trends():
                print("Tendências atualizadas com sucesso!")
            else:
                print("Falha ao atualizar tendências. Verifique o log para mais detalhes.")
            time.sleep(2)
        elif choice == "7":
            show_statistics()
        elif choice == "0":
            confirm = input("Tem certeza que deseja sair? (S/N): ").upper()
            if confirm == "S":
                global bot_running
                bot_running = False
                print("Encerrando o bot...")
                break
        else:
            print("Opção inválida!")
            time.sleep(1)

def process_pending_now_posts():
    """
    Processa posts aprovados com horário "now" para publicação imediata.
    Executado a cada 5 minutos pelo scheduler.
    """
    if not can_post_today() or not can_post_this_month():
        logging.warning("Não é possível processar posts 'now' devido aos limites da API")
        return
    
    posts_data = load_posts()
    now_posts = [p for p in posts_data["approved"] if p["time"] == "now"]
    
    if not now_posts:
        return
    
    logging.info(f"Processando {len(now_posts)} posts com horário 'now'")
    
    for post in now_posts:
        logging.info(f"Publicando post imediato: '{post['text'][:50]}...'")
        
        success, message, tweet_data = post_tweet(post["text"])
        
        if success:
            # Atualiza contadores
            global monthly_posts, daily_posts
            monthly_posts += 1
            daily_posts += 1
            
            # Remove da lista de aprovados e adiciona ao histórico
            posts_data["approved"] = [p for p in posts_data["approved"] 
                                    if p.get("id") != post.get("id")]
            
            post["posted_at"] = datetime.now().isoformat()
            post["status"] = "posted"
            posts_data["history"].append(post)
            save_posts(posts_data)
            
            logging.info(f"Post 'now' publicado com sucesso: {message}")
        else:
            logging.error(f"Falha ao publicar post 'now': {message}")

def scheduler_job():
    """Função executada pela thread do scheduler."""
    global bot_running
    
    # Inicializa o scheduler
    schedule.every().day.at("00:00").do(reset_daily_count)
    schedule.every().day.at(TREND_UPDATE_HOUR).do(update_trends)
    schedule.every(5).minutes.do(process_pending_now_posts)
    
    # Agenda para verificar o primeiro dia do mês
    def check_month_reset():
        if datetime.now().day == 1 and datetime.now().hour == 0:
            reset_monthly_count()
    
    schedule.every().hour.do(check_month_reset)
    
    while bot_running:
        schedule.run_pending()
        time.sleep(1)

def main():
    """Função principal do bot."""
    global monthly_posts, daily_posts, scheduler_thread, trends, trends_last_updated
    
    try:
        clear_screen()
        print("Inicializando Bot para X...\n")
        
        # Inicializa a API
        success, message = initialize_api()
        if not success:
            logging.critical(f"Falha ao inicializar API: {message}")
            print(f"Erro de inicialização: {message}")
            print("\nVerifique suas credenciais no arquivo .env e tente novamente.")
            return
        
        print(f"API inicializada: {message}")
        
        # Carrega contadores de posts
        monthly_posts, daily_posts = load_post_counts()
        print(f"Contadores carregados: {monthly_posts} posts neste mês, {daily_posts} posts hoje")
        
        # Carrega tendências
        print("Carregando tendências...")
        if update_trends():
            print("Tendências carregadas com sucesso!")
        else:
            print("Aviso: Não foi possível carregar tendências. Tentaremos novamente mais tarde.")
        
        # Recuperação de agendamentos
        print("Recuperando agendamentos...")
        scheduled_posts = get_scheduled_posts_for_recovery()
        
        if scheduled_posts:
            print(f"Encontrados {len(scheduled_posts)} posts agendados para recuperação.")
            for post in scheduled_posts:
                if post["time"] != "now" and validate_time(post["time"]):
                    # Verifica se o horário já passou hoje
                    time_parts = post["time"].split(":")
                    hour = int(time_parts[0])
                    minute = int(time_parts[1])
                    
                    now = datetime.now()
                    schedule_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    
                    if schedule_time < now:
                        logging.info(f"Post agendado para {post['time']} já passou hoje, agendando para amanhã")
                        
                    schedule_post_at_time(post)
            print("Agendamentos recuperados com sucesso!")
        else:
            print("Nenhum agendamento para recuperar.")
        
        # Inicia a thread do scheduler
        scheduler_thread = threading.Thread(target=scheduler_job)
        scheduler_thread.daemon = True
        scheduler_thread.start()
        
        print("\nBot inicializado com sucesso!")
        print("Pressione ENTER para acessar o dashboard...")
        input()
        
        # Inicia o dashboard interativo
        display_dashboard()
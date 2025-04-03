# bot.py
"""
Bot para X (Twitter) - Interface interativa e lógica principal

Este módulo implementa o dashboard interativo no terminal e a lógica principal
do bot, incluindo o agendamento de posts e o loop de execução.

Modificações especiais para Windows:
- Uso de msvcrt para captar entrada com timeout na função approve_posts()
- Mensagens de debug em vários pontos para rastrear execução
- Pausa final com input() para evitar fechamento imediato do console

Autor: Uillen Machado (com ajustes)
Repositório: github.com/uillenmachado/botx
"""

import logging
import time
import os
import sys
import threading
from datetime import datetime, timedelta

# Caso esteja no Windows, importamos msvcrt para leitura de teclado
IS_WINDOWS = (os.name == 'nt')
if IS_WINDOWS:
    import msvcrt

try:
    import schedule  # type: ignore
except ImportError:
    print("ERRO: O pacote 'schedule' não está instalado.")
    print("Execute 'pip install schedule' para instalar.")
    sys.exit(1)

from config import (
    POST_INTERVAL_MINUTES, LOG_FILE,
    APPROVE_TIMEOUT, DAILY_POST_LIMIT, MONTHLY_POST_LIMIT,
    TREND_UPDATE_HOUR, DATE_FORMAT, WOEID_GLOBAL
)
from post_manager import (
    load_posts, save_posts, get_post_list, create_post, edit_post, delete_post,
    approve_post, schedule_post, mark_as_posted, get_scheduled_posts_for_recovery,
    get_stats, validate_time, get_post_by_id, get_pending_now_posts
)
from twitter_api import (
    initialize_api, get_trends, post_tweet, get_user_info
)

# -------------------------------------------------------------------
# Configuração de logging
# -------------------------------------------------------------------
try:
    log_dir = os.path.dirname(LOG_FILE)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        filename=LOG_FILE,
        filemode='a'
    )

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)
    
except Exception as e:
    print(f"Aviso: Não foi possível configurar o log para arquivo: {e}")
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

# -------------------------------------------------------------------
# Variáveis globais
# -------------------------------------------------------------------
trends = []
trends_last_updated = None
monthly_posts = 0
daily_posts = 0
bot_running = True
scheduler_thread = None
scheduled_jobs = {}
job_lock = threading.Lock()

# -------------------------------------------------------------------
# Funções utilitárias
# -------------------------------------------------------------------
def clear_screen():
    """Limpa a tela do terminal para melhor visualização."""
    os.system('cls' if os.name == 'nt' else 'clear')


def format_trend_list():
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
    global trends, trends_last_updated
    logging.info("DEBUG -> Atualizando tendências globais...")
    
    try:
        trends_data, timestamp = get_trends()
        if trends_data and len(trends_data) > 0 and "error" not in trends_data[0].get("name", "").lower():
            trends = trends_data
            trends_last_updated = timestamp
            nomes = [t['name'] for t in trends]
            logging.info(f"Tendências atualizadas: {', '.join(nomes)}")
            return True
        else:
            logging.error(f"Falha ao atualizar tendências: {trends_data[0]['name'] if trends_data else 'Sem dados'}")
            return False
    except Exception as e:
        logging.error(f"Erro ao atualizar tendências: {e}")
        return False


def load_post_counts():
    """Carrega a contagem de posts mensais e diários a partir do histórico."""
    posts_data = load_posts()
    today = datetime.now().date()
    current_month = today.replace(day=1)
    
    monthly_count = 0
    daily_count = 0
    
    for post in posts_data["history"]:
        if "posted_at" in post:
            try:
                posted_date = datetime.fromisoformat(post["posted_at"]).date()
                if posted_date.replace(day=1) == current_month:
                    monthly_count += 1
                if posted_date == today:
                    daily_count += 1
            except (ValueError, TypeError):
                logging.warning(f"Formato de data inválido para post: {post.get('id', 'N/A')[:8]}")
    
    logging.info(f"DEBUG -> Contagens: {monthly_count} este mês, {daily_count} hoje")
    return monthly_count, daily_count


def can_post_today():
    global daily_posts
    if daily_posts >= DAILY_POST_LIMIT:
        logging.warning(f"Limite diário de {DAILY_POST_LIMIT} posts atingido")
        return False
    return True


def can_post_this_month():
    global monthly_posts
    if monthly_posts >= MONTHLY_POST_LIMIT:
        logging.warning(f"Limite mensal de {MONTHLY_POST_LIMIT} posts atingido")
        return False
    return True


def reset_daily_count():
    global daily_posts
    daily_posts = 0
    logging.info("DEBUG -> Contador diário de posts resetado")


def reset_monthly_count():
    global monthly_posts
    monthly_posts = 0
    logging.info("DEBUG -> Contador mensal de posts resetado")


def check_month_reset():
    """Verifica se é dia 1 e reseta o contador mensal se estiver na 1ª hora."""
    current_date = datetime.now()
    if current_date.day == 1 and current_date.hour == 0 and current_date.minute < 5:
        reset_monthly_count()


def run_scheduler():
    logging.info("DEBUG -> Iniciando scheduler...")
    import schedule
    
    schedule.every().day.at("00:00").do(reset_daily_count)
    schedule.every().hour.do(check_month_reset)
    schedule.every(5).minutes.do(process_pending_now_posts)
    
    if TREND_UPDATE_HOUR:
        schedule.every().day.at(TREND_UPDATE_HOUR).do(update_trends)
    
    while bot_running:
        try:
            schedule.run_pending()
            time.sleep(1)
        except Exception as e:
            logging.error(f"Erro no scheduler: {e}")
            time.sleep(5)
    
    logging.info("DEBUG -> Scheduler encerrado.")


def post_scheduled_tweet(post):
    global monthly_posts, daily_posts
    
    if not can_post_today() or not can_post_this_month():
        logging.warning(f"Post '{post['text'][:30]}...' não publicado devido aos limites da API")
        return False
    
    post_id = post.get("id", "N/A")[:8]
    logging.info(f"DEBUG -> Publicando post agendado [ID:{post_id}]: '{post['text'][:50]}...'")
    try:
        success, message, tweet_data = post_tweet(post["text"])
        if success:
            monthly_posts += 1
            daily_posts += 1
            mark_as_posted(post)
            logging.info(f"Post [ID:{post_id}] publicado com sucesso: {message}")
            return True
        else:
            logging.error(f"Falha ao publicar post [ID:{post_id}]: {message}")
            return False
    except Exception as e:
        logging.error(f"Erro ao publicar post agendado [ID:{post_id}]: {e}")
        return False


def schedule_post_at_time(post):
    """Agenda um post para um horário específico no schedule."""
    global scheduled_jobs
    
    if post.get("time", "").lower() == "now":
        return False
    
    import schedule
    try:
        time_parts = post["time"].split(":")
        hour = int(time_parts[0])
        minute = int(time_parts[1])
        
        job = schedule.every().day.at(post["time"]).do(post_scheduled_tweet, post)
        post_id = post.get("id")
        if post_id:
            with job_lock:
                if post_id in scheduled_jobs:
                    schedule.cancel_job(scheduled_jobs[post_id])
                scheduled_jobs[post_id] = job
                logging.info(f"DEBUG -> Post agendado para {post['time']}: '{post['text'][:50]}...' [ID:{post_id[:8]}]")
            return True
        else:
            logging.warning(f"Agendamento de post sem ID: {post['text'][:50]}...")
            return False
    except Exception as e:
        logging.error(f"Erro ao agendar post: {e}")
        return False


# -------------------------------------------------------------------
# Função de leitura de ação com timeout (substitui select.select no Windows)
# -------------------------------------------------------------------
def get_user_action_with_timeout(tempo_segundos):
    """
    Lê uma tecla do usuário com timeout. Se não digitar nada no tempo,
    retorna None, indicando 'pular'.
    """
    logging.info("DEBUG -> get_user_action_with_timeout() iniciado")
    start = time.time()
    action = None
    
    print(f"Aguardando resposta... (timeout em {tempo_segundos} segundos)")
    
    if IS_WINDOWS:
        # Método Windows usando msvcrt
        while time.time() - start < tempo_segundos and action is None:
            if msvcrt.kbhit():
                tecla = msvcrt.getch()
                try:
                    # Decodifica a tecla. getch() retorna bytes
                    action = tecla.decode('utf-8', errors='ignore').upper()
                except:
                    action = None
            time.sleep(0.05)
    else:
        # Em outros sistemas, poderíamos manter select.select() ou algo similar
        import select
        while time.time() - start < tempo_segundos and action is None:
            rlist, _, _ = select.select([sys.stdin], [], [], 0.1)
            if rlist:
                action = sys.stdin.readline().strip().upper()
    
    logging.info(f"DEBUG -> Ação lida: {action}")
    return action


# -------------------------------------------------------------------
# CRUD da interface
# -------------------------------------------------------------------
def create_new_post():
    clear_screen()
    print("\n===== CRIAR NOVA POSTAGEM =====\n")
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
            time.sleep(0.2)
            input("\nPressione ENTER para continuar...")


def edit_existing_post(status):
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


# -------------------------------------------------------------------
# Aprovação com timeout (substituído select.select por get_user_action_with_timeout)
# -------------------------------------------------------------------
def approve_posts():
    clear_screen()
    print("\n===== APROVAR POSTAGENS =====\n")
    
    post_list = get_post_list("pending")
    if not post_list:
        print("Não há postagens pendentes para aprovação.")
        input("\nPressione ENTER para continuar...")
        return
    
    timeout_count = 0
    max_consecutive_timeouts = 3
    
    for i, post_str in enumerate(post_list):
        print(f"\n{post_str}")
        print("\nOpções:")
        print("A - Aprovar")
        print("R - Rejeitar")
        print("S - Pular")
        print("E - Editar antes de aprovar")
        print("C - Cancelar aprovações")
        
        # Lê ação com timeout
        action = get_user_action_with_timeout(APPROVE_TIMEOUT)
        
        if not action:
            print("Timeout! Pulando para a próxima postagem.")
            timeout_count += 1
            if timeout_count >= max_consecutive_timeouts:
                print(f"\nMuitos timeouts consecutivos ({max_consecutive_timeouts}). Encerrando processo de aprovação.")
                break
            continue
        else:
            timeout_count = 0
            action = action.strip().upper()[:1]  # Considera apenas primeiro caractere
        
        if action == "A":
            new_time = None
            time_change = input("Deseja alterar o horário? (S/N): ").upper()
            if time_change == "S":
                new_time = input("Digite o novo horário (HH:MM ou 'now'): ")
            
            success, message, post = approve_post(i, True, new_time)
            if success and post:
                print(f"Sucesso! {message}")
                if post.get("time", "").lower() != "now":
                    post_now = input("Deseja postar agora em vez de agendar? (S/N): ").upper()
                    if post_now == "S":
                        if can_post_today() and can_post_this_month():
                            pub_success, pub_message, tweet_data = post_tweet(post["text"])
                            if pub_success:
                                print(f"Post publicado! {pub_message}")
                                global monthly_posts, daily_posts
                                monthly_posts += 1
                                daily_posts += 1
                                posts_data = load_posts()
                                post_id = post.get("id")
                                if post_id:
                                    posts_data["approved"] = [p for p in posts_data["approved"] 
                                                              if p.get("id") != post_id]
                                    post["posted_at"] = datetime.now().isoformat()
                                    post["status"] = "posted"
                                    posts_data["history"].append(post)
                                    save_posts(posts_data)
                                else:
                                    logging.warning(f"Post sem ID encontrado ao tentar postar: {post['text'][:30]}...")
                            else:
                                print(f"Erro ao publicar! {pub_message}")
                        else:
                            print("Não é possível postar devido aos limites da API!")
                else:
                    print("Post aprovado para publicação imediata após aprovação.")
            else:
                print(f"Erro! {message}")
        
        elif action == "R":
            success, message, _ = approve_post(i, False)
            if success:
                print(f"Sucesso! {message}")
            else:
                print(f"Erro! {message}")
        
        elif action == "S":
            print("Postagem ignorada (pulada).")
        
        elif action == "E":
            print("\nDigite o novo texto (deixe em branco para manter o atual):")
            new_text = input("> ")
            print("\nDigite o novo horário (deixe em branco para manter o atual):")
            new_time = input("> ")
            edit_ok, edit_msg = edit_post(
                i,
                new_text=new_text if new_text.strip() else None,
                new_time=new_time if new_time.strip() else None,
                status="pending"
            )
            if edit_ok:
                print(f"Sucesso! {edit_msg}")
                approve_after_edit = input("Deseja aprovar esta postagem agora? (S/N): ").upper()
                if approve_after_edit == "S":
                    final_ok, final_msg, _ = approve_post(i, True)
                    if final_ok:
                        print(f"Sucesso! {final_msg}")
                    else:
                        print(f"Erro! {final_msg}")
            else:
                print(f"Erro! {edit_msg}")
        
        elif action == "C":
            print("Processo de aprovação cancelado.")
            break
        
        input("\nPressione ENTER para continuar...")
    
    print("\nProcesso de aprovação concluído.")
    input("\nPressione ENTER para voltar ao menu principal...")


def schedule_approved_posts():
    clear_screen()
    print("\n===== AGENDAR POSTAGENS =====\n")
    posts_data = load_posts()
    approved_posts = get_post_list("approved")
    
    if not approved_posts:
        print("Não há postagens aprovadas para agendar.")
        input("\nPressione ENTER para continuar...")
        return
    
    for i, post_str in enumerate(approved_posts):
        if i >= len(posts_data["approved"]):
            print("\nTodas as postagens foram processadas.")
            break
        
        post = posts_data["approved"][i]
        if post.get("time", "").lower() == "now":
            continue
        
        print(f"\n{post_str}")
        print("\nOpções:")
        print("A - Agendar para o horário definido")
        print("P - Postar agora")
        print("S - Pular")
        print("C - Cancelar agendamentos")
        
        action = input("\nEscolha uma opção: ").upper()
        
        if action == "A":
            success, message, scheduled_post = schedule_post(i, True)
            if success and scheduled_post:
                print(f"Sucesso! {message}")
                schedule_post_at_time(scheduled_post)
            else:
                print(f"Erro! {message}")
        
        elif action == "P":
            if can_post_today() and can_post_this_month():
                post_id = post.get("id", "N/A")[:8]
                logging.info(f"DEBUG -> Tentando postar imediatamente [ID:{post_id}]: '{post['text'][:50]}...'")
                pub_success, pub_message, _ = post_tweet(post["text"])
                if pub_success:
                    print(f"Post publicado! {pub_message}")
                    global monthly_posts, daily_posts
                    monthly_posts += 1
                    daily_posts += 1
                    post_id_full = post.get("id")
                    if post_id_full:
                        posts_data = load_posts()
                        posts_data["approved"] = [p for p in posts_data["approved"] 
                                                  if p.get("id") != post_id_full]
                        post["posted_at"] = datetime.now().isoformat()
                        post["status"] = "posted"
                        posts_data["history"].append(post)
                        save_posts(posts_data)
                    else:
                        logging.warning(f"Post sem ID ao tentar postar: {post['text'][:30]}...")
                else:
                    print(f"Erro ao publicar! {pub_message}")
            else:
                print("Não é possível postar devido aos limites da API!")
        
        elif action == "C":
            print("Processo de agendamento cancelado.")
            break
    
    print("\nProcesso de agendamento concluído.")
    input("\nPressione ENTER para voltar ao menu principal...")


def process_pending_now_posts():
    """Processa posts aprovados com horário 'now'."""
    if not can_post_today() or not can_post_this_month():
        logging.warning("Não é possível processar posts 'now' devido aos limites da API")
        return
    
    now_posts = get_pending_now_posts()
    if not now_posts:
        return
    
    logging.info(f"DEBUG -> Processando {len(now_posts)} posts com horário 'now'")
    for post in now_posts:
        if not can_post_today() or not can_post_this_month():
            logging.warning("Limite de posts atingido durante o processamento de posts 'now'")
            break
        
        post_id = post.get("id", "N/A")[:8]
        logging.info(f"DEBUG -> Publicando post imediato [ID:{post_id}]: '{post['text'][:50]}...'")
        success, message, tweet_data = post_tweet(post["text"])
        if success:
            global monthly_posts, daily_posts
            monthly_posts += 1
            daily_posts += 1
            post_id_full = post.get("id")
            if post_id_full:
                posts_data = load_posts()
                posts_data["approved"] = [p for p in posts_data["approved"] 
                                          if p.get("id") != post_id_full]
                post["posted_at"] = datetime.now().isoformat()
                post["status"] = "posted"
                posts_data["history"].append(post)
                save_posts(posts_data)
                logging.info(f"Post 'now' [ID:{post_id_full}] publicado com sucesso: {message}")
            else:
                logging.warning(f"Post sem ID encontrado: {post['text'][:30]}...")
        else:
            logging.error(f"Falha ao publicar post 'now' [ID:{post_id}]: {message}")


# -------------------------------------------------------------------
# Dashboard
# -------------------------------------------------------------------
def dashboard():
    while bot_running:
        clear_screen()
        print("\n===== BOT X - DASHBOARD =====\n")
        print("1. Criar Nova Postagem")
        print("2. Listar Postagens")
        print("3. Aprovar Postagens Pendentes")
        print("4. Agendar Postagens Aprovadas")
        print("5. Atualizar Tendências")
        print("6. Exibir Estatísticas")
        print("7. Sair")
        
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
            update_trends()
            input("\nPressione ENTER para continuar...")
        elif choice == "6":
            stats = get_stats()
            clear_screen()
            print("\n===== ESTATÍSTICAS =====\n")
            print(f"Pendentes: {stats['total_pending']}")
            print(f"Aprovadas: {stats['total_approved']}")
            print(f"Agendadas: {stats['total_scheduled']}")
            print(f"Publicadas: {stats['total_posted']}")
            print(f"Total de Posts: {stats['total_all']}")
            print(f"Posts Hoje: {stats['posts_today']}")
            input("\nPressione ENTER para continuar...")
        elif choice == "7":
            print("Encerrando o bot...")
            stop_bot()
        else:
            print("Opção inválida!")
            input("\nPressione ENTER para continuar...")


def stop_bot():
    global bot_running
    bot_running = False


# -------------------------------------------------------------------
# main()
# -------------------------------------------------------------------
def main():
    print("DEBUG -> Iniciando main()...")
    success, message = initialize_api()
    print(f"DEBUG -> initialize_api() retornou: success={success}, message={message}")
    
    if not success:
        print(f"Erro ao conectar com a API: {message}")
        input("Pressione ENTER para sair...")
        return
    
    global monthly_posts, daily_posts
    print("DEBUG -> Carregando contadores de post...")
    monthly_posts, daily_posts = load_post_counts()
    print(f"DEBUG -> Contadores carregados: Mês={monthly_posts}, Dia={daily_posts}")
    
    print("DEBUG -> Atualizando tendências...")
    update_trends()
    
    print("DEBUG -> Iniciando thread do scheduler...")
    global scheduler_thread
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    
    print("DEBUG -> Recuperando posts agendados anteriores...")
    scheduled_posts = get_scheduled_posts_for_recovery()
    for post in scheduled_posts:
        schedule_post_at_time(post)
    
    print("DEBUG -> Chamando dashboard()...")
    dashboard()
    
    print("DEBUG -> Aguardando thread do scheduler...")
    if scheduler_thread and scheduler_thread.is_alive():
        scheduler_thread.join(timeout=5)
    
    print("DEBUG -> Encerrando main().")
    input("Pressione ENTER para sair...")


if __name__ == "__main__":
    main()

"""
Bot para X (Twitter) - Postagem Manual com Aprovação e Dashboard

Este script implementa um bot que permite ao usuário criar postagens manualmente,
se inspirando em tendências globais, aprovar cada uma, e agendá-las ou postar 
imediatamente no X (Twitter).

Configuração:
- Requer um arquivo .env com as credenciais da API do X
- Usa um arquivo posts.json para gerenciar postagens pendentes, aprovadas e agendadas
- Posta até 16 vezes por dia, das 08:00 às 23:00, a cada 60 minutos
- Busca as 5 principais tendências globais diariamente às 07:00 para inspiração

Autor: Uillen Machado
Repositório: github.com/uillenmachado/botx
"""

import os
import logging
import schedule
import time
from datetime import datetime
from inputimeout import inputimeout, TimeoutOccurred

# Importa os módulos do projeto
from config import (
    START_HOUR, END_HOUR, DAILY_POST_LIMIT, MONTHLY_POST_LIMIT, 
    POST_INTERVAL_MINUTES, APPROVE_TIMEOUT, TREND_UPDATE_HOUR,
    LOG_FILE, DATE_FORMAT
)
import post_manager
import twitter_api

# Variáveis globais
monthly_posts = 0
daily_posts = 0
posts_data = None
trends_list = []
last_trend_update = None

# Configura o logging
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

def load_data():
    """
    Carrega os dados necessários para o funcionamento do bot:
    - Arquivo de postagens (posts.json)
    - Contadores de posts (mensal e diário)
    """
    global posts_data, monthly_posts, daily_posts
    
    # Carrega o arquivo de postagens
    posts_data = post_manager.load_posts()
    
    # Define os contadores baseados no histórico
    stats = post_manager.get_stats(posts_data)
    daily_posts = stats["posts_today"]
    
    # Para o contador mensal, consideramos o total de posts no histórico do mês atual
    current_month = datetime.now().month
    current_year = datetime.now().year
    monthly_posts = 0
    
    for post in posts_data["history"]:
        if "posted_at" in post:
            post_date = datetime.fromisoformat(post["posted_at"])
            if post_date.month == current_month and post_date.year == current_year:
                monthly_posts += 1
    
    logging.info(f"Dados carregados: {stats['total_pending']} pendentes, {stats['total_approved']} aprovados, "
                f"{stats['total_scheduled']} agendados, {monthly_posts} posts este mês")

def reconnect_api():
    """
    Tenta reconectar com a API do X em caso de falha.
    
    Returns:
        bool: True se a conexão foi estabelecida, False caso contrário.
    """
    success, message = twitter_api.initialize_api()
    if success:
        logging.info("Reconexão com a API do X bem-sucedida.")
        return True
    else:
        logging.error(f"Falha ao reconectar com a API do X: {message}")
        return False

def update_trends():
    """
    Atualiza a lista de tendências globais e registra o momento da atualização.
    """
    global trends_list, last_trend_update
    
    try:
        trends, timestamp = twitter_api.get_trends()
        if trends and len(trends) > 0:
            trends_list = trends
            last_trend_update = timestamp
            logging.info(f"Tendências atualizadas: {', '.join([t['name'] for t in trends_list])}")
            return True
        else:
            logging.warning("Não foi possível obter tendências.")
            return False
    except Exception as e:
        logging.error(f"Erro ao atualizar tendências: {e}")
        return False

def create_post():
    """
    Permite ao usuário criar uma nova postagem e adicioná-la à lista de pendentes.
    Mostra as tendências globais para inspiração.
    Inclui validações para o texto e horário da postagem.
    """
    global posts_data
    
    print("\n=== Criar Nova Postagem ===")
    print("Tendências globais para inspiração:")
    for i, trend in enumerate(trends_list, 1):
        volume = trend.get("volume", "N/A")
        print(f"{i}. {trend['name']} (Volume: {volume})")
    
    if last_trend_update:
        print(f"\nÚltima atualização das tendências: {last_trend_update.strftime(DATE_FORMAT)}")
    
    print("\nDigite sua postagem (você pode usar as tendências acima ou criar algo novo).")

    try:
        texto = input("Digite o texto da postagem (máximo 280 caracteres): ").strip()
        if not texto:
            print("Erro: O texto não pode estar vazio.")
            return

        horario = input("Digite o horário para postagem (formato HH:MM, entre 08:00 e 23:00, ou deixe em branco para postar agora): ").strip()
        if not horario:
            horario = "now"
            
        # Cria a postagem usando o post_manager
        success, message = post_manager.create_post(texto, horario, posts_data)
        print(message)
        
    except Exception as e:
        logging.error(f"Erro ao criar postagem: {e}")
        print(f"Ocorreu um erro ao criar a postagem: {e}")

def approve_posts():
    """
    Permite ao usuário aprovar ou rejeitar postagens pendentes, com opção de postar agora ou agendar.
    Inclui validações para horários de agendamento.
    """
    global posts_data
    
    if not posts_data["pending"]:
        print("Nenhuma postagem pendente para aprovar.")
        return

    print("\n=== Aprovar Postagens ===")
    
    # Exibe a lista de posts pendentes
    post_list = post_manager.get_post_list("pending", posts_data)
    for post in post_list:
        print(post)
    
    # Cria uma cópia para iterar, pois vamos modificar a lista original
    pending_posts = posts_data["pending"].copy()
    
    for i, post in enumerate(pending_posts):
        print(f"\nPostagem #{i + 1}:")
        print(f"Texto: {post['text']}")
        print(f"Horário: {post['time']}")
        
        try:
            choice = inputimeout(
                prompt="Aprovar esta postagem? (s/n) [Timeout em 30s]: ",
                timeout=APPROVE_TIMEOUT
            ).lower()
            
            if choice == "s":
                if post["time"] == "now":
                    action = input("Postar agora (1) ou agendar para outro horário (2)? ")
                    if action == "1":
                        # Aprova o post
                        success, msg, approved_post = post_manager.approve_post(i, True, None, posts_data)
                        if not success:
                            print(msg)
                            continue
                        
                        # Posta imediatamente
                        print("Publicando imediatamente...")
                        post_success, post_msg, post_data = twitter_api.post_tweet(post["text"])
                        
                        if post_success:
                            # Marca como publicado
                            post_manager.mark_as_posted(approved_post, posts_data)
                            print("Postagem publicada imediatamente!")
                        else:
                            print(f"Erro ao publicar: {post_msg}")
                    else:
                        new_time = input("Digite o novo horário (formato HH:MM, entre 08:00 e 23:00): ")
                        # Aprova com o novo horário
                        success, msg, _ = post_manager.approve_post(i, True, new_time, posts_data)
                        print(msg)
                else:
                    # Aprova para o horário original
                    success, msg, _ = post_manager.approve_post(i, True, None, posts_data)
                    print(msg)
            else:
                # Rejeita o post
                success, msg, _ = post_manager.approve_post(i, False, None, posts_data)
                print(msg)
                
        except TimeoutOccurred:
            print("Tempo esgotado. Postagem mantida como pendente.")
            continue
        except Exception as e:
            logging.error(f"Erro ao processar aprovação: {e}")
            print(f"Erro ao processar aprovação: {e}")
            continue
    
    # Atualiza os posts_data após todas as operações
    posts_data = post_manager.load_posts()

def post_now(text):
    """
    Publica um tweet imediatamente.
    
    Args:
        text (str): Texto do tweet a ser publicado.
    
    Returns:
        bool: True se o post foi publicado com sucesso, False caso contrário.
    """
    global monthly_posts, daily_posts
    
    try:
        if monthly_posts >= MONTHLY_POST_LIMIT:
            logging.warning("Limite mensal de postagens atingido. Pulando postagem.")
            print("Aviso: Limite mensal de postagens atingido. Postagem não enviada.")
            return False
            
        if daily_posts >= DAILY_POST_LIMIT:
            logging.warning("Limite diário de postagens atingido. Pulando postagem.")
            print("Aviso: Limite diário de postagens atingido. Postagem não enviada.")
            return False

        # Usa a função do módulo twitter_api para publicar
        success, message, post_data = twitter_api.post_tweet(text)
        
        if success:
            monthly_posts += 1
            daily_posts += 1
            logging.info(f"Post publicado imediatamente: {text[:30]}... Total mensal: {monthly_posts}/{MONTHLY_POST_LIMIT}, Diário: {daily_posts}/{DAILY_POST_LIMIT}")
            return True
        else:
            logging.error(f"Erro ao publicar tweet: {message}")
            print(f"Erro ao publicar tweet: {message}")
            return False
            
    except Exception as e:
        logging.error(f"Erro inesperado ao publicar tweet: {e}")
        print(f"Erro inesperado ao publicar tweet: {e}")
        return False

def post_tweet(post):
    """
    Publica um tweet agendado.
    
    Args:
        post (dict): Dicionário com informações do post a ser publicado.
    
    Returns:
        bool: True se o post foi publicado com sucesso, False caso contrário.
    """
    global monthly_posts, daily_posts, posts_data
    
    try:
        text = post["text"]
        
        if monthly_posts >= MONTHLY_POST_LIMIT:
            logging.warning("Limite mensal de postagens atingido. Pulando postagem agendada.")
            return False
            
        if daily_posts >= DAILY_POST_LIMIT:
            logging.warning("Limite diário de postagens atingido. Pulando postagem agendada.")
            return False

        # Usa a função do módulo twitter_api para publicar
        success, message, post_data = twitter_api.post_tweet(text)
        
        if success:
            monthly_posts += 1
            daily_posts += 1
            logging.info(f"Post agendado publicado: {text[:30]}... Total mensal: {monthly_posts}/{MONTHLY_POST_LIMIT}, Diário: {daily_posts}/{DAILY_POST_LIMIT}")
            
            # Marca como publicado e remove da lista de agendados
            post_manager.mark_as_posted(post, posts_data)
            return True
        else:
            logging.error(f"Erro ao publicar tweet agendado: {message}")
            return False
    except Exception as e:
        logging.error(f"Erro inesperado ao publicar tweet agendado: {e}")
        return False

def reset_daily_counters():
    """
    Reseta o contador diário de postagens e atualiza o mensal no início de cada mês.
    """
    global daily_posts, monthly_posts
    current_date = datetime.now()
    if current_date.day == 1 and current_date.hour == 0 and current_date.minute == 0:
        monthly_posts = 0
        logging.info("Contador mensal resetado.")
    daily_posts = 0
    logging.info("Contador diário resetado.")

def display_stats():
    """
    Exibe estatísticas sobre o uso do bot e limites da API.
    """
    print("\n=== Estatísticas do Bot ===")
    print(f"Posts enviados hoje: {daily_posts}/{DAILY_POST_LIMIT}")
    print(f"Posts enviados este mês: {monthly_posts}/{MONTHLY_POST_LIMIT}")
    
    # Usa a função do módulo post_manager para obter estatísticas
    stats = post_manager.get_stats(posts_data)
    
    print(f"\nTotal de postagens:")
    print(f"- Pendentes: {stats['total_pending']}")
    print(f"- Aprovadas: {stats['total_approved']}")
    print(f"- Agendadas: {stats['total_scheduled']}")
    print(f"- Publicadas: {stats['total_posted']}")
    
    print(f"\nTendências atuais:")
    for i, trend in enumerate(trends_list, 1):
        volume = trend.get("volume", "N/A")
        print(f"{i}. {trend['name']} (Volume: {volume})")
        
    if last_trend_update:
        print(f"Última atualização das tendências: {last_trend_update.strftime(DATE_FORMAT)}")
    
    # Informações da API
    api_limits = twitter_api.check_api_limits()
    print("\nLimites da API:")
    print(f"- Postagens: {api_limits['post_tweets']['limit']} por mês")
    print(f"- Tendências: {api_limits['trends']['limit']} a cada {api_limits['trends']['period']}")
    print(f"- Nota: {api_limits['trends']['note']}")

def edit_or_delete_post():
    """
    Permite ao usuário editar ou excluir postagens pendentes e aprovadas.
    """
    global posts_data
    
    print("\n=== Editar ou Excluir Postagens ===")
    print("1. Editar/Excluir postagem pendente")
    print("2. Editar/Excluir postagem aprovada")
    print("3. Voltar ao menu principal")
    
    try:
        choice = input("Escolha uma opção (1-3): ")
        
        if choice == "1":
            status = "pending"
            status_nome = "pendente"
        elif choice == "2":
            status = "approved"
            status_nome = "aprovada"
        elif choice == "3":
            return
        else:
            print("Opção inválida.")
            return
        
        # Exibe a lista de posts do tipo selecionado
        post_list = post_manager.get_post_list(status, posts_data)
        if not post_list:
            print(f"Nenhuma postagem {status_nome} encontrada.")
            return
            
        print(f"\nLista de postagens {status_nome}s:")
        for post in post_list:
            print(post)
        
        try:
            post_index = int(input(f"\nDigite o número da postagem {status_nome} que deseja editar/excluir (ou 0 para cancelar): ")) - 1
            
            if post_index < 0:
                return
                
            if post_index >= len(posts_data[status]):
                print("Índice inválido.")
                return
                
            action = input("Deseja editar (e) ou excluir (x) esta postagem? ").lower()
            
            if action == "e":  # Editar
                new_text = input("Digite o novo texto (deixe em branco para manter o atual): ").strip()
                new_time = input("Digite o novo horário (deixe em branco para manter o atual): ").strip()
                
                # Se ambos estiverem vazios, não faz nada
                if not new_text and not new_time:
                    print("Nenhuma alteração realizada.")
                    return
                    
                success, message = post_manager.edit_post(
                    post_index,
                    new_text if new_text else None,
                    new_time if new_time else None,
                    status,
                    posts_data
                )
                print(message)
                
            elif action == "x":  # Excluir
                confirm = input("Tem certeza que deseja excluir esta postagem? (s/n): ").lower()
                if confirm == "s":
                    success, message = post_manager.delete_post(post_index, status, posts_data)
                    print(message)
                else:
                    print("Exclusão cancelada.")
            else:
                print("Ação inválida.")
                
        except ValueError:
            print("Entrada inválida. O número da postagem deve ser um número inteiro.")
            return
            
    except Exception as e:
        logging.error(f"Erro ao editar/excluir postagem: {e}")
        print(f"Ocorreu um erro: {e}")
    
    # Recarrega os dados após as alterações
    posts_data = post_manager.load_posts()

def recover_scheduled_posts():
    """
    Recupera as postagens agendadas do arquivo posts.json e recria os agendamentos.
    Esta função é executada na inicialização do bot para garantir que posts agendados
    antes de um reinício sejam retomados.
    
    Returns:
        int: Número de postagens recuperadas.
    """
    global posts_data
    
    try:
        # Obtém a lista de posts agendados
        scheduled_posts = post_manager.get_scheduled_posts_for_recovery(posts_data)
        count = 0
        
        for post in scheduled_posts:
            # Verifica se o horário ainda é válido (não passou)
            now = datetime.now().time()
            post_time = datetime.strptime(post["time"], "%H:%M").time()
            
            # Se já passou do horário hoje, não agenda
            if now > post_time:
                logging.info(f"Post agendado para {post['time']} não foi recuperado pois o horário já passou: {post['text'][:30]}...")
                continue
                
            # Agenda o post
            try:
                # Cria um job para o post com uma função lambda que captura o post
                schedule.every().day.at(post["time"]).do(lambda p=post: post_tweet(p))
                count += 1
                logging.info(f"Post recuperado e agendado para {post['time']}: {post['text'][:30]}...")
            except Exception as e:
                logging.error(f"Erro ao agendar post recuperado: {e}")
        
        return count
        
    except Exception as e:
        logging.error(f"Erro ao recuperar posts agendados: {e}")
        return 0

def schedule_approved_posts():
    """
    Agenda as postagens aprovadas para os horários definidos.
    Transfere posts da lista de aprovados para a lista de agendados.
    Esta função é chamada periodicamente pelo schedule.
    """
    global posts_data
    
    if not posts_data["approved"]:
        return
        
    logging.info(f"Verificando posts aprovados para agendamento. Total: {len(posts_data['approved'])}")
    
    # Cria uma cópia para iterar, pois vamos modificar a lista original
    approved_posts = posts_data["approved"].copy()
    
    for i, post in enumerate(approved_posts):
        if post["time"] != "now":
            # Tenta agendar o post
            try:
                # Agenda o post capturando o objeto post inteiro numa lambda
                job = schedule.every().day.at(post["time"]).do(lambda p=post: post_tweet(p))
                
                # Move para agendados
                success, message, _ = post_manager.schedule_post(0, True, posts_data)
                if success:
                    logging.info(f"Post agendado para {post['time']}: {post['text'][:30]}...")
                else:
                    logging.error(f"Erro ao agendar post: {message}")
                    
            except Exception as e:
                logging.error(f"Erro ao agendar post: {e}")
                continue

    # Recarrega os dados após as alterações
    posts_data = post_manager.load_posts()

def main():
    """
    Função principal que inicializa o bot e configura o agendamento.
    Fornece um dashboard interativo para o usuário gerenciar postagens.
    """
    global posts_data
    
    print("Inicializando Bot para X...")
    
    # Inicializa conexão com a API
    success, message = twitter_api.initialize_api()
    if not success:
        print(f"Erro ao conectar com a API do X: {message}")
        print("Verifique suas credenciais e conexão de internet.")
        return
    
    print(message)
    
    # Carrega os dados
    load_data()
    
    # Atualiza tendências
    update_trends()
    
    # Recupera posts agendados anteriores
    recovered = recover_scheduled_posts()
    if recovered > 0:
        print(f"Recuperados {recovered} posts agendados de execuções anteriores.")
    
    # Agenda o reset diário à meia-noite
    schedule.every().day.at("00:00").do(reset_daily_counters)
    # Agenda a atualização de tendências no horário definido
    schedule.every().day.at(TREND_UPDATE_HOUR).do(update_trends)
    # Agenda a verificação de postagens aprovadas a cada 5 minutos
    schedule.every(5).minutes.do(schedule_approved_posts)
    
    logging.info("Bot iniciado. Aguardando entrada do usuário e horários de postagem...")
    print("Bot para X iniciado com sucesso!")
    
    # Loop principal do bot
    try:
        while True:
            # Executa tarefas agendadas pendentes
            schedule.run_pending()
            
            print("\n=== Dashboard do Bot ===")
            print("1. Criar nova postagem (ver tendências para inspiração)")
            print("2. Aprovar postagens pendentes (postar agora ou agendar)")
            print("3. Ver postagens pendentes")
            print("4. Ver postagens aprovadas (prontas para agendamento)")
            print("5. Ver postagens agendadas")
            print("6. Editar ou excluir postagens")
            print("7. Ver estatísticas do bot")
            print("8. Atualizar tendências manualmente")
            print("9. Sair e continuar agendamento")
            
            try:
                # Removido o timeout do menu principal, conforme solicitado
                choice = input("Escolha uma opção (1-9): ")
            except KeyboardInterrupt:
                print("\nOperação cancelada. Retornando ao menu principal.")
                continue
            
            if choice == "1":
                create_post()
            elif choice == "2":
                approve_posts()
            elif choice == "3":
                print("\n=== Postagens Pendentes ===")
                post_list = post_manager.get_post_list("pending", posts_data)
                if not post_list:
                    print("Nenhuma postagem pendente.")
                for post in post_list:
                    print(post)
            elif choice == "4":
                print("\n=== Postagens Aprovadas (Prontas para Agendamento) ===")
                post_list = post_manager.get_post_list("approved", posts_data)
                if not post_list:
                    print("Nenhuma postagem aprovada.")
                for post in post_list:
                    print(post)
            elif choice == "5":
                print("\n=== Postagens Agendadas ===")
                post_list = post_manager.get_post_list("scheduled", posts_data)
                if not post_list:
                    print("Nenhuma postagem agendada.")
                for post in post_list:
                    print(post)
            elif choice == "6":
                edit_or_delete_post()
            elif choice == "7":
                display_stats()
            elif choice == "8":
                print("Atualizando tendências...")
                if update_trends():
                    print(f"Tendências atualizadas: {', '.join([t['name'] for t in trends_list])}")
                else:
                    print("Falha ao atualizar tendências. Tente novamente mais tarde.")
            elif choice == "9":
                print("Saindo do dashboard. O bot continuará rodando para postagens agendadas.")
                break
            else:
                print("Opção inválida. Por favor, escolha uma opção de 1 a 9.")
            
            # Recarrega os dados após cada interação para garantir consistência
            posts_data = post_manager.load_posts()
    
    except KeyboardInterrupt:
        print("\nBot encerrado pelo usuário.")
        logging.info("Bot encerrado pelo usuário.")
        return
    
    print("\nBot continua executando em segundo plano para publicar posts agendados.")
    print("Para interagir novamente com o dashboard, execute o bot novamente.")
    
    try:
        # Loop para manter o bot rodando e executar as tarefas agendadas
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nBot encerrado pelo usuário.")
        logging.info("Bot encerrado pelo usuário.")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Bot Daemon - Executa automação em background

Uso:
    python bot_daemon.py [--niche NICHO] [--interval MINUTOS]

Exemplo:
    python bot_daemon.py --niche tech --interval 15
"""
import os
import sys
import time
import signal
import logging
import argparse
from datetime import datetime

from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot_daemon.log')
    ]
)
logger = logging.getLogger('bot_daemon')

# Flag para shutdown graceful
running = True


def signal_handler(signum, frame):
    """Handler para shutdown graceful"""
    global running
    logger.info(f"Recebido sinal {signum}, encerrando...")
    running = False


def run_daemon(niche: str = "tech", interval_minutes: int = 15):
    """
    Loop principal do daemon.
    
    Args:
        niche: Nicho de atuação
        interval_minutes: Intervalo entre ciclos
    """
    global running
    
    # Configurar handlers de sinal
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Importar aqui para evitar imports circulares
    from app.services.bot_engine import create_bot
    
    logger.info(f"Iniciando daemon - Nicho: {niche}, Intervalo: {interval_minutes}min")
    
    try:
        bot = create_bot(niche=niche)
        logger.info("Bot engine inicializado com sucesso")
        
        # Status inicial
        status = bot.get_status()
        logger.info(f"Conta: @{status.get('account', {}).get('username', 'N/A')}")
        logger.info(f"Seguidores: {status.get('account', {}).get('followers', 'N/A')}")
        
        monetization = status.get('monetization', {})
        if monetization:
            progress = monetization.get('progress', {})
            logger.info(f"Progresso monetização: {progress.get('overall', 0)}%")
        
    except Exception as e:
        logger.error(f"Erro ao inicializar bot: {e}")
        return
    
    cycle_count = 0
    
    while running:
        try:
            cycle_count += 1
            logger.info(f"=== Ciclo #{cycle_count} iniciado ===")
            
            # Executar ciclo
            result = bot.run_cycle()
            
            # Log de ações
            for action in result.get("actions", []):
                action_type = action.get("type", "unknown")
                action_result = action.get("result", {})
                
                if action_result.get("success"):
                    logger.info(f"✅ {action_type}: {action_result}")
                elif action_result.get("skipped"):
                    logger.debug(f"⏭️ {action_type} pulado: {action_result.get('reason')}")
                else:
                    logger.warning(f"❌ {action_type} falhou: {action_result.get('error')}")
            
            # Log de erros
            for error in result.get("errors", []):
                logger.error(f"Erro no ciclo: {error}")
            
            if not result.get("actions"):
                logger.info("Nenhuma ação necessária neste ciclo")
            
            # Aguardar próximo ciclo
            logger.info(f"Próximo ciclo em {interval_minutes} minutos")
            
            # Sleep em intervalos pequenos para permitir shutdown rápido
            for _ in range(interval_minutes * 60):
                if not running:
                    break
                time.sleep(1)
                
        except Exception as e:
            logger.error(f"Erro no ciclo: {e}")
            time.sleep(60)  # Esperar 1 min antes de tentar novamente
    
    logger.info("Daemon encerrado")


def main():
    parser = argparse.ArgumentParser(description="Bot Daemon para monetização no X")
    
    parser.add_argument(
        "--niche",
        type=str,
        default=os.getenv("BOT_NICHE", "tech"),
        choices=["tech", "finance", "humor", "news", "lifestyle"],
        help="Nicho de atuação (default: tech)"
    )
    
    parser.add_argument(
        "--interval",
        type=int,
        default=int(os.getenv("BOT_INTERVAL", 15)),
        help="Intervalo entre ciclos em minutos (default: 15)"
    )
    
    parser.add_argument(
        "--once",
        action="store_true",
        help="Executar apenas um ciclo e sair"
    )
    
    args = parser.parse_args()
    
    if args.once:
        # Modo single-run
        from app.services.bot_engine import create_bot
        bot = create_bot(niche=args.niche)
        result = bot.run_cycle()
        print(f"Resultado: {result}")
    else:
        # Modo daemon
        run_daemon(niche=args.niche, interval_minutes=args.interval)


if __name__ == "__main__":
    main()

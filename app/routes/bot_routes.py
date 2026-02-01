"""
Rotas da API do Bot de Monetização
"""
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required
import os

bp = Blueprint('bot', __name__, url_prefix='/bot')


def get_bot():
    """Obtém instância do bot (lazy loading)"""
    from ..services.bot_engine import create_bot
    
    if not hasattr(current_app, '_bot_engine'):
        niche = os.getenv("BOT_NICHE", "tech")
        current_app._bot_engine = create_bot(niche=niche)
    
    return current_app._bot_engine


@bp.route('/status', methods=['GET'])
def status():
    """
    Retorna status completo do bot.
    
    Inclui:
    - Estatísticas da conta
    - Progresso para monetização
    - Análise de conteúdo
    - Próximas ações programadas
    """
    try:
        bot = get_bot()
        return jsonify(bot.get_status())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/post', methods=['POST'])
def create_post():
    """
    Cria um post original.
    
    Body JSON:
    - topic: Assunto do post (opcional, usa keyword do nicho)
    - style: Estilo (informativo, provocativo, humor, inspiracional)
    - include_hook: Incluir hook (default: true)
    - include_cta: Incluir CTA (default: true)
    - dry_run: Apenas gerar, não postar (default: false)
    """
    try:
        bot = get_bot()
        data = request.get_json() or {}
        
        result = bot.run_once(
            action_type="post",
            topic=data.get("topic"),
            style=data.get("style"),
            include_hook=data.get("include_hook", True),
            include_cta=data.get("include_cta", True),
            dry_run=data.get("dry_run", False)
        )
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/reply', methods=['POST'])
def create_reply():
    """
    Cria um reply estratégico.
    
    Body JSON:
    - post_id: ID do post para responder (opcional, busca viral automaticamente)
    - tone: Tom da resposta (agreeable, contrarian, curious, supportive)
    - dry_run: Apenas gerar, não postar
    """
    try:
        bot = get_bot()
        data = request.get_json() or {}
        
        result = bot.run_once(
            action_type="reply",
            post_id=data.get("post_id"),
            tone=data.get("tone", "agreeable"),
            dry_run=data.get("dry_run", False)
        )
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/thread', methods=['POST'])
def create_thread():
    """
    Cria uma thread.
    
    Body JSON:
    - topic: Assunto da thread
    - num_tweets: Número de tweets (default: 5)
    - style: Estilo
    """
    try:
        bot = get_bot()
        data = request.get_json() or {}
        
        result = bot.run_once(action_type="thread", **data)
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/quote', methods=['POST'])
def create_quote():
    """
    Cria um quote tweet de post viral.
    """
    try:
        bot = get_bot()
        result = bot.run_once(action_type="quote")
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/viral', methods=['GET'])
def find_viral():
    """
    Encontra posts virais para engajar.
    
    Query params:
    - query: Termo de busca
    - min_likes: Mínimo de likes (default: 100)
    - max_age_hours: Idade máxima em horas (default: 6)
    - limit: Número máximo de posts (default: 20)
    """
    try:
        bot = get_bot()
        
        result = bot.run_once(
            action_type="find_viral",
            query=request.args.get("query"),
            min_likes=int(request.args.get("min_likes", 100)),
            max_age_hours=int(request.args.get("max_age_hours", 6)),
            limit=int(request.args.get("limit", 20))
        )
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/analytics', methods=['GET'])
def analytics():
    """
    Retorna analytics detalhados.
    
    Query params:
    - days: Período de análise (default: 7)
    """
    try:
        bot = get_bot()
        days = int(request.args.get("days", 7))
        
        return jsonify({
            "account": bot.analytics.get_account_stats(),
            "performance": bot.analytics.get_recent_tweets_performance(days=days),
            "content_analysis": bot.analytics.analyze_best_performing_content(days=days),
            "monetization": bot.analytics.calculate_monetization_progress(),
            "growth": bot.analytics.get_growth_trend(days=30),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/monetization', methods=['GET'])
def monetization():
    """
    Retorna progresso para monetização.
    """
    try:
        bot = get_bot()
        return jsonify(bot.analytics.calculate_monetization_progress())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/schedule', methods=['GET'])
def get_schedule():
    """
    Retorna schedule recomendado para o dia.
    """
    try:
        bot = get_bot()
        return jsonify({
            "schedule": bot.strategy.get_daily_schedule(),
            "next_post_time": bot.strategy.get_next_post_time().isoformat(),
            "current_state": bot.strategy.state,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/cycle', methods=['POST'])
def run_cycle():
    """
    Executa um ciclo completo de automação.
    
    O ciclo verifica:
    1. Se deve postar (baseado no horário e limite diário)
    2. Se deve fazer reply
    3. Salva analytics
    """
    try:
        bot = get_bot()
        result = bot.run_cycle()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/generate', methods=['POST'])
def generate_content():
    """
    Gera conteúdo sem postar (preview).
    
    Body JSON:
    - type: "post", "reply", "thread"
    - topic: Assunto
    - style: Estilo
    - original_post: Texto do post original (para reply)
    - author: Username do autor (para reply)
    """
    try:
        bot = get_bot()
        data = request.get_json() or {}
        
        content_type = data.get("type", "post")
        
        if content_type == "post":
            content = bot.content.generate_post(
                topic=data.get("topic", ""),
                style=data.get("style", "informativo"),
                include_hook=data.get("include_hook", True),
                include_cta=data.get("include_cta", True)
            )
            return jsonify({"type": "post", "content": content})
        
        elif content_type == "reply":
            content = bot.content.generate_reply(
                original_post=data.get("original_post", ""),
                author=data.get("author", "user"),
                tone=data.get("tone", "agreeable"),
                add_value=data.get("add_value", True)
            )
            return jsonify({"type": "reply", "content": content})
        
        elif content_type == "thread":
            tweets = bot.content.generate_thread(
                topic=data.get("topic", ""),
                num_tweets=data.get("num_tweets", 5),
                style=data.get("style", "informativo")
            )
            return jsonify({"type": "thread", "tweets": tweets})
        
        else:
            return jsonify({"error": f"Tipo desconhecido: {content_type}"}), 400
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

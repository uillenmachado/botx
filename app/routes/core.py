
from flask import Blueprint, render_template, request, jsonify, current_app
from ..services.twitter_service import TwitterService
from ..models import ScheduledPost, db
from datetime import datetime
import bleach, random

bp=Blueprint('core',__name__)
ts=TwitterService(current_app.config.get('RATELIMIT'),current_app.config.get('RATELIMIT_WINDOW'))

def generate_post(context=""):
    prov=ts.content_pool("provocacoes")
    frases=ts.content_pool("frases_impacto")
    provoc=context.capitalize()+", né?" if context else random.choice(prov)
    impact=random.choice(frases)
    return f"{provoc}\n\n\"{impact}\""

@bp.route('/')
def index():
    return render_template('index.html')

@bp.route('/generate',methods=['POST'])
def gen():
    context=bleach.clean(request.form.get('context',''))
    post=generate_post(context)
    return jsonify(post=post)

@bp.route('/post',methods=['POST'])
def post_now():
    content=bleach.clean(request.form.get('post',''))[:280]
    res=ts.post(content)
    return jsonify(res)

@bp.route('/schedule',methods=['POST'])
def schedule():
    content=bleach.clean(request.form.get('post',''))[:280]
    time_str=request.form.get('time','')
    sched=ScheduledPost(content=content,time=time_str)
    db.session.add(sched);db.session.commit()
    return jsonify(status="success",message="Agendado")

@bp.route('/scheduled')
def scheduled():
    jobs=ScheduledPost.query.filter_by(sent=False).all()
    return jsonify([{"id":j.id,"content":j.content,"time":j.time} for j in jobs])

@bp.route('/history')
def history():
    hist=ts.client.get_users_tweets(id=ts.client.get_me().data.id,max_results=20,tweet_fields=["public_metrics"]).data
    return jsonify([{"text":h.text,"metrics":h.public_metrics} for h in hist])


@bp.route('/schedule', methods=['POST'])
def schedule():
    import re
    content = bleach.clean(request.form.get('post',''))[:280]
    time_str = request.form.get('time','')
    if not re.match(r'^([01]\d|2[0-3]):([0-5]\d)$', time_str):
        return jsonify(status="error", message="Formato de hora inválido. Use HH:MM")
    sched = ScheduledPost(content=content, time=time_str)
    db.session.add(sched); db.session.commit()
    return jsonify(status="success", message="Agendado")


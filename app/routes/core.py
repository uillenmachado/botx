import uuid
import os
import re
import random

from flask import Blueprint, render_template, request, jsonify, current_app
from ..services.twitter_service import TwitterService
from ..models import ScheduledPost, db
import bleach

bp = Blueprint('core', __name__)


def get_twitter_service():
    """Get TwitterService instance within app context"""
    return TwitterService(
        current_app.config.get('RATELIMIT', 25),
        current_app.config.get('RATELIMIT_WINDOW', 86400)
    )


def generate_post(context=""):
    """Generate a post combining provocations and impact phrases"""
    ts = get_twitter_service()
    prov = ts.content_pool("provocacoes")
    frases = ts.content_pool("frases_impacto")
    
    if not prov:
        prov = ["Pense nisso"]
    if not frases:
        frases = ["A mudança começa agora."]
    
    provoc = context.capitalize() + ", né?" if context else random.choice(prov)
    impact = random.choice(frases)
    return f"{provoc}\n\n\"{impact}\""


@bp.route('/')
def index():
    return render_template('index.html')


@bp.route('/generate', methods=['POST'])
def gen():
    context = bleach.clean(request.form.get('context', ''))
    post = generate_post(context)
    return jsonify(post=post)


@bp.route('/post', methods=['POST'])
def post_now():
    """Post tweet immediately or queue for async processing"""
    content = bleach.clean(request.form.get('post', ''))[:280]
    media_id = request.form.get('media_id')
    async_flag = request.form.get('async', '1')
    
    ts = get_twitter_service()
    
    if async_flag == '0':
        res = ts.post(content, media_id=media_id if media_id else None)
    else:
        res = ts.post_async(content, media_id if media_id else None)
    
    return jsonify(res)


@bp.route('/schedule', methods=['POST'])
def schedule():
    """Schedule a tweet for a specific time"""
    content = bleach.clean(request.form.get('post', ''))[:280]
    time_str = request.form.get('time', '')
    
    if not re.match(r'^([01]\d|2[0-3]):([0-5]\d)$', time_str):
        return jsonify(status="error", message="Formato de hora inválido. Use HH:MM")
    
    sched = ScheduledPost(content=content, time=time_str)
    db.session.add(sched)
    db.session.commit()
    return jsonify(status="success", message="Agendado")


@bp.route('/scheduled')
def scheduled():
    """Get scheduled posts as JSON"""
    jobs = ScheduledPost.query.filter_by(sent=False).all()
    return jsonify([{"id": j.id, "content": j.content, "time": j.time} for j in jobs])


@bp.route('/scheduled_view')
def scheduled_view():
    """Get scheduled posts as HTML page"""
    jobs = ScheduledPost.query.filter_by(sent=False).all()
    return render_template('scheduled.html', jobs=jobs)


@bp.route('/history')
def history():
    """Get recent tweet history with metrics"""
    ts = get_twitter_service()
    try:
        hist = ts.client.get_users_tweets(
            id=ts.client.get_me().data.id,
            max_results=20,
            tweet_fields=["public_metrics"]
        ).data
        return jsonify([{"text": h.text, "metrics": h.public_metrics} for h in hist])
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route('/upload', methods=['POST'])
def upload():
    """Upload image for tweet attachment"""
    from werkzeug.utils import secure_filename
    
    file = request.files.get('file')
    if not file:
        return jsonify(status="error", message="No file"), 400
    
    mime = file.mimetype
    if mime not in ['image/png', 'image/jpeg', 'image/gif']:
        return jsonify(status="error", message="Invalid image type"), 400
    
    # Ensure uploads directory exists
    uploads_dir = os.path.join(current_app.root_path, '..', 'uploads')
    os.makedirs(uploads_dir, exist_ok=True)
    
    filename = secure_filename(f"{uuid.uuid4().hex}_{file.filename}")
    path = os.path.join(uploads_dir, filename)
    file.save(path)
    
    ts = get_twitter_service()
    media_id = ts.upload_image(path)
    
    if not media_id:
        return jsonify(status="error", message="Upload failed"), 500
    
    return jsonify(status="success", media_id=media_id)

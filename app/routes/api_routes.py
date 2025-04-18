
from flask_restx import Resource, Namespace
from ..models import ScheduledPost, PostHistory
from .. import db

def init(api):
    ns=Namespace('v1')
    @ns.route('/scheduled')
    class Schedules(Resource):
        def get(self):return [{"id":s.id,"content":s.content,"time":s.time} for s in ScheduledPost.query.all()]
    api.add_namespace(ns)

import logging
from flask import Blueprint, jsonify

class Metrics:
    def __init__(self):
        self.posts_success=0
        self.posts_failed=0
        self.scheduled=0
        self.rate_limit_hits=0
    def to_dict(self):
        return self.__dict__

metrics = Metrics()
metrics_bp = Blueprint('metrics', __name__)

@metrics_bp.route('/', methods=['GET'])
def get_metrics():
    return jsonify(metrics.to_dict())
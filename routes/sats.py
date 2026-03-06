from flask import Blueprint, jsonify
from services.stats_engine import calculate_stats

stats_bp = Blueprint("stats", __name__)


@stats_bp.route("/stats")

def stats():

    data = calculate_stats()

    return jsonify(data)
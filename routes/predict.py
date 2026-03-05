from flask import Blueprint, request, jsonify
from services.predictor import predict_match

predict_bp = Blueprint("predict", __name__)

@predict_bp.route("/predict", methods=["POST"])
def predict():

    data = request.get_json()

    home_team = data.get("home_team")
    away_team = data.get("away_team")

    result = predict_match(home_team, away_team)

    return jsonify(result)
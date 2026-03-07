from flask import Blueprint, request, jsonify
from services.predictor import predict_match

predict_bp = Blueprint("predict", __name__)


@predict_bp.route("/predict")
def predict():

    home = request.args.get("home")
    away = request.args.get("away")

    if not home or not away:
        return jsonify({"error": "use /predict?home=TeamA&away=TeamB"})

    result = predict_match(home, away)

    return jsonify(result)
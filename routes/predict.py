from flask import Blueprint, request, jsonify
from services.predictor import predict_match

predict_bp = Blueprint("predict", __name__)

@predict_bp.route("/predict", methods=["GET", "POST"])
def predict():

    if request.method == "GET":

        home_team = request.args.get("home")
        away_team = request.args.get("away")

        if not home_team or not away_team:
            return jsonify({
                "error": "use /predict?home=TeamA&away=TeamB"
            })

        result = predict_match(home_team, away_team)
        return jsonify(result)

    data = request.get_json()

    home_team = data.get("home_team")
    away_team = data.get("away_team")

    result = predict_match(home_team, away_team)

    return jsonify(result)
from flask import Flask, render_template, jsonify

from services.predictor import predict_match
from services.value_bet import find_value_bet


app = Flask(__name__, template_folder="templates")


@app.route("/")
def home():

    return render_template("index.html")


@app.route("/data")
def data():

    prediction = predict_match(
        "Barcelona",
        "Real Madrid"
    )

    value = find_value_bet(

        prediction["probabilities"]["home_win"]["prob"],
        prediction["probabilities"]["draw"]["prob"],
        prediction["probabilities"]["away_win"]["prob"]

    )

    prediction["value_bet"] = value

    return jsonify(prediction)


if __name__ == "__main__":

    app.run(debug=True)
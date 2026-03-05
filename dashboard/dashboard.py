from flask import Flask, render_template

from services.auto_analyzer import analyze_today_matches


app = Flask(__name__, template_folder="templates")


@app.route("/")
def dashboard():

    games = analyze_today_matches()

    return render_template(
        "index.html",
        games=games
    )


if __name__ == "__main__":

    app.run(debug=True)
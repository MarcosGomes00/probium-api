@app.route("/")
def home():
    return {"status": "PROBIUM API online"}


@app.route("/stats")
def stats():
    return calculate_stats()


@app.route("/predict")
def predict():
    home = request.args.get("home")
    away = request.args.get("away")

    return predict_match(home, away)


@app.route("/import-history")
def import_history():

    try:

        collect_top_leagues()

        return {
            "status": "ok",
            "message": "history import started"
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e)
        }, 500
import requests

BOT_TOKEN = "8725909088:AAGQMNr-9RVQB7hWmePCLmm0GwaGuzOVy-A"
CHAT_ID = "-1003814625223"


def prob_bar(prob):

    size = int(prob * 10)

    return "█" * size + "░" * (10 - size)


def market_text(b):

    if b["market"] == "HOME WIN":
        return f"🏠 {b['home']} vence"

    if b["market"] == "AWAY WIN":
        return f"✈️ {b['away']} vence"

    if b["market"] == "DRAW":
        return "🤝 Empate"

    if b["market"] == "OVER 2.5":
        return "⚽ Over 2.5 gols"

    if b["market"] == "UNDER 2.5":
        return "🛡️ Under 2.5 gols"

    if b["market"] == "BTTS YES":
        return "🔥 Ambas marcam"

    if b["market"] == "BTTS NO":
        return "❌ Ambas NÃO marcam"

    return b["market"]


def format_message(bets):

    msg = "🧠 PROBIUM EDGE AI\n"
    msg += "📊 Scanner Inteligente de Value Bets\n\n"

    medals = ["🥇", "🥈", "🥉", "🏅", "🏅"]

    for i, b in enumerate(bets, 1):

        prob = round(b["prob"] * 100)
        ev = round(b["ev"] * 100)

        medal = medals[i - 1]

        entrada = market_text(b)

        msg += (
            f"{medal} {b['home']} vs {b['away']}\n"
            f"🏆 {b['league']} | 🕒 {b['kickoff']}\n\n"

            f"🎯 ENTRADA DA APOSTA\n"
            f"➡️ {entrada}\n\n"

            f"💰 Odd: {b['odd']} | 📈 EV: +{ev}%\n"
            f"📊 Probabilidade\n"
            f"{prob_bar(b['prob'])} {prob}%\n\n"

            f"📉 Mercado analisado: {b['market']}\n"
            f"🤖 Confiança do modelo: {b['confidence']}\n"
            f"💰 Stake sugerida: {b['stake']}%\n\n"

            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )

    msg += "⚠️ Gestão de banca recomendada\n"
    msg += "🤖 Powered by PROBIUM EDGE AI"

    return msg


def send_message(bets):

    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️ Telegram não configurado")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": format_message(bets)
    }

    try:

        requests.post(url, data=payload, timeout=10)

        print("✅ Mensagem enviada para Telegram")

    except Exception as e:

        print("❌ Erro Telegram:", e)
import json
import os
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

# Configurações do BOT 2 e Canal
TELEGRAM_BOT_TOKEN_2 = "8185027087:AAH1JQJKtlWy_oUQpAvqvHEsFIVOK3ScYBc"
CHAT_ID = "-1003814625223"
HISTORY_FILE = "bets_history.json"

def enviar_telegram(texto):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN_2}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": texto, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload)
        print("✅ Dashboard enviado ao Telegram!")
    except Exception as e:
        print(f"Erro ao enviar: {e}")

def gerar_dashboard():
    if not os.path.exists(HISTORY_FILE):
        print("Nenhum histórico encontrado.")
        return

    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        bets = json.load(f)

    hoje = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime('%d/%m/%Y')
    
    total_apostas = 0
    greens = 0
    reds = 0
    lucro_total = 0.0

    # Contagem de resultados que já foram checados
    for bet in bets:
        if bet.get("checked") and bet.get("date") == hoje:
            total_apostas += 1
            lucro_total += bet.get("profit", 0)
            if bet.get("result") == "GREEN":
                greens += 1
            elif bet.get("result") == "RED":
                reds += 1

    if total_apostas == 0:
        print("Sem apostas finalizadas hoje para gerar relatório.")
        return

    win_rate = (greens / total_apostas) * 100

    if lucro_total > 0:
        saldo_msg = f"🟢 <b>POSITIVO:</b> +{lucro_total:.2f} Unidades"
    else:
        saldo_msg = f"🔴 <b>NEGATIVO:</b> {lucro_total:.2f} Unidades"

    mensagem = (
        f"📊 <b>DASHBOARD DE PERFORMANCE DO DIA</b> 📊\n"
        f"🗓 <b>Data:</b> {hoje}\n\n"
        f"🎯 <b>Total de Sinais Finalizados:</b> {total_apostas}\n"
        f"✅ <b>GREENS:</b> {greens}\n"
        f"❌ <b>REDS:</b> {reds}\n"
        f"📈 <b>Taxa de Acerto (Win Rate):</b> {win_rate:.1f}%\n\n"
        f"💰 <b>Saldo do Dia:</b>\n"
        f"{saldo_msg}\n\n"
        f"<i>Robô de Análise + Inteligência Artificial</i> 🤖"
    )

    enviar_telegram(mensagem)

if __name__ == "__main__":
    print("Gerando Dashboard...")
    gerar_dashboard()
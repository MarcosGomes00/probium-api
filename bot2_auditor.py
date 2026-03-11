import sqlite3
import requests
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# ==========================================
# CONFIGURAÇÕES BOT 2 - AUDITOR
# ==========================================

API_KEY_ODDS = "6a1c0078b3ed09b42fbacee8f07e7cc3"

TELEGRAM_TOKEN = "SEU_TOKEN_AQUI"

CHAT_ID = "-1003814625223"

DB_FILE = "probum.db"

# ==========================================
# CRIAR BANCO CASO NÃO EXISTA
# ==========================================

def inicializar_banco():

    conn = sqlite3.connect(DB_FILE)

    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS operacoes_tipster (
            id_aposta TEXT PRIMARY KEY,
            esporte TEXT,
            jogo TEXT,
            liga TEXT,
            mercado TEXT,
            selecao TEXT,
            odd REAL,
            prob REAL,
            ev REAL,
            stake REAL,
            status TEXT DEFAULT 'PENDENTE',
            lucro REAL DEFAULT 0,
            data_hora TEXT,
            pinnacle_odd REAL,
            ranking_score REAL
        )
    """)

    conn.commit()

    conn.close()

# ==========================================
# TELEGRAM
# ==========================================

def enviar_telegram(texto):

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": texto,
        "parse_mode": "HTML"
    }

    try:

        requests.post(url, json=payload, timeout=10)

    except:

        pass

# ==========================================
# OBTER RESULTADOS DA API
# ==========================================

def obter_resultados_api(esporte):

    url = f"https://api.the-odds-api.com/v4/sports/{esporte}/scores/"

    params = {
        "apiKey": API_KEY_ODDS,
        "daysFrom": 3
    }

    try:

        res = requests.get(url, params=params, timeout=15)

        if res.status_code == 200:

            return res.json()

    except:

        pass

    return []

# ==========================================
# RESOLVER APOSTA
# ==========================================

def resolver_aposta(aposta, placar):

    mercado = aposta['mercado'].upper()

    selecao = aposta['selecao']

    odd = aposta['odd']

    stake = aposta['stake']

    scores = placar.get("scores", [])

    if not scores:

        return "PENDENTE", 0

    h_team = placar["home_team"]

    a_team = placar["away_team"]

    h_score = next(
        (int(s["score"]) for s in scores if s["name"] == h_team),
        0
    )

    a_score = next(
        (int(s["score"]) for s in scores if s["name"] == a_team),
        0
    )

    total = h_score + a_score

    status = "RED"

    # ==========================================
    # FUTEBOL
    # ==========================================

    if aposta['esporte'] == 'soccer':

        if "H2H" in mercado:

            if "1" in selecao and h_score > a_score:

                status = "GREEN"

            elif "2" in selecao and a_score > h_score:

                status = "GREEN"

            elif "X" in selecao and h_score == a_score:

                status = "GREEN"

        elif "BTTS" in mercado:

            if "Sim" in selecao and h_score > 0 and a_score > 0:

                status = "GREEN"

            elif "Não" in selecao and (h_score == 0 or a_score == 0):

                status = "GREEN"

        elif "TOTAL" in mercado or "TOTALS" in mercado:

            try:

                linha = float(selecao.split()[-1])

                if "Over" in selecao and total > linha:

                    status = "GREEN"

                elif "Under" in selecao and total < linha:

                    status = "GREEN"

                elif total == linha:

                    status = "REEMBOLSO"

            except:

                pass

    # ==========================================
    # BASQUETE
    # ==========================================

    elif aposta['esporte'] == 'basketball':

        if "H2H" in mercado:

            if h_team in selecao and h_score > a_score:

                status = "GREEN"

            elif a_team in selecao and a_score > h_score:

                status = "GREEN"

        elif "SPREAD" in mercado:

            try:

                linha = float(selecao.split()[-1])

                if h_team in selecao:

                    resultado = h_score + linha - a_score

                else:

                    resultado = a_score + linha - h_score

                if resultado > 0:

                    status = "GREEN"

                elif resultado == 0:

                    status = "REEMBOLSO"

            except:

                pass

        elif "TOTAL" in mercado:

            try:

                linha = float(selecao.split()[-1])

                if "Over" in selecao and total > linha:

                    status = "GREEN"

                elif "Under" in selecao and total < linha:

                    status = "GREEN"

                elif total == linha:

                    status = "REEMBOLSO"

            except:

                pass

    # ==========================================
    # CÁLCULO FINANCEIRO
    # ==========================================

    if status == "GREEN":

        lucro = (stake * odd) - stake

    elif status == "REEMBOLSO":

        lucro = 0

    else:

        lucro = -stake

    return status, lucro

# ==========================================
# AUDITORIA
# ==========================================

def rotina_auditoria():

    conn = sqlite3.connect(DB_FILE)

    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM operacoes_tipster WHERE status='PENDENTE'"
    )

    pendentes = cursor.fetchall()

    if not pendentes:

        print("☕ Nenhuma aposta pendente para auditar.")

        conn.close()

        return

    esportes = set(p['esporte'] for p in pendentes)

    for esporte in esportes:

        resultados = obter_resultados_api(esporte)

        for placar in resultados:

            if not placar.get("completed"):

                continue

            for aposta in pendentes:

                if aposta['id_aposta'].startswith(placar['id']):

                    status, lucro = resolver_aposta(aposta, placar)

                    if status != "PENDENTE":

                        cursor.execute(
                            "UPDATE operacoes_tipster SET status=?, lucro=? WHERE id_aposta=?",
                            (status, lucro, aposta['id_aposta'])
                        )

    conn.commit()

    conn.close()

    print("✅ Auditoria finalizada.")

# ==========================================
# RELATÓRIO DIÁRIO
# ==========================================

def gerar_relatorio_diario():

    data_alvo = (
        datetime.now(ZoneInfo("America/Sao_Paulo"))
        - timedelta(days=1)
    ).strftime('%d/%m/%Y')

    conn = sqlite3.connect(DB_FILE)

    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM operacoes_tipster WHERE data_hora=? AND status!='PENDENTE'",
        (data_alvo,)
    )

    ops = cursor.fetchall()

    conn.close()

    if not ops:

        return

    total = len(ops)

    greens = sum(1 for o in ops if o['status'] == 'GREEN')

    reds = sum(1 for o in ops if o['status'] == 'RED')

    voids = sum(1 for o in ops if o['status'] == 'REEMBOLSO')

    lucro = sum(o['lucro'] for o in ops)

    investido = sum(o['stake'] for o in ops)

    roi = (lucro / investido * 100) if investido > 0 else 0

    winrate = (greens / (greens + reds) * 100) if (greens + reds) > 0 else 0

    emoji = "💰" if lucro >= 0 else "🩸"

    txt = (
        f"📊 <b>RELATÓRIO DIÁRIO SINDICATO ({data_alvo})</b>\n\n"
        f"✅ Greens: {greens}\n"
        f"❌ Reds: {reds}\n"
        f"🔄 Devolvidas: {voids}\n"
        f"🎯 Winrate: {winrate:.1f}%\n\n"
        f"💵 Investido: {investido:.2f}u\n"
        f"{emoji} Resultado: {lucro:+.2f}u\n"
        f"📈 ROI: {roi:+.2f}%"
    )

    enviar_telegram(txt)

# ==========================================
# LOOP PRINCIPAL
# ==========================================

if __name__ == "__main__":

    inicializar_banco()

    while True:

        agora = datetime.now(ZoneInfo("America/Sao_Paulo"))

        rotina_auditoria()

        if agora.hour == 9 and agora.minute == 0:

            gerar_relatorio_diario()

            time.sleep(60)

        time.sleep(3600)
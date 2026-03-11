import asyncio
import aiohttp
import sqlite3
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# ==========================================
# CONFIGURAÇÕES BOT 3 - BASQUETE
# ==========================================
API_KEYS_ODDS = [
    "6a1c0078b3ed09b42fbacee8f07e7cc3", "4949c49070dd3eff2113bd1a07293165",
    "0ecb237829d0f800181538e1a4fa2494", "4790419cc795932ffaeb0152fa5818c8",
    "5ee1c6a8c611b6c3d6aff8043764555f", "b668851102c3e0a56c33220161c029ec",
    "0d43575dd39e175ba670fb91b2230442", "d32378e66e89f159688cc2239f38a6a4",
    "713146de690026b224dd8bbf0abc0339"
]

# Token e Chat exclusivo do Basquete para organização
TELEGRAM_TOKEN = "8413563055:AAGyovCDMJOxiAukTbXwaJPm3ZDckIf7qJU" 
CHAT_ID = "-1003814625223"
DB_FILE = "probum.db"
SCAN_INTERVAL = 21600 # 6 Horas

SOFT_BOOKIES = ["bet365","betano","1xbet","draftkings","williamhill","unibet","888sport","betfair_ex_eu"]
SHARP_BOOKIE = "pinnacle"
TODAS_CASAS = SOFT_BOOKIES + [SHARP_BOOKIE]

# LIGAS DE ALTA LIQUIDEZ (NBA e Euroleague são as mais seguras para Basquete)
LEAGUE_TIERS = {
    "basketball_nba": 1.5, 
    "basketball_euroleague": 1.2
}

LIGAS = list(LEAGUE_TIERS.keys())
jogos_enviados = {}
chave_odds_atual = 0 
api_lock = asyncio.Lock()

def carregar_memoria_banco():
    global jogos_enviados
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT id_aposta FROM operacoes_tipster WHERE status = 'PENDENTE' AND esporte = 'basketball'")
        for (id_aposta,) in cursor.fetchall():
            jogos_enviados[id_aposta.split("_")[0]] = datetime.now(ZoneInfo("America/Sao_Paulo")) + timedelta(hours=24)
        conn.close()
    except: pass

def salvar_aposta_banco(op, stake):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        id_aposta = f"{op['jogo_id']}_{op['mercado_nome'][:4]}_{op['selecao_nome'][:4]}".replace(" ", "")
        hoje = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime('%d/%m/%Y')
        cursor.execute("""
            INSERT OR IGNORE INTO operacoes_tipster 
            (id_aposta, esporte, jogo, liga, mercado, selecao, odd, prob, ev, stake, status, lucro, data_hora, pinnacle_odd, ranking_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDENTE', 0, ?, ?, ?)
        """, (id_aposta, 'basketball', f"{op['home_team']} x {op['away_team']}", op['evento']['sport_title'], op['mercado_nome'], op['selecao_nome'], op['odd_bookie'], op['prob_justa'], op['ev_real'], stake, hoje, op.get('odd_pinnacle', 0), op.get('ranking_score', 0)))
        conn.commit()
        conn.close()
    except: pass

async def enviar_telegram_async(session, texto):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": texto, "parse_mode": "HTML", "disable_web_page_preview": True}
    try: await session.post(url, json=payload, timeout=10)
    except: pass

async def fazer_requisicao_odds(session, url, parametros):
    global chave_odds_atual
    for _ in range(len(API_KEYS_ODDS)):
        async with api_lock: chave_teste = API_KEYS_ODDS[chave_odds_atual]
        parametros["apiKey"] = chave_teste
        try:
            async with session.get(url, params=parametros, timeout=15) as resposta:
                if resposta.status == 200: return await resposta.json()
                elif resposta.status in [401, 429]:
                    async with api_lock: chave_odds_atual = (chave_odds_atual + 1) % len(API_KEYS_ODDS)
                else: return await resposta.json()
        except: pass
    return None

def validar_basquete(odd, ev):
    # Basquete tem margens menores na Pinnacle, então EVs de 1.5% já são ótimos
    if not (1.30 <= odd <= 5.0) or ev > 0.15: return False
    return ev >= 0.015

async def processar_liga_async(session, liga_key, agora_br):
    # BUSCA VENCEDOR (H2H), HANDICAPS (SPREADS) E PONTOS (TOTALS)
    parametros = {"regions": "eu", "markets": "h2h,spreads,totals", "bookmakers": ",".join(TODAS_CASAS)}
    data = await fazer_requisicao_odds(session, f"https://api.the-odds-api.com/v4/sports/{liga_key}/odds/", parametros)
    if not isinstance(data, list): return

    for evento in data:
        jogo_id = str(evento['id'])
        if jogo_id in jogos_enviados: continue
        
        horario_br = datetime.fromisoformat(evento["commence_time"].replace("Z", "+00:00")).astimezone(ZoneInfo("America/Sao_Paulo"))
        if not (30 <= (horario_br - agora_br).total_seconds() / 60 <= 1440): continue

        bookmakers = evento.get("bookmakers", [])
        pinnacle = next((b for b in bookmakers if b["key"] == SHARP_BOOKIE), None)
        if not pinnacle: continue

        oportunidades_jogo = []
        for soft_b in bookmakers:
            if soft_b["key"] not in SOFT_BOOKIES: continue
            
            for m_key in ["h2h", "spreads", "totals"]:
                pin_m = next((m for m in pinnacle.get("markets", []) if m["key"] == m_key), None)
                soft_m = next((m for m in soft_b.get("markets", []) if m["key"] == m_key), None)
                
                if pin_m and soft_m:
                    margem_pin = sum(1/out["price"] for out in pin_m["outcomes"] if out["price"] > 0)
                    for s_out in soft_m["outcomes"]:
                        # No basquete, comparamos a seleção e o ponto (linha)
                        p_match = next((p for p in pin_m["outcomes"] if p["name"] == s_out["name"] and p.get("point") == s_out.get("point")), None)
                        
                        if p_match:
                            prob_real = (1/p_match["price"]) / margem_pin
                            ev = (prob_real * s_out["price"]) - 1
                            
                            if validar_basquete(s_out["price"], ev):
                                score = ev * LEAGUE_TIERS.get(liga_key, 1.0)
                                oportunidades_jogo.append({
                                    "jogo_id": jogo_id, "evento": evento, "home_team": evento["home_team"], "away_team": evento["away_team"],
                                    "horario_br": horario_br, "mercado_nome": m_key.upper(), "selecao_nome": f"{s_out['name']} {s_out.get('point','')}",
                                    "odd_bookie": s_out["price"], "odd_pinnacle": p_match["price"], "prob_justa": prob_real, "ev_real": ev,
                                    "nome_bookie": soft_b["title"], "ranking_score": score
                                })

        if oportunidades_jogo:
            melhor = max(oportunidades_jogo, key=lambda x: x["ranking_score"])
            mercado_txt = "Vencedor" if melhor["mercado_nome"] == "H2H" else ("Handicap de Pontos" if melhor["mercado_nome"] == "SPREADS" else "Total de Pontos")
            
            txt = (f"🏀 <b>BASQUETE: VALOR DETECTADO</b>\n\n🏆 <b>Liga:</b> {melhor['evento']['sport_title']}\n⚔️ <b>Jogo:</b> {melhor['home_team']} x {melhor['away_team']}\n"
                   f"⏰ <b>Horário:</b> {melhor['horario_br'].strftime('%H:%M')}\n\n🎯 <b>Mercado:</b> {mercado_txt}\n👉 <b>Entrada:</b> {melhor['selecao_nome']}\n"
                   f"🏛️ <b>Casa:</b> {melhor['nome_bookie'].upper()}\n📈 <b>Odd:</b> {melhor['odd_bookie']:.2f}\n📊 <b>EV:</b> +{melhor['ev_real']*100:.1f}%\n")
            
            await enviar_telegram_async(session, txt)
            jogos_enviados[jogo_id] = agora_br + timedelta(hours=24)
            salvar_aposta_banco(melhor, 1.5)

async def loop_infinito():
    while True:
        async with aiohttp.ClientSession() as session:
            agora_br = datetime.now(ZoneInfo("America/Sao_Paulo"))
            print(f"🏀 Varredura Basquete Iniciada: {agora_br.strftime('%H:%M')}")
            await asyncio.gather(*[processar_liga_async(session, l, agora_br) for l in LIGAS])
        await asyncio.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    carregar_memoria_banco()
    asyncio.run(loop_infinito())
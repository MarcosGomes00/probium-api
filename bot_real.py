import asyncio
import aiohttp
import time
import json
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

try:
    from services.result_checker import check_results
    from services.stats_analyzer import check_advanced_stats
    from services.auto_learning import is_league_profitable
except Exception: pass

# ==========================================
# 1. CONFIGURAÇÕES E CHAVES
# ==========================================
API_KEYS_ODDS =[
    "6a1c0078b3ed09b42fbacee8f07e7cc3",
    "4949c49070dd3eff2113bd1a07293165",
    "0ecb237829d0f800181538e1a4fa2494",
    "4790419cc795932ffaeb0152fa5818c8",
    "5ee1c6a8c611b6c3d6aff8043764555f",
    "b668851102c3e0a56c33220161c029ec",
    "0d43575dd39e175ba670fb91b2230442",
    "d32378e66e89f159688cc2239f38a6a4",
    "713146de690026b224dd8bbf0abc0339"
]

TELEGRAM_TOKEN = "8725909088:AAGQMNr-9RVQB7hWmePCLmm0GwaGuzOVy-A"
CHAT_ID = "-1003814625223"
DB_FILE = "probum.db"

SOFT_BOOKIES =["bet365", "betano", "1xbet", "draftkings", "williamhill", "unibet", "888sport", "betfair_ex_eu"]
SHARP_BOOKIE = "pinnacle"
TODAS_CASAS = SOFT_BOOKIES +[SHARP_BOOKIE]

LIGAS =[
    "soccer_epl", "soccer_spain_la_liga", "soccer_italy_serie_a",              
    "soccer_germany_bundesliga", "soccer_france_ligue_one", "soccer_portugal_primeira_liga",
    "soccer_uefa_champs_league", "soccer_uefa_europa_league",
    "soccer_brazil_campeonato", "soccer_brazil_copa_do_brasil", "soccer_brazil_serie_b",
    "soccer_conmebol_copa_libertadores", "soccer_conmebol_copa_sudamericana",
    "basketball_nba", "basketball_euroleague"                     
]

# VARIÁVEIS GLOBAIS DE MEMÓRIA
jogos_enviados = {}
historico_pinnacle = {} # Memória do Smart Money Tracker
chave_odds_atual = 0 
ultima_varredura_normal = datetime.min.replace(tzinfo=ZoneInfo("America/Sao_Paulo"))
api_lock = asyncio.Lock()

oportunidades_globais = []
surebets_globais =[]

# ==========================================
# 2. FUNÇÕES DE SUPORTE ASSÍNCRONAS
# ==========================================
def limpar_memoria_antiga():
    agora = datetime.now()
    
    # Limpa Anti-Spam
    para_remover =[k for k, v in jogos_enviados.items() if agora > v]
    for k in para_remover: del jogos_enviados[k]
        
    # Limpa Histórico de Odds (Para não vazar memória RAM)
    para_remover_hist =[k for k, v in historico_pinnacle.items() if agora > v["expires"]]
    for k in para_remover_hist: del historico_pinnacle[k]

async def fazer_requisicao_odds(session, url, parametros):
    global chave_odds_atual
    for _ in range(len(API_KEYS_ODDS)):
        async with api_lock: chave_teste = API_KEYS_ODDS[chave_odds_atual]
        parametros["apiKey"] = chave_teste
        try:
            async with session.get(url, params=parametros, timeout=15) as resposta:
                if resposta.status == 200:
                    return await resposta.json()
                elif resposta.status in[401, 429]: 
                    async with api_lock: chave_odds_atual = (chave_odds_atual + 1) % len(API_KEYS_ODDS)
                else: return await resposta.json()
        except Exception: pass
    return None

def inicializar_banco():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS operacoes_tipster (
            id_aposta TEXT PRIMARY KEY, esporte TEXT, jogo TEXT, liga TEXT, 
            mercado TEXT, selecao TEXT, odd REAL, prob REAL, ev REAL, stake REAL, 
            status TEXT DEFAULT 'PENDENTE', lucro REAL DEFAULT 0, data_hora TEXT
        )
    """)
    conn.commit()
    conn.close()

async def enviar_telegram_async(session, texto):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": texto, "parse_mode": "HTML", "disable_web_page_preview": True}
    try: await session.post(url, json=payload, timeout=10)
    except: pass

def calcular_prob_justa(outcomes):
    try:
        margem = sum(1 / item["price"] for item in outcomes if item["price"] > 0)
        return {item["name"]: (1 / item["price"]) / margem for item in outcomes if item["price"] > 0}
    except: return {}

def validar_entrada_afiadissima(odd_oferecida, prob_real, ev_real, liga):
    if not (1.40 <= odd_oferecida <= 7.00): return False 
    if ev_real > 0.15: return False 
    
    ev_exigido = 0.0
    if odd_oferecida <= 2.50: ev_exigido = 0.015
    elif odd_oferecida <= 4.00: ev_exigido = 0.040
    else: ev_exigido = 0.070 

    ligas_tier_2 =["serie_b", "turkey", "belgium", "mexico", "uruguay", "sudamericana"]
    if any(l in liga for l in ligas_tier_2):
        ev_exigido += 0.015 
    return ev_real >= ev_exigido

# ==========================================
# 3. NÚCLEO ASYNC (VARREDURA NA VELOCIDADE DA LUZ)
# ==========================================
async def processar_liga_async(session, liga, agora_br, faz_12_horas):
    is_nba = "basketball" in liga
    mercados_alvo = "h2h,spreads,totals" if is_nba else "h2h,btts,totals,draw_no_bet,double_chance,spreads"
    casas_busca = ",".join(TODAS_CASAS)
    parametros = {"regions": "eu,us", "markets": mercados_alvo, "bookmakers": casas_busca}
    url_odds = f"https://api.the-odds-api.com/v4/sports/{liga}/odds/"
    
    data = await fazer_requisicao_odds(session, url_odds, parametros)
    if not data: return

    try:
        for evento in data:
            jogo_id = str(evento['id'])
            if jogo_id in jogos_enviados: continue

            horario_br = datetime.fromisoformat(evento["commence_time"].replace("Z", "+00:00")).astimezone(ZoneInfo("America/Sao_Paulo"))
            minutos_faltando = (horario_br - agora_br).total_seconds() / 60
            if not (15 <= minutos_faltando <= 1440): continue 

            bookmakers = evento.get("bookmakers",[])
            
            # -----------------------------------------------
            # 🚨 SCANNER DE ARBITRAGEM (SUREBETS)
            # -----------------------------------------------
            melhores_odds_h2h = {}
            for b in bookmakers:
                m_h2h = next((m for m in b.get("markets",[]) if m["key"] == "h2h"), None)
                if m_h2h:
                    for out in m_h2h["outcomes"]:
                        if out["name"] not in melhores_odds_h2h or out["price"] > melhores_odds_h2h[out["name"]][0]:
                            melhores_odds_h2h[out["name"]] = (out["price"], b["title"])
            
            if len(melhores_odds_h2h) >= 2:
                soma_prob = sum(1 / v[0] for v in melhores_odds_h2h.values())
                if 0 < soma_prob < 1.0: 
                    lucro_garantido = (1 / soma_prob) - 1
                    if lucro_garantido > 0.005: 
                        surebets_globais.append({
                            "jogo_id": jogo_id, "home_team": evento["home_team"], "away_team": evento["away_team"],
                            "liga": evento['sport_title'], "horario": horario_br, "lucro": lucro_garantido,
                            "odds": melhores_odds_h2h
                        })

            # -----------------------------------------------
            # 📉 RASTREADOR DE SMART MONEY (DROPPING ODDS)
            # -----------------------------------------------
            pinnacle = next((b for b in bookmakers if b["key"] == SHARP_BOOKIE), None)
            if not pinnacle: continue 

            dropping_alerts = {}
            for m in pinnacle.get("markets", []):
                for out in m["outcomes"]:
                    chave_hist = f"{jogo_id}_{m['key']}_{out['name']}_{out.get('point','')}"
                    preco_atual = out["price"]
                    
                    # Checa se a odd derreteu mais de 8% desde a última varredura
                    if chave_hist in historico_pinnacle:
                        preco_antigo = historico_pinnacle[chave_hist]["price"]
                        if (preco_antigo - preco_atual) / preco_antigo >= 0.08:
                            dropping_alerts[chave_hist] = True
                    
                    # Salva a odd atual na memória por 24h
                    historico_pinnacle[chave_hist] = {"price": preco_atual, "expires": agora_br + timedelta(hours=24)}

            # -----------------------------------------------
            # 💎 CÁLCULO DE VALOR (+EV)
            # -----------------------------------------------
            oportunidades_jogo =[]
            for soft_b in bookmakers:
                if soft_b["key"] == SHARP_BOOKIE or soft_b["key"] not in SOFT_BOOKIES: continue
                nome_casa = soft_b["title"]

                for m_key in["h2h", "btts", "draw_no_bet", "double_chance"]:
                    pin_m = next((m for m in pinnacle.get("markets",[]) if m["key"] == m_key), None)
                    soft_m = next((m for m in soft_b.get("markets",[]) if m["key"] == m_key), None)
                    if pin_m and soft_m:
                        probs_justas = calcular_prob_justa(pin_m["outcomes"])
                        for s_outcome in soft_m["outcomes"]:
                            prob_real = probs_justas.get(s_outcome["name"], 0)
                            odd_oferecida = s_outcome["price"]
                            if prob_real > 0:
                                ev_real = (prob_real * odd_oferecida) - 1
                                if validar_entrada_afiadissima(odd_oferecida, prob_real, ev_real, liga):
                                    chave_hist = f"{jogo_id}_{m_key}_{s_outcome['name']}_"
                                    is_dropping = dropping_alerts.get(chave_hist, False)
                                    
                                    traducao = m_key.replace("h2h", "Vencedor (1X2)").replace("btts", "Ambas Marcam").replace("draw_no_bet", "Empate Anula").replace("double_chance", "Dupla Aposta")
                                    selecao = "Sim" if s_outcome["name"]=="Yes" else "Não" if s_outcome["name"]=="No" else s_outcome["name"].replace("/", " ou ")
                                    oportunidades_jogo.append((traducao, selecao, odd_oferecida, prob_real, ev_real, nome_casa, is_dropping))

                for m_key in["totals", "spreads"]:
                    pin_m = next((m for m in pinnacle.get("markets",[]) if m["key"] == m_key), None)
                    soft_m = next((m for m in soft_b.get("markets",[]) if m["key"] == m_key), None)
                    if pin_m and soft_m:
                        for s_outcome in soft_m["outcomes"]:
                            ponto = s_outcome.get("point")
                            pin_match = next((p for p in pin_m["outcomes"] if p["name"] == s_outcome["name"] and p.get("point") == ponto), None)
                            if pin_match and (1.70 <= pin_match["price"] <= 2.30):
                                if m_key == "totals":
                                    par_pinnacle =[p for p in pin_m["outcomes"] if p.get("point") == ponto]
                                    nome_mercado, selecao_nome = "Gols/Pontos", f"{s_outcome['name']} {ponto}"
                                else:
                                    par_pinnacle =[p for p in pin_m["outcomes"] if p.get("point") in (ponto, -ponto)]
                                    nome_mercado, selecao_nome = "Handicap Asiático", f"{s_outcome['name']} ({ponto})"
                                try:
                                    prob_real = (1 / pin_match["price"]) / sum(1 / i["price"] for i in par_pinnacle if i["price"] > 0)
                                    odd_oferecida = s_outcome["price"]
                                    if prob_real > 0:
                                        ev_real = (prob_real * odd_oferecida) - 1
                                        if validar_entrada_afiadissima(odd_oferecida, prob_real, ev_real, liga):
                                            chave_hist = f"{jogo_id}_{m_key}_{s_outcome['name']}_{ponto}"
                                            is_dropping = dropping_alerts.get(chave_hist, False)
                                            oportunidades_jogo.append((nome_mercado, selecao_nome, odd_oferecida, prob_real, ev_real, nome_casa, is_dropping))
                                except: pass

            if oportunidades_jogo:
                melhor_op = max(oportunidades_jogo, key=lambda x: x[4]) 
                is_rara = (melhor_op[2] >= 4.01 and melhor_op[4] >= 0.07) or (melhor_op[4] >= 0.035 and melhor_op[3] >= 0.50) or melhor_op[6]
                
                if faz_12_horas or is_rara:
                    oportunidades_globais.append({
                        "jogo_id": jogo_id, "evento": evento, "home_team": evento["home_team"], "away_team": evento["away_team"],
                        "horario_br": horario_br, "minutos_faltando": minutos_faltando, "mercado_nome": melhor_op[0],
                        "selecao_nome": melhor_op[1], "odd_bookie": melhor_op[2], "prob_justa": melhor_op[3], 
                        "ev_real": melhor_op[4], "nome_bookie": melhor_op[5], "is_dropping": melhor_op[6], 
                        "is_nba": is_nba, "esporte": liga
                    })
    except Exception as e: pass

# ==========================================
# 4. EXECUTOR ASYNC & ENVIO TELEGRAM
# ==========================================
async def gerenciar_varreduras_e_enviar():
    global ultima_varredura_normal
    agora_br = datetime.now(ZoneInfo("America/Sao_Paulo"))
    faz_12_horas = (agora_br - ultima_varredura_normal).total_seconds() >= 43200
    
    if faz_12_horas: print(f"\n🔄[TURNO DE 12H - {agora_br.strftime('%H:%M:%S')}] Motor Async LIGADO! Varrando o mundo inteiro...")
    else: print(f"\n🕵️‍♂️[ESPIÃO - {agora_br.strftime('%H:%M:%S')}] Buscando Surebets e Dropping Odds...")
        
    limpar_memoria_antiga()
    oportunidades_globais.clear()
    surebets_globais.clear()
    
    # 🔥 MÁGICA ASYNC: Faz todas as requisições ao mesmo tempo!
    async with aiohttp.ClientSession() as session:
        tasks =[processar_liga_async(session, liga, agora_br, faz_12_horas) for liga in LIGAS]
        await asyncio.gather(*tasks)

        # --- DISPARAR SUREBETS ---
        if surebets_globais:
            print(f"🚨 ACHAMOS {len(surebets_globais)} SUREBETS (ARBITRAGEM)!")
            for arb in surebets_globais:
                texto_arb = (
                    "🚨🚨 <b>SUREBET DETECTADA (RISCO ZERO)</b> 🚨🚨\n"
                    "<i>Apostas cruzadas cobrindo 100% das opções garantindo lucro!</i>\n\n"
                    f"🏆 <b>Liga:</b> {arb['liga']}\n"
                    f"⏰ <b>Horário:</b> {arb['horario'].strftime('%H:%M')}\n"
                    f"⚽ <b>Jogo:</b> {arb['home_team']} x {arb['away_team']}\n\n"
                    f"<b>COMO MONTAR A OPERAÇÃO:</b>\n"
                )
                for selecao, dados in arb["odds"].items():
                    texto_arb += f"👉 <b>{selecao}:</b> Odd {dados[0]:.2f} na 🏛️ {dados[1]}\n"
                
                texto_arb += f"\n💰 <b>LUCRO 100% GARANTIDO:</b> +{arb['lucro']*100:.2f}%\n"
                await enviar_telegram_async(session, texto_arb)
                jogos_enviados[arb["jogo_id"]] = datetime.now() + timedelta(hours=24)

        # --- DISPARAR OPORTUNIDADES +EV ---
        if oportunidades_globais:
            oportunidades_globais.sort(key=lambda x: x["ev_real"], reverse=True)
            top_snipers = oportunidades_globais[:5] if faz_12_horas else oportunidades_globais[:3]
            
            for op in top_snipers:
                ev_real, prob_justa, odd_bookie = op["ev_real"], op["prob_justa"], op["odd_bookie"]
                
                if op["is_dropping"]:
                    cabecalho = "📉 <b>SMART MONEY (DERRETIMENTO DE ODD)</b> 📉\n<i>O dinheiro Asiático entrou pesado e a Pinnacle derreteu. A Bet recreativa dormiu!</i>"
                    kelly_pct = 2.0
                elif odd_bookie >= 4.01:
                    cabecalho = "🦓 <b>ZEBRA DE VALOR (ANÁLISE SUPERIOR)</b> 🦓\n<i>Falha brutal da casa identificada. Lucro de alta variância!</i>"
                    kelly_pct = 0.5 
                elif ev_real >= 0.035 and prob_justa >= 0.50:
                    cabecalho = "🎯🏆 <b>OPORTUNIDADE ÚNICA (ENTRADA PESADA)</b> 🏆🎯\n<i>Padrão Diamante: Altíssima assertividade + Matemática perfeita.</i>"
                    kelly_pct = 3.0 
                else:
                    cabecalho = "💎 <b>APOSTA INSTITUCIONAL (PADRÃO)</b> 💎"
                    b_kelly, q_kelly = odd_bookie - 1, 1 - prob_justa
                    try: kelly_pct = max(1.0, min(((prob_justa - (q_kelly / b_kelly)) * 0.25) * 100, 2.0))
                    except: kelly_pct = 1.0

                horas_f, min_f = int(op["minutos_faltando"] // 60), int(op["minutos_faltando"] % 60)
                tempo_str = f"{horas_f}h {min_f}min" if horas_f > 0 else f"{min_f} min"
                emoji = "🏀" if op["is_nba"] else "⚽"
                
                texto_msg = (
                    f"{cabecalho}\n\n"
                    f"🏆 <b>Liga:</b> {op['evento']['sport_title']}\n"
                    f"⏰ <b>Horário:</b> {op['horario_br'].strftime('%H:%M')} (Faltam {tempo_str})\n"
                    f"{emoji} <b>Jogo:</b> {op['home_team']} x {op['away_team']}\n\n"
                    f"🎯 <b>Mercado:</b> {op['mercado_nome']}\n"
                    f"👉 <b>Entrada:</b> {op['selecao_nome']}\n"
                    f"🏛️ <b>Casa de Aposta:</b> {op['nome_bookie']}\n"
                    f"📈 <b>Odd Atual:</b> {odd_bookie:.2f}\n\n"
                    f"💰 <b>Gestão Sugerida:</b> {kelly_pct:.1f}% da Banca\n"
                    f"📊 <b>Vantagem Matemática (+EV):</b> +{ev_real*100:.2f}%\n"
                )
                await enviar_telegram_async(session, texto_msg)
                jogos_enviados[op["jogo_id"]] = datetime.now() + timedelta(hours=24)

            # --- MÚLTIPLA BLINDADA DE 12 HORAS ---
            if faz_12_horas:
                jogos_seguros =[op for op in top_snipers if op["prob_justa"] >= 0.55 and op["odd_bookie"] <= 1.80]
                if len(jogos_seguros) >= 2:
                    m1, m2 = jogos_seguros[0], jogos_seguros[1]
                    odd_dupla = m1["odd_bookie"] * m2["odd_bookie"]
                    texto_multipla = (
                        "🔥🧩 <b>COMBO +EV SINDICATO (MÚLTIPLA)</b> 🧩🔥\n"
                        "<i>Juntamos as 2 análises de maior Win-Rate do momento!</i>\n\n"
                        f"1️⃣ <b>{m1['home_team']} x {m1['away_team']}</b>\n👉 {m1['mercado_nome']} - <b>{m1['selecao_nome']}</b> (@{m1['odd_bookie']:.2f})\n\n"
                        f"2️⃣ <b>{m2['home_team']} x {m2['away_team']}</b>\n👉 {m2['mercado_nome']} - <b>{m2['selecao_nome']}</b> (@{m2['odd_bookie']:.2f})\n\n"
                        f"🚀 <b>ODD FINAL DA DUPLA:</b> {odd_dupla:.2f}\n💰 <b>Stake:</b> 0.5% a 1.0% da Banca"
                    )
                    await enviar_telegram_async(session, texto_multipla)
                
                ultima_varredura_normal = agora_br

async def loop_infinito():
    while True:
        await gerenciar_varreduras_e_enviar()
        print("\n⏳ Bot dormindo por 2 horas (Rastreador Smart Money Ativo)...")
        await asyncio.sleep(7200)

if __name__ == "__main__":
    inicializar_banco()
    print("🤖 Bot Sindicato ASIÁTICO v10.0 (ASYNC ENGINE + SMART MONEY) INICIADO!")
    print("⚡ Motor Assíncrono Ativo: Analisando o mundo inteiro em Segundos.")
    print("📉 Smart Money Tracker Ativo: Vigiando derretimentos de odd > 8%.")
    print("🚨 Scanner de ARBITRAGEM (Surebets) de Risco Zero Operacional.")
    
    # Inicia o Loop Assíncrono
    asyncio.run(loop_infinito())
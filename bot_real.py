import asyncio
import aiohttp
import time
import json
import sqlite3
import unicodedata
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# ==========================================
# 1. CONFIGURAÇÕES E CHAVES (9 Chaves = 4.500 reqs/mês)
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

jogos_enviados = {}
historico_pinnacle = {} 
memoria_ia = {} 
chave_odds_atual = 0 
api_lock = asyncio.Lock()

oportunidades_globais =[]

# ==========================================
# 2. FUNÇÕES DE BANCO E TELEGRAM
# ==========================================
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

def salvar_aposta_banco(op, stake):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        id_aposta = f"{op['jogo_id']}_{op['mercado_nome'][:4]}_{op['selecao_nome'][:4]}".replace(" ", "")
        data_atual = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime('%d/%m/%Y')
        cursor.execute("""
            INSERT OR IGNORE INTO operacoes_tipster 
            (id_aposta, esporte, jogo, liga, mercado, selecao, odd, prob, ev, stake, status, lucro, data_hora)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDENTE', 0, ?)
        """, (
            id_aposta, op['esporte'], f"{op['home_team']} x {op['away_team']}",
            op['evento']['sport_title'], op['mercado_nome'], op['selecao_nome'],
            op['odd_bookie'], op['prob_justa'], op['ev_real'], stake, data_atual
        ))
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
                elif resposta.status in[401, 429]: 
                    async with api_lock: chave_odds_atual = (chave_odds_atual + 1) % len(API_KEYS_ODDS)
                else: return await resposta.json()
        except Exception: pass
    return None

# ==========================================
# 3. VALIDAÇÕES E INTELIGÊNCIA ARTIFICIAL
# ==========================================
def normalizar_nome(nome):
    if not isinstance(nome, str): return str(nome)
    nome = ''.join(c for c in unicodedata.normalize('NFD', nome) if unicodedata.category(c) != 'Mn').lower().strip()
    sufixos =[" fc", " cf", " cd", " sc", " cp", " fk", " nk", " u21", " u20", " u19"]
    for suf in sufixos:
        if nome.endswith(suf):
            nome = nome[:-len(suf)].strip()
            
    if "manchester city" in nome: return "man city"
    if "manchester united" in nome: return "man utd"
    
    mapa = {
        "bayern munich": "bayern", "bayern munchen": "bayern",
        "paris saint germain": "psg", "paris sg": "psg",
        "internazionale": "inter", "inter milan": "inter", "ac milan": "milan"
    }
    return mapa.get(nome, nome)

def calcular_prob_justa(outcomes):
    try:
        margem = sum(1 / item["price"] for item in outcomes if item["price"] > 0)
        return {normalizar_nome(item["name"]): (1 / item["price"]) / margem for item in outcomes if item["price"] > 0}
    except: return {}

def treinar_inteligencia_artificial():
    global memoria_ia
    memoria_ia.clear()
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT liga, mercado, lucro, stake FROM operacoes_tipster WHERE status != 'PENDENTE'")
        historico = cursor.fetchall()
        conn.close()

        dados_agrupados = {}
        for liga, mercado, lucro, stake in historico:
            chave = f"{liga}_{mercado}"
            if chave not in dados_agrupados:
                dados_agrupados[chave] = {"apostas": 0, "lucro_total": 0.0, "stake_total": 0.0}
            dados_agrupados[chave]["apostas"] += 1
            dados_agrupados[chave]["lucro_total"] += lucro
            dados_agrupados[chave]["stake_total"] += stake

        for chave, dados in dados_agrupados.items():
            # MELHORIA: Aumentado de 5 para 20 apostas mínimas para evitar ruidos de curto prazo (variância)
            if dados["apostas"] >= 20: 
                roi = (dados["lucro_total"] / dados["stake_total"]) * 100
                memoria_ia[chave] = roi
    except: pass

def validar_com_ia(odd_oferecida, prob_real, ev_real, liga, liga_titulo, mercado_nome):
    if not (1.30 <= odd_oferecida <= 15.00): return False 
    if ev_real > 0.15: return False 
    
    if odd_oferecida <= 1.70: ev_exigido = 0.010 
    elif odd_oferecida <= 3.49: ev_exigido = 0.020 
    else: ev_exigido = 0.035 

    ligas_tier_2 =["serie_b", "turkey", "belgium", "mexico", "uruguay", "sudamericana"]
    if any(l in liga for l in ligas_tier_2): ev_exigido += 0.010 

    chave_ia = f"{liga_titulo}_{mercado_nome}"
    if chave_ia in memoria_ia:
        roi_historico = memoria_ia[chave_ia]
        if roi_historico <= -25.0: return False
        elif roi_historico < 0: ev_exigido += 0.010 
        elif roi_historico >= 15.0: ev_exigido -= 0.005 

    return ev_real >= ev_exigido

# ==========================================
# 4. MOTOR DE BUSCA (VARREDURA)
# ==========================================
async def processar_liga_async(session, liga, agora_br):
    is_nba = "basketball" in liga
    # MELHORIA: Adicionado mercado de 'totals' (Gols Over/Under) no futebol
    mercados_alvo = "h2h,spreads,totals" if is_nba else "h2h,btts,spreads,totals"
    casas_busca = ",".join(TODAS_CASAS)
    
    parametros = {"regions": "eu", "markets": mercados_alvo, "bookmakers": casas_busca}
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
            pinnacle = next((b for b in bookmakers if b["key"] == SHARP_BOOKIE), None)
            if not pinnacle: continue 

            dropping_alerts = {}
            for m in pinnacle.get("markets", []):
                for out in m["outcomes"]:
                    chave_hist = f"{jogo_id}_{m['key']}_{out['name']}_{out.get('point','')}"
                    preco_atual = out["price"]
                    if chave_hist in historico_pinnacle:
                        preco_antigo = historico_pinnacle[chave_hist]["price"]
                        # MELHORIA: Como o ciclo agora é a cada 3h, uma queda de 6% representa um STEAM MOVE forte
                        if (preco_antigo - preco_atual) / preco_antigo >= 0.06:
                            dropping_alerts[chave_hist] = True
                    historico_pinnacle[chave_hist] = {"price": preco_atual, "expires": agora_br + timedelta(hours=24)}

            oportunidades_jogo =[]
            for soft_b in bookmakers:
                if soft_b["key"] == SHARP_BOOKIE or soft_b["key"] not in SOFT_BOOKIES: continue
                nome_casa = soft_b["title"]

                # 1. 1X2 e AMBAS MARCAM
                for m_key in ["h2h", "btts"]:
                    pin_m = next((m for m in pinnacle.get("markets", []) if m["key"] == m_key), None)
                    soft_m = next((m for m in soft_b.get("markets",[]) if m["key"] == m_key), None)
                    if pin_m and soft_m:
                        probs_justas = calcular_prob_justa(pin_m["outcomes"])
                        for s_outcome in soft_m["outcomes"]:
                            nome_norm = normalizar_nome(s_outcome["name"])
                            prob_real = probs_justas.get(nome_norm, 0)
                            odd_oferecida = s_outcome["price"]
                            if prob_real > 0:
                                ev_real = (prob_real * odd_oferecida) - 1
                                traducao = m_key.replace("h2h", "Vencedor (1X2)").replace("btts", "Ambas Marcam")
                                if validar_com_ia(odd_oferecida, prob_real, ev_real, liga, evento['sport_title'], traducao):
                                    chave_hist = f"{jogo_id}_{m_key}_{s_outcome['name']}_"
                                    is_dropping = dropping_alerts.get(chave_hist, False)
                                    selecao = "Sim" if s_outcome["name"]=="Yes" else "Não" if s_outcome["name"]=="No" else s_outcome["name"].replace("/", " ou ")
                                    oportunidades_jogo.append((traducao, selecao, odd_oferecida, prob_real, ev_real, nome_casa, is_dropping))

                # 2. HANDICAPS (SPREADS) E GOLS (TOTALS)
                for m_key in ["spreads", "totals"]:
                    pin_m = next((m for m in pinnacle.get("markets", []) if m["key"] == m_key), None)
                    soft_m = next((m for m in soft_b.get("markets", []) if m["key"] == m_key), None)
                    if pin_m and soft_m:
                        for s_outcome in soft_m["outcomes"]:
                            ponto = s_outcome.get("point")
                            nome_s_norm = normalizar_nome(s_outcome["name"])
                            
                            pin_match = next((p for p in pin_m["outcomes"] if normalizar_nome(p["name"]) == nome_s_norm and p.get("point") == ponto), None)
                            if pin_match and (1.50 <= pin_match["price"] <= 2.50):
                                par_pinnacle =[p for p in pin_m["outcomes"] if p.get("point") in (ponto, -ponto) or (m_key == "totals" and p.get("point") == ponto)]
                                
                                # Define nome do mercado amigável
                                if m_key == "spreads":
                                    nome_mercado = "Handicap Asiático" if not is_nba else "Handicap (Spread)"
                                    selecao_nome = f"{s_outcome['name']} ({ponto})"
                                else:
                                    nome_mercado = "Gols (Mais/Menos)" if not is_nba else "Pontos Totais"
                                    selecao_nome = f"{s_outcome['name']} {ponto}" # Ex: Over 2.5

                                try:
                                    prob_real = (1 / pin_match["price"]) / sum(1 / i["price"] for i in par_pinnacle if i["price"] > 0)
                                    odd_oferecida = s_outcome["price"]
                                    if prob_real > 0:
                                        ev_real = (prob_real * odd_oferecida) - 1
                                        if validar_com_ia(odd_oferecida, prob_real, ev_real, liga, evento['sport_title'], nome_mercado):
                                            chave_hist = f"{jogo_id}_{m_key}_{s_outcome['name']}_{ponto}"
                                            is_dropping = dropping_alerts.get(chave_hist, False)
                                            oportunidades_jogo.append((nome_mercado, selecao_nome, odd_oferecida, prob_real, ev_real, nome_casa, is_dropping))
                                except: pass

            if oportunidades_jogo:
                melhor_op = max(oportunidades_jogo, key=lambda x: x[4]) 
                
                oportunidades_globais.append({
                    "jogo_id": jogo_id, "evento": evento, "home_team": evento["home_team"], "away_team": evento["away_team"],
                    "horario_br": horario_br, "minutos_faltando": minutos_faltando, "mercado_nome": melhor_op[0],
                    "selecao_nome": melhor_op[1], "odd_bookie": melhor_op[2], "prob_justa": melhor_op[3], 
                    "ev_real": melhor_op[4], "nome_bookie": melhor_op[5], "is_dropping": melhor_op[6], 
                    "is_nba": is_nba, "esporte": liga
                })
    except Exception as e: pass

# ==========================================
# 5. GERENCIADOR DE ENVIO (TOP 5 E MÚLTIPLAS)
# ==========================================
async def gerenciar_varreduras_e_enviar():
    global jogos_enviados, historico_pinnacle
    agora_br = datetime.now(ZoneInfo("America/Sao_Paulo"))
    
    treinar_inteligencia_artificial()
    print(f"\n🔄[VARREDURA GERAL - {agora_br.strftime('%H:%M:%S')}] Buscando e filtrando os melhores jogos...")
        
    jogos_enviados = {k: v for k, v in jogos_enviados.items() if agora_br <= v}
    historico_pinnacle = {k: v for k, v in historico_pinnacle.items() if agora_br <= v["expires"]}
    oportunidades_globais.clear()
    
    async with aiohttp.ClientSession() as session:
        tasks =[processar_liga_async(session, liga, agora_br) for liga in LIGAS]
        await asyncio.gather(*tasks)

        if oportunidades_globais:
            
            candidatas_multipla = [op for op in oportunidades_globais if op["odd_bookie"] <= 1.70 and op["prob_justa"] >= 0.60]
            jogos_multipla_ids =[]
            
            if len(candidatas_multipla) >= 2:
                candidatas_multipla.sort(key=lambda x: x["prob_justa"], reverse=True)
                jogos_multipla = candidatas_multipla[:3]
                jogos_multipla_ids = [op["jogo_id"] for op in jogos_multipla]
                
                odd_total = 1.0
                texto_multipla = "🔥 <b>OPORTUNIDADE IMPERDÍVEL: MÚLTIPLA PRONTA</b> 🔥\n\n"
                
                for i, op in enumerate(jogos_multipla, 1):
                    odd_total *= op["odd_bookie"]
                    texto_multipla += f"⚽ <b>Jogo {i}: {op['home_team']} x {op['away_team']}</b>\n"
                    texto_multipla += f"👉 <b>Entrada:</b> {op['mercado_nome']} - {op['selecao_nome']}\n"
                    texto_multipla += f"📈 <b>Odd:</b> {op['odd_bookie']:.2f} | ⏰ {op['horario_br'].strftime('%H:%M')}\n\n"

                texto_multipla += f"💵 <b>ODD TOTAL DO BILHETE:</b> {odd_total:.2f}\n"
                texto_multipla += f"💰 <b>Gestão Sugerida:</b> 0.5% a 1.0% da Banca\n"
                texto_multipla += f"✅ <i>Cruze essas entradas na sua casa de aposta!</i>"
                
                await enviar_telegram_async(session, texto_multipla)
                
                for op in jogos_multipla:
                    jogos_enviados[op["jogo_id"]] = datetime.now() + timedelta(hours=24)
                    salvar_aposta_banco(op, 0.5)

            singles = [op for op in oportunidades_globais if op["jogo_id"] not in jogos_multipla_ids]
            singles.sort(key=lambda x: x["ev_real"], reverse=True)
            top_singles = singles[:5]

            top_singles.sort(key=lambda x: x["horario_br"])
            
            for op in top_singles:
                ev_real, prob_justa, odd_bookie = op["ev_real"], op["prob_justa"], op["odd_bookie"]
                chave_ia = f"{op['evento']['sport_title']}_{op['mercado_nome']}"
                roi_atual = memoria_ia.get(chave_ia, 0)
                tag_ia = f"\n🤖 <b>Selo IA:</b> Mercado com {roi_atual:.1f}% de ROI histórico." if roi_atual > 0 else ""

                if op["is_dropping"]:
                    cabecalho = "📉 <b>SMART MONEY (DERRETIMENTO DE ODD)</b>"
                    confianca = "🔥 ELITE"
                    kelly_pct = 2.0
                elif odd_bookie <= 1.70:
                    cabecalho = "🎯 <b>ALTA PROBABILIDADE (ENTRADA SEGURA)</b>"
                    confianca = "🔥 ELITE"
                    kelly_pct = 2.0 
                elif odd_bookie >= 3.50:
                    cabecalho = "🦓 <b>ZEBRA DE VALOR (ALTO RETORNO)</b>"
                    confianca = "👍 BOA"
                    kelly_pct = 0.5 
                else:
                    cabecalho = "💎 <b>SNIPER INSTITUCIONAL (MODERADA)</b>"
                    confianca = "💪 FORTE"
                    try: kelly_pct = max(1.0, min(((prob_justa - ((1-prob_justa)/(odd_bookie-1))) * 0.25) * 100, 1.5))
                    except: kelly_pct = 1.0

                horas_f, min_f = int(op["minutos_faltando"] // 60), int(op["minutos_faltando"] % 60)
                tempo_str = f"{horas_f}h {min_f}min" if horas_f > 0 else f"{min_f} min"
                
                texto_msg = (
                    f"{cabecalho}\n\n"
                    f"🏆 <b>Liga:</b> {op['evento']['sport_title']}\n"
                    f"⏰ <b>Horário:</b> {op['horario_br'].strftime('%H:%M')} (Faltam {tempo_str})\n"
                    f"⚽ <b>Jogo:</b> {op['home_team']} x {op['away_team']}\n\n"
                    f"🎯 <b>Mercado:</b> {op['mercado_nome']}\n"
                    f"👉 <b>Entrada:</b> {op['selecao_nome']}\n"
                    f"🏛️ <b>Casa de Aposta:</b> {op['nome_bookie']}\n"
                    f"📈 <b>Odd Atual:</b> {odd_bookie:.2f}\n\n"
                    f"💰 <b>Gestão/Stake:</b> {kelly_pct:.1f}% Unidades\n"
                    f"🛡️ <b>Confiança:</b> {confianca}\n"
                    f"📊 <b>Vantagem Matemática (+EV):</b> +{ev_real*100:.2f}%\n"
                    f"✅ <b>Probabilidade Real:</b> {prob_justa*100:.1f}%{tag_ia}\n"
                )
                await enviar_telegram_async(session, texto_msg)
                jogos_enviados[op["jogo_id"]] = datetime.now() + timedelta(hours=24)
                salvar_aposta_banco(op, kelly_pct)

async def loop_infinito():
    while True:
        await gerenciar_varreduras_e_enviar()
        # MELHORIA: Tempo de sleep ajustado para 3 HORAS (10800 segundos).
        # Você gasta apenas 120 requisições por dia (sobram 30 requests de margem de segurança)
        # e pega derretimento de odds muito mais rápido que a configuração de 5 horas.
        print("\n⏳ Bot dormindo por 3 horas (Varredura dinâmica ativada)...")
        await asyncio.sleep(10800)

if __name__ == "__main__":
    inicializar_banco()
    print("🤖 Bot Sindicato ASIÁTICO v10.5 INICIADO!")
    print("🎯 MODO: Dinâmico (Ciclo 3h) | Busca em Gols e Handicaps | IA Blindada contra ruídos!")
    asyncio.run(loop_infinito())
import asyncio
import aiohttp
import time
import json
import sqlite3
import unicodedata
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

SOFT_BOOKIES =["bet365","betano","1xbet","draftkings","williamhill","unibet","888sport","betfair_ex_eu"]
SHARP_BOOKIE = "pinnacle"
TODAS_CASAS = SOFT_BOOKIES +[SHARP_BOOKIE]
SCAN_INTERVAL = 18000 # 5 Horas (Garante 30 dias na API)

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
surebets_globais =[]

# ==========================================
# 2. FUNÇÕES DE SUPORTE E BANCO DE DADOS
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

def carregar_memoria_banco():
    global jogos_enviados
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT id_aposta FROM operacoes_tipster WHERE status = 'PENDENTE'")
        apostas = cursor.fetchall()
        for (id_aposta,) in apostas:
            jogo_id = id_aposta.split("_")[0]
            jogos_enviados[jogo_id] = datetime.now(ZoneInfo("America/Sao_Paulo")) + timedelta(hours=24)
        conn.close()
        print(f"🧠 Memória restaurada: {len(jogos_enviados)} jogos pendentes.")
    except: pass

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
                if resposta.status == 200: 
                    return await resposta.json()
                elif resposta.status in[401, 429]: 
                    async with api_lock: chave_odds_atual = (chave_odds_atual + 1) % len(API_KEYS_ODDS)
                else: return await resposta.json()
        except: pass
    return None

def normalizar_nome(nome):
    if not isinstance(nome, str): return str(nome)
    nome = ''.join(c for c in unicodedata.normalize('NFD', nome) if unicodedata.category(c) != 'Mn').lower().strip()
    sufixos =[" fc", " cf", " cd", " sc", " cp", " fk", " nk"]
    for s in sufixos:
        if nome.endswith(s): nome = nome[:-len(s)].strip()
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

# ==========================================
# 3. MÓDULO DE INTELIGÊNCIA ARTIFICIAL E FILTROS
# ==========================================
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
            if dados["apostas"] >= 10: 
                roi = (dados["lucro_total"] / dados["stake_total"]) * 100
                memoria_ia[chave] = roi
    except: pass

def validar_com_ia(odd, prob, ev, liga, liga_titulo, mercado_nome, esporte):
    """ 🔥 SEGREDO DO SINDICATO: FILTROS SEPARADOS POR ESPORTE 🔥 """
    if not (1.30 <= odd <= 15.00): return False 
    if ev > 0.18: return False 
    
    ev_exigido = 0.0

    if esporte == "basketball":
        # Basquete é um mercado de linhas muito precisas. EV>1.5% já é excelente.
        if odd <= 2.10: ev_exigido = 0.015 
        else: ev_exigido = 0.025
    else:
        # Futebol tem muita variação. Filtro dinâmico por Odd.
        if odd <= 1.70: ev_exigido = 0.010 
        elif odd <= 3.50: ev_exigido = 0.020 
        else: ev_exigido = 0.035 

    # Penalidade para Ligas Várzeas (Futebol)
    if esporte == "soccer":
        ligas_tier_2 =["serie_b", "turkey", "belgium", "mexico", "uruguay", "sudamericana"]
        if any(l in liga for l in ligas_tier_2): ev_exigido += 0.010 

    # Validação com a Memória de Acertos (IA)
    chave_ia = f"{liga_titulo}_{mercado_nome}"
    if chave_ia in memoria_ia:
        roi_historico = memoria_ia[chave_ia]
        if roi_historico <= -25.0: return False
        elif roi_historico < 0: ev_exigido += 0.010 
        elif roi_historico >= 15.0: ev_exigido -= 0.005 

    return ev >= ev_exigido

# ==========================================
# 4. NÚCLEO ASYNC DE VARREDURA
# ==========================================
async def processar_liga_async(session, liga, agora_br):
    esporte_str = "basketball" if "basketball" in liga else "soccer"
    mercados_alvo = "h2h,spreads,totals" if esporte_str == "basketball" else "h2h,btts,spreads,totals"
    casas_busca = ",".join(TODAS_CASAS)
    
    parametros = {"regions": "eu", "markets": mercados_alvo, "bookmakers": casas_busca}
    url_odds = f"https://api.the-odds-api.com/v4/sports/{liga}/odds/"
    
    data = await fazer_requisicao_odds(session, url_odds, parametros)
    if not isinstance(data, list): return

    try:
        for evento in data:
            jogo_id = str(evento['id'])
            if jogo_id in jogos_enviados: continue

            horario_br = datetime.fromisoformat(evento["commence_time"].replace("Z", "+00:00")).astimezone(ZoneInfo("America/Sao_Paulo"))
            minutos_faltando = (horario_br - agora_br).total_seconds() / 60
            if not (15 <= minutos_faltando <= 1440): continue 

            bookmakers = evento.get("bookmakers",[])
            
            # SUREBETS
            melhores_odds_h2h = {}
            for b in bookmakers:
                m_h2h = next((m for m in b.get("markets",[]) if m["key"] == "h2h"), None)
                if m_h2h:
                    for out in m_h2h["outcomes"]:
                        n_out = normalizar_nome(out["name"])
                        if n_out not in melhores_odds_h2h or out["price"] > melhores_odds_h2h[n_out][0]:
                            melhores_odds_h2h[n_out] = (out["price"], b["title"], out["name"])
            if len(melhores_odds_h2h) >= 2:
                soma_prob = sum(1 / v[0] for v in melhores_odds_h2h.values())
                if 0 < soma_prob < 1.0: 
                    lucro_garantido = (1 / soma_prob) - 1
                    if lucro_garantido > 0.005: 
                        surebets_globais.append({
                            "jogo_id": jogo_id, "home_team": evento["home_team"], "away_team": evento["away_team"],
                            "liga": evento['sport_title'], "horario": horario_br, "lucro": lucro_garantido,
                            "odds": melhores_odds_h2h, "esporte": esporte_str
                        })

            pinnacle = next((b for b in bookmakers if b["key"] == SHARP_BOOKIE), None)
            if not pinnacle: continue 

            # SMART MONEY (Quedas)
            dropping_alerts = {}
            for m in pinnacle.get("markets",[]):
                for out in m["outcomes"]:
                    n_out = normalizar_nome(out["name"])
                    chave_hist = f"{jogo_id}_{m['key']}_{n_out}_{out.get('point','')}"
                    preco_atual = out["price"]
                    if chave_hist in historico_pinnacle:
                        preco_antigo = historico_pinnacle[chave_hist]["price"]
                        if (preco_antigo - preco_atual) / preco_antigo >= 0.06:
                            dropping_alerts[chave_hist] = True
                    historico_pinnacle[chave_hist] = {"price": preco_atual, "expires": agora_br + timedelta(hours=24)}

            oportunidades_jogo =[]
            for soft_b in bookmakers:
                if soft_b["key"] == SHARP_BOOKIE or soft_b["key"] not in SOFT_BOOKIES: continue
                nome_casa = soft_b["title"]

                # MERCADOS 1X2 E BTTS
                for m_key in["h2h", "btts"]:
                    pin_m = next((m for m in pinnacle.get("markets",[]) if m["key"] == m_key), None)
                    soft_m = next((m for m in soft_b.get("markets",[]) if m["key"] == m_key), None)
                    if pin_m and soft_m:
                        probs_justas = calcular_prob_justa(pin_m["outcomes"])
                        for s_outcome in soft_m["outcomes"]:
                            n_out = normalizar_nome(s_outcome["name"])
                            prob_real = probs_justas.get(n_out, 0)
                            odd_oferecida = s_outcome["price"]
                            if prob_real > 0:
                                ev_real = (prob_real * odd_oferecida) - 1
                                traducao = "Vencedor (1X2)" if m_key == "h2h" else "Ambas Marcam"
                                
                                # 🔥 VALIDA COM A REGRA ESPECÍFICA DO ESPORTE
                                if validar_com_ia(odd_oferecida, prob_real, ev_real, liga, evento['sport_title'], traducao, esporte_str):
                                    chave_hist = f"{jogo_id}_{m_key}_{n_out}_"
                                    is_dropping = dropping_alerts.get(chave_hist, False)
                                    selecao = "Sim" if s_outcome["name"]=="Yes" else "Não" if s_outcome["name"]=="No" else s_outcome["name"].replace("/", " ou ")
                                    oportunidades_jogo.append((traducao, selecao, odd_oferecida, prob_real, ev_real, nome_casa, is_dropping))

                # MERCADOS SPREAD E TOTAIS
                for m_key in["spreads", "totals"]:
                    pin_m = next((m for m in pinnacle.get("markets",[]) if m["key"] == m_key), None)
                    soft_m = next((m for m in soft_b.get("markets",[]) if m["key"] == m_key), None)
                    if pin_m and soft_m:
                        for s_outcome in soft_m["outcomes"]:
                            ponto = s_outcome.get("point")
                            nome_s = s_outcome["name"]
                            n_out = normalizar_nome(nome_s)
                            
                            pin_match = next((p for p in pin_m["outcomes"] if normalizar_nome(p["name"]) == n_out and p.get("point") == ponto), None)
                            if pin_match and (1.50 <= pin_match["price"] <= 2.50):
                                par_pinnacle =[p for p in pin_m["outcomes"] if p.get("point") in (ponto, -ponto) or (m_key == "totals" and p.get("point") == ponto)]
                                
                                if m_key == "spreads":
                                    nome_mercado = "Handicap Asiático" if esporte_str == "soccer" else "Handicap (Spread)"
                                    selecao_nome = f"{nome_s} ({ponto})"
                                else:
                                    nome_mercado = "Gols Totais" if esporte_str == "soccer" else "Pontos Totais"
                                    selecao_nome = f"{nome_s} {ponto}"

                                try:
                                    prob_real = (1 / pin_match["price"]) / sum(1 / i["price"] for i in par_pinnacle if i["price"] > 0)
                                    odd_oferecida = s_outcome["price"]
                                    if prob_real > 0:
                                        ev_real = (prob_real * odd_oferecida) - 1
                                        # 🔥 VALIDA COM A REGRA ESPECÍFICA DO ESPORTE
                                        if validar_com_ia(odd_oferecida, prob_real, ev_real, liga, evento['sport_title'], nome_mercado, esporte_str):
                                            chave_hist = f"{jogo_id}_{m_key}_{n_out}_{ponto}"
                                            is_dropping = dropping_alerts.get(chave_hist, False)
                                            oportunidades_jogo.append((nome_mercado, selecao_nome, odd_oferecida, prob_real, ev_real, nome_casa, is_dropping))
                                except: pass

            if oportunidades_jogo:
                # Se achou várias no mesmo jogo, pega a de MAIOR PROBABILIDADE para garantir Green
                melhor_op = max(oportunidades_jogo, key=lambda x: x[3]) 
                
                oportunidades_globais.append({
                    "jogo_id": jogo_id, "evento": evento, "home_team": evento["home_team"], "away_team": evento["away_team"],
                    "horario_br": horario_br, "minutos_faltando": minutos_faltando, "mercado_nome": melhor_op[0],
                    "selecao_nome": melhor_op[1], "odd_bookie": melhor_op[2], "prob_justa": melhor_op[3], 
                    "ev_real": melhor_op[4], "nome_bookie": melhor_op[5], "is_dropping": melhor_op[6], 
                    "esporte": esporte_str
                })
    except: pass

# ==========================================
# 5. MÓDULO DE ENVIO DE MÚLTIPLAS E SINGLES
# ==========================================
async def gerenciar_varreduras_e_enviar():
    global oportunidades_globais, surebets_globais, jogos_enviados, historico_pinnacle
    agora_br = datetime.now(ZoneInfo("America/Sao_Paulo"))
    
    treinar_inteligencia_artificial()
        
    jogos_enviados = {k: v for k, v in jogos_enviados.items() if agora_br <= v}
    historico_pinnacle = {k: v for k, v in historico_pinnacle.items() if agora_br <= v["expires"]}
    oportunidades_globais.clear()
    surebets_globais.clear()
    
    async with aiohttp.ClientSession() as session:
        tasks =[processar_liga_async(session, liga, agora_br) for liga in LIGAS]
        await asyncio.gather(*tasks)

        if surebets_globais:
            for arb in surebets_globais:
                texto_arb = (
                    "🚨🚨 <b>SUREBET DETECTADA (RISCO ZERO)</b> 🚨🚨\n\n"
                    f"🏆 <b>Liga:</b> {arb['liga']}\n"
                    f"⚽ <b>Jogo:</b> {arb['home_team']} x {arb['away_team']}\n\n"
                )
                for n_out, dados in arb["odds"].items():
                    texto_arb += f"👉 <b>{dados[2]}:</b> Odd {dados[0]:.2f} na 🏛️ {dados[1]}\n"
                texto_arb += f"\n💰 <b>LUCRO 100% GARANTIDO:</b> +{arb['lucro']*100:.2f}%\n"
                await enviar_telegram_async(session, texto_arb)
                jogos_enviados[arb["jogo_id"]] = agora_br + timedelta(hours=24)

        if oportunidades_globais:
            
            # --- 1. MÓDULO DE MÚLTIPLA PRONTA ---
            candidatas_multipla =[op for op in oportunidades_globais if op["odd_bookie"] <= 1.70 and op["prob_justa"] >= 0.60]
            jogos_multipla_ids =[]
            
            if len(candidatas_multipla) >= 2:
                candidatas_multipla.sort(key=lambda x: x["prob_justa"], reverse=True)
                jogos_multipla = candidatas_multipla[:3]
                jogos_multipla_ids = [op["jogo_id"] for op in jogos_multipla]
                
                odd_total = 1.0
                texto_multipla = "🔥 <b>OPORTUNIDADE IMPERDÍVEL: MÚLTIPLA PRONTA</b> 🔥\n\n"
                for i, op in enumerate(jogos_multipla, 1):
                    odd_total *= op["odd_bookie"]
                    emoji_esp = "🏀" if op["esporte"] == "basketball" else "⚽"
                    texto_multipla += f"{emoji_esp} <b>Jogo {i}: {op['home_team']} x {op['away_team']}</b>\n"
                    texto_multipla += f"👉 <b>Entrada:</b> {op['mercado_nome']} - {op['selecao_nome']} ({op['nome_bookie'].title()})\n"
                    texto_multipla += f"📈 <b>Odd:</b> {op['odd_bookie']:.2f} | ⏰ {op['horario_br'].strftime('%H:%M')}\n\n"
                texto_multipla += f"💵 <b>ODD TOTAL:</b> {odd_total:.2f}\n"
                texto_multipla += f"💰 <b>Gestão Sugerida:</b> 0.5% da Banca\n"
                texto_multipla += f"✅ <i>Cruze essas entradas na sua casa de aposta!</i>"
                
                await enviar_telegram_async(session, texto_multipla)
                for op in jogos_multipla:
                    jogos_enviados[op["jogo_id"]] = agora_br + timedelta(hours=24)
                    salvar_aposta_banco(op, 0.5)

            # --- 2. FILTRAGEM INDEPENDENTE (SEM UM ESPORTE ENGOLIR O OUTRO) ---
            singles =[op for op in oportunidades_globais if op["jogo_id"] not in jogos_multipla_ids]
            
            # Divide os dois mundos
            soccer_ops = [op for op in singles if op["esporte"] == "soccer"]
            basket_ops = [op for op in singles if op["esporte"] == "basketball"]
            
            # Ordena por melhor valor matemático dentro de seu esporte
            soccer_ops.sort(key=lambda x: x["ev_real"], reverse=True)
            basket_ops.sort(key=lambda x: x["ev_real"], reverse=True)
            
            # Teto dinâmico de qualidade (Manda os melhores se houver, sem engolir um ao outro)
            # Se tiver 12 bons de futebol, vai mandar 10. Se tiver 5 bons de basquete, vai mandar 5.
            melhores_finais = soccer_ops[:10] + basket_ops[:5]
            
            # Ordena cronologicamente para mandar bonitinho no Telegram
            melhores_finais.sort(key=lambda x: x["horario_br"])
            
            for op in melhores_finais:
                ev_real, prob_justa, odd_bookie, esporte = op["ev_real"], op["prob_justa"], op["odd_bookie"], op["esporte"]
                emoji = "🏀" if esporte == "basketball" else "⚽"
                
                # CLASSIFICAÇÃO INTELIGENTE COM SUAS TAGS
                if op["is_dropping"]:
                    cabecalho, confianca, kelly_pct = f"📉 <b>SMART MONEY (DERRETIMENTO)</b>", "🔥 ELITE", 2.0
                elif esporte == "basketball":
                    if ev_real >= 0.04: cabecalho, confianca, kelly_pct = f"{emoji} <b>NBA/EURO: SNIPER (+EV ALTO)</b>", "🔥 ELITE", 2.0
                    else: cabecalho, confianca, kelly_pct = f"{emoji} <b>NBA/EURO: SÓLIDA</b>", "💪 FORTE", 1.5
                else:
                    if odd_bookie <= 1.70 and prob_justa >= 0.60:
                        cabecalho, confianca, kelly_pct = f"{emoji} <b>ALTA PROBABILIDADE (MÁXIMA SEGURANÇA)</b>", "🔥 ELITE", 2.0
                    elif ev_real >= 0.06:
                        cabecalho, confianca, kelly_pct = f"{emoji} <b>SNIPER INSTITUCIONAL</b>", "🔥 ELITE", 2.0
                    elif odd_bookie >= 3.50:
                        cabecalho, confianca, kelly_pct = f"{emoji} <b>ZEBRA DE VALOR (+EV ALTO)</b>", "👍 BOA", 0.5
                    else:
                        cabecalho, confianca, kelly_pct = f"{emoji} <b>ENTRADA DE VALOR (MODERADA)</b>", "💪 FORTE", 1.0

                horas_f, min_f = int(op["minutos_faltando"] // 60), int(op["minutos_faltando"] % 60)
                tempo_str = f"{horas_f}h {min_f}min" if horas_f > 0 else f"{min_f} min"
                
                texto_msg = (
                    f"{cabecalho}\n\n"
                    f"🏆 <b>Liga:</b> {op['evento']['sport_title']}\n"
                    f"⏰ <b>Horário:</b> {op['horario_br'].strftime('%H:%M')} (Faltam {tempo_str})\n"
                    f"⚔️ <b>Jogo:</b> {op['home_team']} x {op['away_team']}\n\n"
                    f"🎯 <b>Mercado:</b> {op['mercado_nome']}\n"
                    f"👉 <b>Entrada:</b> {op['selecao_nome']}\n"
                    f"🏛️ <b>Casa de Aposta:</b> {op['nome_bookie'].upper()}\n"
                    f"📈 <b>Odd Atual:</b> {odd_bookie:.2f}\n\n"
                    f"💰 <b>Gestão/Stake:</b> {kelly_pct:.1f}% Unidades\n"
                    f"🛡️ <b>Confiança:</b> {confianca}\n"
                    f"📊 <b>Vantagem Matemática (+EV):</b> +{ev_real*100:.2f}%\n"
                    f"✅ <b>Probabilidade Real:</b> {prob_justa*100:.1f}%\n"
                )
                await enviar_telegram_async(session, texto_msg)
                jogos_enviados[op["jogo_id"]] = agora_br + timedelta(hours=24)
                salvar_aposta_banco(op, kelly_pct)

async def loop_infinito():
    while True:
        print("\n🔎 VARREDURA GERAL INICIADA")
        await gerenciar_varreduras_e_enviar()
        print(f"\n⏳ Bot dormindo por {SCAN_INTERVAL//3600} horas (Economia de Chaves)...")
        await asyncio.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    inicializar_banco()
    carregar_memoria_banco()
    print("🤖 BOT SINDICATO ASIÁTICO V12 PRO INICIADO")
    print("🎯 MODO: Sem Limites Cegos | Validação Paralela por Esporte | Multiplas ON")
    asyncio.run(loop_infinito())
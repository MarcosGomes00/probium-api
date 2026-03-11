import asyncio
import aiohttp
import sqlite3
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# ==========================================
# CONFIGURAÇÕES BOT 1 - FUTEBOL
# ==========================================
API_KEYS_ODDS =[
    "6a1c0078b3ed09b42fbacee8f07e7cc3", "4949c49070dd3eff2113bd1a07293165",
    "0ecb237829d0f800181538e1a4fa2494", "4790419cc795932ffaeb0152fa5818c8",
    "5ee1c6a8c611b6c3d6aff8043764555f", "b668851102c3e0a56c33220161c029ec",
    "0d43575dd39e175ba670fb91b2230442", "d32378e66e89f159688cc2239f38a6a4",
    "713146de690026b224dd8bbf0abc0339"
]

TELEGRAM_TOKEN = "8725909088:AAGQMNr-9RVQB7hWmePCLmm0GwaGuzOVy-A" # Token Bot 1
CHAT_ID = "-1003814625223"
DB_FILE = "probum.db"
SCAN_INTERVAL = 21600 # 6 Horas para economizar API

SOFT_BOOKIES =["bet365","betano","1xbet","draftkings","williamhill","unibet","888sport","betfair_ex_eu"]
SHARP_BOOKIE = "pinnacle"
TODAS_CASAS = SOFT_BOOKIES +[SHARP_BOOKIE]

LEAGUE_TIERS = {
    "soccer_uefa_champs_league": 1.5, "soccer_epl": 1.5, "soccer_spain_la_liga": 1.2,
    "soccer_germany_bundesliga": 1.2, "soccer_italy_serie_a": 1.2, "soccer_brazil_campeonato": 1.0,
    "soccer_conmebol_copa_libertadores": 1.0, "soccer_france_ligue_one": 1.0,
    "soccer_portugal_primeira_liga": 1.0, "soccer_brazil_copa_do_brasil": 1.0,
    "soccer_conmebol_copa_sudamericana": 0.8, "soccer_brazil_serie_b": 0.8
}

LIGAS = list(LEAGUE_TIERS.keys())
jogos_enviados = {}
sgp_enviados = {} # Memória das múltiplas na mesma partida
historico_pinnacle = {} 
memoria_ia = {} 
chave_odds_atual = 0 
api_lock = asyncio.Lock()

oportunidades_globais =[]
sgp_globais =[] # Lista de Bet Builders

# FUNÇÕES DE BANCO E IA
def carregar_memoria_banco():
    global jogos_enviados
    try:
        conn = sqlite3.connect(DB_FILE, timeout=10)
        cursor = conn.cursor()
        cursor.execute("SELECT id_aposta FROM operacoes_tipster WHERE status = 'PENDENTE'")
        for (id_aposta,) in cursor.fetchall():
            jogos_enviados[id_aposta.split("_")[0]] = datetime.now(ZoneInfo("America/Sao_Paulo")) + timedelta(hours=24)
        conn.close()
    except: pass

def checar_limite_diario():
    try:
        conn = sqlite3.connect(DB_FILE, timeout=10)
        cursor = conn.cursor()
        hoje = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime('%d/%m/%Y')
        cursor.execute("SELECT COUNT(*) FROM operacoes_tipster WHERE data_hora = ?", (hoje,))
        total_hoje = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM operacoes_tipster WHERE data_hora = ? AND esporte = 'soccer'", (hoje,))
        futebol_hoje = cursor.fetchone()[0]
        conn.close()
        return total_hoje, futebol_hoje
    except: return 0, 0

def salvar_aposta_banco(op, stake):
    try:
        conn = sqlite3.connect(DB_FILE, timeout=10)
        cursor = conn.cursor()
        id_aposta = f"{op['jogo_id']}_{op['mercado_nome'][:4]}_{op['selecao_nome'][:4]}".replace(" ", "")
        hoje = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime('%d/%m/%Y')
        cursor.execute("""
            INSERT OR IGNORE INTO operacoes_tipster 
            (id_aposta, esporte, jogo, liga, mercado, selecao, odd, prob, ev, stake, status, lucro, data_hora, pinnacle_odd, ranking_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDENTE', 0, ?, ?, ?)
        """, (id_aposta, op['esporte'], f"{op['home_team']} x {op['away_team']}", op['evento']['sport_title'], op['mercado_nome'], op['selecao_nome'], op['odd_bookie'], op['prob_justa'], op['ev_real'], stake, hoje, op.get('odd_pinnacle', 0), op.get('ranking_score', 0)))
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
    for s in[" fc", " cf", " cd", " sc", " cp", " fk", " nk"]:
        if nome.endswith(s): nome = nome[:-len(s)].strip()
    return {"bayern munich": "bayern", "paris saint germain": "psg", "internazionale": "inter", "ac milan": "milan"}.get(nome, nome)

def calcular_prob_justa(outcomes):
    try:
        margem = sum(1 / item["price"] for item in outcomes if item["price"] > 0)
        return {normalizar_nome(item["name"]): ((1 / item["price"]) / margem, item["price"]) for item in outcomes if item["price"] > 0}
    except: return {}

def treinar_ia():
    global memoria_ia
    memoria_ia.clear()
    try:
        conn = sqlite3.connect(DB_FILE, timeout=10)
        cursor = conn.cursor()
        cursor.execute("SELECT liga, mercado, lucro, stake FROM operacoes_tipster WHERE status != 'PENDENTE'")
        for liga, mercado, lucro, stake in cursor.fetchall():
            chave = f"{liga}_{mercado}"
            if chave not in memoria_ia: memoria_ia[chave] = {"l": 0.0, "s": 0.0, "c": 0}
            memoria_ia[chave]["l"] += lucro
            memoria_ia[chave]["s"] += stake
            memoria_ia[chave]["c"] += 1
        for k, v in memoria_ia.items():
            memoria_ia[k] = (v["l"] / v["s"]) * 100 if v["c"] >= 10 else 0
        conn.close()
    except: pass

def validar_futebol(odd, ev, liga):
    if not (1.30 <= odd <= 15.00) or ev > 0.18: return False 
    ev_exigido = 0.010 if odd <= 1.70 else (0.020 if odd <= 3.50 else 0.035)
    if LEAGUE_TIERS.get(liga, 1.0) >= 1.4: ev_exigido -= 0.005
    return ev >= ev_exigido

async def processar_liga_async(session, liga_key, agora_br):
    # Ampliamos para totals (Gols) para poder gerar os Bet Builders perfeitos
    parametros = {"regions": "eu", "markets": "h2h,btts,totals", "bookmakers": ",".join(TODAS_CASAS)}
    data = await fazer_requisicao_odds(session, f"https://api.the-odds-api.com/v4/sports/{liga_key}/odds/", parametros)
    if not isinstance(data, list): return

    for evento in data:
        jogo_id = str(evento['id'])
        horario_br = datetime.fromisoformat(evento["commence_time"].replace("Z", "+00:00")).astimezone(ZoneInfo("America/Sao_Paulo"))
        minutos = (horario_br - agora_br).total_seconds() / 60
        if not (15 <= minutos <= 1440): continue 

        bookmakers = evento.get("bookmakers",[])
        pinnacle = next((b for b in bookmakers if b["key"] == SHARP_BOOKIE), None)
        if not pinnacle: continue 

        dropping_alerts = {}
        for m in pinnacle.get("markets",[]):
            for out in m["outcomes"]:
                n_out = normalizar_nome(out["name"])
                chave_hist = f"{jogo_id}_{m['key']}_{n_out}_{out.get('point','')}"
                preco_atual = out["price"]
                if chave_hist in historico_pinnacle and (historico_pinnacle[chave_hist]["price"] - preco_atual) / historico_pinnacle[chave_hist]["price"] >= 0.06:
                    dropping_alerts[chave_hist] = True
                historico_pinnacle[chave_hist] = {"price": preco_atual, "expires": agora_br + timedelta(hours=24)}

        oportunidades_jogo =[]
        for soft_b in bookmakers:
            if soft_b["key"] not in SOFT_BOOKIES: continue
            
            for m_key in ["h2h", "btts", "totals"]:
                pin_m = next((m for m in pinnacle.get("markets",[]) if m["key"] == m_key), None)
                soft_m = next((m for m in soft_b.get("markets",[]) if m["key"] == m_key), None)
                
                if pin_m and soft_m:
                    if m_key in ["h2h", "btts"]:
                        probs_justas = calcular_prob_justa(pin_m["outcomes"])
                        for s_out in soft_m["outcomes"]:
                            n_out = normalizar_nome(s_out["name"])
                            if n_out in probs_justas:
                                prob_real, odd_pin = probs_justas[n_out]
                                odd_oferecida = s_out["price"]
                                ev_real = (prob_real * odd_oferecida) - 1
                                if prob_real > 0 and validar_futebol(odd_oferecida, ev_real, liga_key):
                                    is_dropping = dropping_alerts.get(f"{jogo_id}_{m_key}_{n_out}_", False)
                                    score = (ev_real * 100) * prob_real * LEAGUE_TIERS.get(liga_key, 1.0) * (1.3 if is_dropping else 1.0)
                                    traducao = "Vencedor (1X2)" if m_key == "h2h" else "Ambas Marcam"
                                    selecao = "Sim" if s_out["name"]=="Yes" else "Não" if s_out["name"]=="No" else s_out["name"].replace("/", " ou ")
                                    oportunidades_jogo.append({
                                        "jogo_id": jogo_id, "evento": evento, "home_team": evento["home_team"], "away_team": evento["away_team"],
                                        "horario_br": horario_br, "minutos": minutos, "mercado_nome": traducao, "selecao_nome": selecao,
                                        "odd_bookie": odd_oferecida, "odd_pinnacle": odd_pin, "prob_justa": prob_real, "ev_real": ev_real,
                                        "nome_bookie": soft_b["title"], "is_dropping": is_dropping, "ranking_score": score, "esporte": "soccer"
                                    })
                    elif m_key == "totals":
                        for s_out in soft_m["outcomes"]:
                            ponto = s_out.get("point")
                            n_out = normalizar_nome(s_out["name"])
                            pin_match = next((p for p in pin_m["outcomes"] if normalizar_nome(p["name"]) == n_out and p.get("point") == ponto), None)
                            if pin_match and (1.50 <= pin_match["price"] <= 2.50):
                                par_pin =[p for p in pin_m["outcomes"] if p.get("point") == ponto]
                                try:
                                    prob_real = (1 / pin_match["price"]) / sum(1 / i["price"] for i in par_pin if i["price"] > 0)
                                    odd_oferecida = s_out["price"]
                                    ev_real = (prob_real * odd_oferecida) - 1
                                    if prob_real > 0 and validar_futebol(odd_oferecida, ev_real, liga_key):
                                        is_dropping = dropping_alerts.get(f"{jogo_id}_{m_key}_{n_out}_{ponto}", False)
                                        score = (ev_real * 100) * prob_real * LEAGUE_TIERS.get(liga_key, 1.0)
                                        oportunidades_jogo.append({
                                            "jogo_id": jogo_id, "evento": evento, "home_team": evento["home_team"], "away_team": evento["away_team"],
                                            "horario_br": horario_br, "minutos": minutos, "mercado_nome": "Gols (Mais/Menos)", "selecao_nome": f"{s_out['name']} {ponto}",
                                            "odd_bookie": odd_oferecida, "odd_pinnacle": pin_match["price"], "prob_justa": prob_real, "ev_real": ev_real,
                                            "nome_bookie": soft_b["title"], "is_dropping": is_dropping, "ranking_score": score, "esporte": "soccer"
                                        })
                                except: pass

        if oportunidades_jogo:
            # 🔥 MOTOR DE "CRIAR APOSTA" (BET BUILDER) 🔥
            # Se o bot achou 2 ou mais mercados com valor NO MESMO JOGO, ele junta!
            mercados_unicos =[]
            mercados_vistos = set()
            for op in sorted(oportunidades_jogo, key=lambda x: x["ev_real"], reverse=True):
                if op["mercado_nome"] not in mercados_vistos and op["ev_real"] >= 0.015:
                    mercados_unicos.append(op)
                    mercados_vistos.add(op["mercado_nome"])
            
            if len(mercados_unicos) >= 2 and jogo_id not in sgp_enviados:
                sgp_globais.append({
                    "jogo_id": jogo_id,
                    "evento": evento,
                    "home_team": evento["home_team"],
                    "away_team": evento["away_team"],
                    "horario_br": horario_br,
                    "pernas": mercados_unicos
                })

            # Adiciona o melhor mercado avulso desse jogo para a lista global de Singles (se ainda não enviou)
            if jogo_id not in jogos_enviados:
                oportunidades_globais.append(max(oportunidades_jogo, key=lambda x: x["ranking_score"]))

async def varrer_e_enviar():
    global jogos_enviados, sgp_enviados, historico_pinnacle
    agora_br = datetime.now(ZoneInfo("America/Sao_Paulo"))
    treinar_ia()
    
    jogos_enviados = {k: v for k, v in jogos_enviados.items() if agora_br <= v}
    sgp_enviados = {k: v for k, v in sgp_enviados.items() if agora_br <= v}
    historico_pinnacle = {k: v for k, v in historico_pinnacle.items() if agora_br <= v["expires"]}
    
    oportunidades_globais.clear()
    sgp_globais.clear()
    
    async with aiohttp.ClientSession() as session:
        await asyncio.gather(*[processar_liga_async(session, l, agora_br) for l in LIGAS])

        # --- 1. ENVIAR BET BUILDERS (CRIAR APOSTA NO MESMO JOGO) ---
        for sgp in sgp_globais:
            odd_combinada = 1.0
            texto_sgp = "🧩 <b>OPORTUNIDADE: CRIAR APOSTA (BET BUILDER)</b> 🧩\n\n"
            texto_sgp += f"🏆 <b>Liga:</b> {sgp['evento']['sport_title']}\n"
            texto_seq = f"⚽ <b>Jogo:</b> {sgp['home_team']} x {sgp['away_team']}\n⏰ <b>Horário:</b> {sgp['horario_br'].strftime('%H:%M')}\n\n"
            texto_sgp += texto_seq
            texto_sgp += "🛠️ <b>Vá em 'Criar Aposta' e junte estas seleções:</b>\n"
            
            casa_sugerida = sgp["pernas"][0]["nome_bookie"].title()
            for i, perna in enumerate(sgp["pernas"], 1):
                odd_combinada *= perna["odd_bookie"]
                texto_sgp += f"👉 <b>Selo {i}:</b> {perna['mercado_nome']} - {perna['selecao_nome']}\n"
            
            # As casas cobram uma taxa ao cruzar apostas, então a odd real é uns 15% menor
            odd_estimada = odd_combinada * 0.85 
            
            texto_sgp += f"\n🏦 <b>Casa Sugerida:</b> {casa_sugerida} ou Bet365\n"
            texto_sgp += f"💵 <b>Odd Combinada Estimada:</b> ~{odd_estimada:.2f}\n"
            texto_sgp += f"💰 <b>Gestão Sugerida:</b> 0.5% da Banca\n"
            texto_sgp += f"💡 <i>(O Algoritmo encontrou Desajuste Matemático em todos esses mercados juntos!)</i>"
            
            await enviar_telegram_async(session, texto_sgp)
            sgp_enviados[sgp["jogo_id"]] = agora_br + timedelta(hours=24)
            # Aproveita e já bloqueia o single desse jogo pra não poluir
            jogos_enviados[sgp["jogo_id"]] = agora_br + timedelta(hours=24)

        # --- 2. ENVIAR SINGLES NORMAIS ---
        if oportunidades_globais:
            singles = [op for op in oportunidades_globais if op["jogo_id"] not in sgp_enviados]
            singles.sort(key=lambda x: x["ranking_score"], reverse=True)
            
            total_hoje, fut_hoje = checar_limite_diario()
            vagas_restantes_global = max(0, 10 - total_hoje)
            vagas_permitidas = min(5, vagas_restantes_global)
            
            if vagas_restantes_global > 0:
                singles_finais =[]
                for op in singles:
                    if len(singles_finais) < vagas_permitidas:
                        singles_finais.append(op)
                    elif len(singles_finais) < vagas_restantes_global and op["ranking_score"] > 2.0:
                        singles_finais.append(op)
                        
                singles_finais.sort(key=lambda x: x["horario_br"])
                
                for op in singles_finais:
                    ev = op["ev_real"]
                    if op["is_dropping"]: cb, cf, st = "📉 <b>SMART MONEY (DERRETIMENTO)</b>", "🔥 ELITE", 2.0
                    elif op["odd_bookie"] <= 1.70: cb, cf, st = "🎯 <b>ALTA PROBABILIDADE</b>", "🔥 ELITE", 2.0
                    elif op["odd_bookie"] >= 3.50: cb, cf, st = "🦓 <b>ZEBRA DE VALOR</b>", "👍 BOA", 0.5
                    else: cb, cf, st = "💎 <b>SNIPER INSTITUCIONAL</b>", "💪 FORTE", 1.5

                    txt = (f"{cb}\n\n🏆 <b>Liga:</b> {op['evento']['sport_title']}\n⏰ <b>Horário:</b> {op['horario_br'].strftime('%H:%M')}\n"
                           f"⚽ <b>Jogo:</b> {op['home_team']} x {op['away_team']}\n\n🎯 <b>Mercado:</b> {op['mercado_nome']}\n"
                           f"👉 <b>Entrada:</b> {op['selecao_nome']}\n🏛️ <b>Casa:</b> {op['nome_bookie'].upper()}\n"
                           f"📈 <b>Odd Atual:</b> {op['odd_bookie']:.2f} (Pin: {op['odd_pinnacle']:.2f})\n\n💰 <b>Gestão/Stake:</b> {st:.1f}%\n"
                           f"🛡️ <b>Confiança:</b> {cf}\n📊 <b>Valor (+EV):</b> +{ev*100:.2f}%\n✅ <b>Probabilidade:</b> {op['prob_justa']*100:.1f}%\n")
                    await enviar_telegram_async(session, txt)
                    jogos_enviados[op["jogo_id"]] = agora_br + timedelta(hours=24)
                    salvar_aposta_banco(op, st)

async def loop_infinito():
    while True:
        print("\n⚽ BOT FUTEBOL: VARREDURA INICIADA")
        await varrer_e_enviar()
        print(f"⚽ BOT FUTEBOL: Dormindo por {SCAN_INTERVAL//3600}h...")
        await asyncio.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    carregar_memoria_banco()
    print("🤖 BOT FUTEBOL SINDICATO V12.1 INICIADO")
    print("🔥 Motor de 'CRIAR APOSTA' (Bet Builder) Ativado!")
    asyncio.run(loop_infinito())
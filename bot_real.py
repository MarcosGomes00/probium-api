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

# PESO DE RELEVÂNCIA (SISTEMA DE RANKING)
LEAGUE_TIERS = {
    "soccer_uefa_champs_league": 1.5,
    "soccer_epl": 1.5,
    "basketball_nba": 1.5,
    "soccer_spain_la_liga": 1.2,
    "soccer_germany_bundesliga": 1.2,
    "soccer_italy_serie_a": 1.2,
    "basketball_euroleague": 1.2,
    "soccer_brazil_campeonato": 1.0,
    "soccer_conmebol_copa_libertadores": 1.0,
    "soccer_france_ligue_one": 1.0,
    "soccer_portugal_primeira_liga": 1.0,
    "soccer_brazil_copa_do_brasil": 1.0,
    "soccer_conmebol_copa_sudamericana": 0.8,
    "soccer_brazil_serie_b": 0.8
}

LIGAS = list(LEAGUE_TIERS.keys())

jogos_enviados = {}
historico_pinnacle = {} 
memoria_ia = {} 
chave_odds_atual = 0 
api_lock = asyncio.Lock()

oportunidades_globais =[]

# ==========================================
# 2. FUNÇÕES DE SUPORTE, CLV E BANCO
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
    # Upgrade automático do Banco (Para Tracking de CLV e Ranking)
    cursor.execute("PRAGMA table_info(operacoes_tipster)")
    colunas = [col[1] for col in cursor.fetchall()]
    if "pinnacle_odd" not in colunas:
        cursor.execute("ALTER TABLE operacoes_tipster ADD COLUMN pinnacle_odd REAL DEFAULT 0")
    if "ranking_score" not in colunas:
        cursor.execute("ALTER TABLE operacoes_tipster ADD COLUMN ranking_score REAL DEFAULT 0")
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
    except: pass

def salvar_aposta_banco(op, stake):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        id_aposta = f"{op['jogo_id']}_{op['mercado_nome'][:4]}_{op['selecao_nome'][:4]}".replace(" ", "")
        data_atual = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime('%d/%m/%Y')
        cursor.execute("""
            INSERT OR IGNORE INTO operacoes_tipster 
            (id_aposta, esporte, jogo, liga, mercado, selecao, odd, prob, ev, stake, status, lucro, data_hora, pinnacle_odd, ranking_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDENTE', 0, ?, ?, ?)
        """, (
            id_aposta, op['esporte'], f"{op['home_team']} x {op['away_team']}",
            op['evento']['sport_title'], op['mercado_nome'], op['selecao_nome'],
            op['odd_bookie'], op['prob_justa'], op['ev_real'], stake, data_atual,
            op['odd_pinnacle'], op['ranking_score']
        ))
        conn.commit()
        conn.close()
    except Exception as e: print(f"Erro BD: {e}")

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
        return {normalizar_nome(item["name"]): ((1 / item["price"]) / margem, item["price"]) for item in outcomes if item["price"] > 0}
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
            if dados["apostas"] >= 10: 
                memoria_ia[chave] = (dados["lucro_total"] / dados["stake_total"]) * 100
    except: pass

# ==========================================
# 3. CÉREBROS SEPARADOS (FUTEBOL vs BASQUETE)
# ==========================================
def validar_futebol_ia(odd, ev, liga_key):
    """ Regras rígidas baseadas na probabilidade do 1X2 e Ambas """
    ev_exigido = 0.010 if odd <= 1.70 else (0.020 if odd <= 3.50 else 0.035)
    
    # Tolerância extra para ligas Tier S (Limites maiores)
    if LEAGUE_TIERS.get(liga_key, 1.0) >= 1.4:
        ev_exigido -= 0.005
        
    return ev >= ev_exigido

def validar_basquete_ia(odd, ev, liga_key):
    """ Linhas afiadas. EV de 1.5% na NBA é um erro brutal da casa """
    ev_exigido = 0.015 if odd <= 2.10 else 0.025
    return ev >= ev_exigido

def calcular_ranking_score(ev, prob, liga_key, is_dropping, is_line_error):
    """ O CORAÇÃO DO SINDICATO: Ranking Ponderado """
    peso_liga = LEAGUE_TIERS.get(liga_key, 1.0)
    peso_sharp = 1.3 if is_dropping else 1.0
    peso_erro_linha = 1.5 if is_line_error else 1.0
    
    # Multiplica tudo para gerar uma "Nota de Qualidade" da aposta
    return (ev * 100) * prob * peso_liga * peso_sharp * peso_erro_linha

# ==========================================
# 4. NÚCLEO ASYNC DE VARREDURA
# ==========================================
async def processar_liga_async(session, liga_key, agora_br):
    esporte_str = "basketball" if "basketball" in liga_key else "soccer"
    mercados_alvo = "h2h,spreads,totals" if esporte_str == "basketball" else "h2h,btts"
    casas_busca = ",".join(TODAS_CASAS)
    
    parametros = {"regions": "eu", "markets": mercados_alvo, "bookmakers": casas_busca}
    url_odds = f"https://api.the-odds-api.com/v4/sports/{liga_key}/odds/"
    
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
            pinnacle = next((b for b in bookmakers if b["key"] == SHARP_BOOKIE), None)
            if not pinnacle: continue 

            # SHARP MONEY (Quedas Reais)
            dropping_alerts = {}
            for m in pinnacle.get("markets",[]):
                for out in m["outcomes"]:
                    n_out = normalizar_nome(out["name"])
                    chave_hist = f"{jogo_id}_{m['key']}_{n_out}_{out.get('point','')}"
                    preco_atual = out["price"]
                    if chave_hist in historico_pinnacle:
                        preco_antigo = historico_pinnacle[chave_hist]["price"]
                        # Drop Real: Queda > 6% na Pinnacle
                        if (preco_antigo - preco_atual) / preco_antigo >= 0.06:
                            dropping_alerts[chave_hist] = True
                    historico_pinnacle[chave_hist] = {"price": preco_atual, "expires": agora_br + timedelta(hours=24)}

            oportunidades_jogo =[]
            for soft_b in bookmakers:
                if soft_b["key"] == SHARP_BOOKIE or soft_b["key"] not in SOFT_BOOKIES: continue
                nome_casa = soft_b["title"]

                # LÓGICA FUTEBOL E MONEYLINE
                for m_key in["h2h", "btts"]:
                    pin_m = next((m for m in pinnacle.get("markets",[]) if m["key"] == m_key), None)
                    soft_m = next((m for m in soft_b.get("markets",[]) if m["key"] == m_key), None)
                    if pin_m and soft_m:
                        probs_justas = calcular_prob_justa(pin_m["outcomes"])
                        for s_outcome in soft_m["outcomes"]:
                            n_out = normalizar_nome(s_outcome["name"])
                            
                            if n_out in probs_justas:
                                prob_real, odd_pinnacle = probs_justas[n_out]
                                odd_oferecida = s_outcome["price"]
                                
                                if prob_real > 0:
                                    ev_real = (prob_real * odd_oferecida) - 1
                                    
                                    # Usa o Cérebro Específico
                                    valido = validar_basquete_ia(odd_oferecida, ev_real, liga_key) if esporte_str == "basketball" else validar_futebol_ia(odd_oferecida, ev_real, liga_key)
                                    
                                    if valido:
                                        chave_hist = f"{jogo_id}_{m_key}_{n_out}_"
                                        is_dropping = dropping_alerts.get(chave_hist, False)
                                        score = calcular_ranking_score(ev_real, prob_real, liga_key, is_dropping, False)
                                        
                                        traducao = "Vencedor (1X2)" if m_key == "h2h" else "Ambas Marcam"
                                        selecao = "Sim" if s_outcome["name"]=="Yes" else "Não" if s_outcome["name"]=="No" else s_outcome["name"].replace("/", " ou ")
                                        
                                        oportunidades_jogo.append({
                                            "jogo_id": jogo_id, "evento": evento, "home_team": evento["home_team"], "away_team": evento["away_team"],
                                            "horario_br": horario_br, "minutos_faltando": minutos_faltando, "mercado_nome": traducao,
                                            "selecao_nome": selecao, "odd_bookie": odd_oferecida, "odd_pinnacle": odd_pinnacle,
                                            "prob_justa": prob_real, "ev_real": ev_real, "nome_bookie": nome_casa, 
                                            "is_dropping": is_dropping, "is_line_error": False, "ranking_score": score, "esporte": esporte_str
                                        })

                # LÓGICA BASQUETE (HANDICAPS E TOTAIS) - CAÇADOR DE ERROS DE LINHA
                if esporte_str == "basketball":
                    for m_key in["spreads", "totals"]:
                        pin_m = next((m for m in pinnacle.get("markets",[]) if m["key"] == m_key), None)
                        soft_m = next((m for m in soft_b.get("markets",[]) if m["key"] == m_key), None)
                        if pin_m and soft_m:
                            for s_outcome in soft_m["outcomes"]:
                                ponto = s_outcome.get("point")
                                nome_s = s_outcome["name"]
                                n_out = normalizar_nome(nome_s)
                                
                                # Procura a MESMA linha exata na Pinnacle para comparar
                                pin_match = next((p for p in pin_m["outcomes"] if normalizar_nome(p["name"]) == n_out and p.get("point") == ponto), None)
                                
                                if pin_match and (1.50 <= pin_match["price"] <= 2.50):
                                    par_pinnacle =[p for p in pin_m["outcomes"] if p.get("point") in (ponto, -ponto) or (m_key == "totals" and p.get("point") == ponto)]
                                    
                                    nome_mercado = "Handicap Asiático" if m_key == "spreads" else "Pontos Totais"
                                    selecao_nome = f"{nome_s} {ponto}"

                                    try:
                                        prob_real = (1 / pin_match["price"]) / sum(1 / i["price"] for i in par_pinnacle if i["price"] > 0)
                                        odd_oferecida = s_outcome["price"]
                                        
                                        if prob_real > 0:
                                            ev_real = (prob_real * odd_oferecida) - 1
                                            
                                            if validar_basquete_ia(odd_oferecida, ev_real, liga_key):
                                                chave_hist = f"{jogo_id}_{m_key}_{n_out}_{ponto}"
                                                is_dropping = dropping_alerts.get(chave_hist, False)
                                                
                                                # Erro de linha gritante: EV maior que 5% em Spread da NBA significa que a casa dormiu no ponto
                                                is_line_error = ev_real > 0.05
                                                score = calcular_ranking_score(ev_real, prob_real, liga_key, is_dropping, is_line_error)
                                                
                                                oportunidades_jogo.append({
                                                    "jogo_id": jogo_id, "evento": evento, "home_team": evento["home_team"], "away_team": evento["away_team"],
                                                    "horario_br": horario_br, "minutos_faltando": minutos_faltando, "mercado_nome": nome_mercado,
                                                    "selecao_nome": selecao_nome, "odd_bookie": odd_oferecida, "odd_pinnacle": pin_match["price"],
                                                    "prob_justa": prob_real, "ev_real": ev_real, "nome_bookie": nome_casa, 
                                                    "is_dropping": is_dropping, "is_line_error": is_line_error, "ranking_score": score, "esporte": esporte_str
                                                })
                                    except: pass

            if oportunidades_jogo:
                # Seleciona a de MAIOR SCORE (Melhor balanceamento de risco/retorno) dentro do jogo
                melhor_op = max(oportunidades_jogo, key=lambda x: x["ranking_score"]) 
                oportunidades_globais.append(melhor_op)
    except: pass

# ==========================================
# 5. GERENCIADOR DE RANQUEAMENTO E ENVIO
# ==========================================
async def gerenciar_varreduras_e_enviar():
    global oportunidades_globais, jogos_enviados, historico_pinnacle
    agora_br = datetime.now(ZoneInfo("America/Sao_Paulo"))
    
    treinar_inteligencia_artificial()
        
    jogos_enviados = {k: v for k, v in jogos_enviados.items() if agora_br <= v}
    historico_pinnacle = {k: v for k, v in historico_pinnacle.items() if agora_br <= v["expires"]}
    oportunidades_globais.clear()
    
    async with aiohttp.ClientSession() as session:
        tasks =[processar_liga_async(session, liga, agora_br) for liga in LIGAS]
        await asyncio.gather(*tasks)

        if oportunidades_globais:
            
            # --- 1. SELEÇÃO DE MÚLTIPLA PRONTA ---
            candidatas_multipla =[op for op in oportunidades_globais if op["odd_bookie"] <= 1.70 and op["prob_justa"] >= 0.60]
            jogos_multipla_ids =[]
            
            if len(candidatas_multipla) >= 2:
                candidatas_multipla.sort(key=lambda x: x["ranking_score"], reverse=True)
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
                
                await enviar_telegram_async(session, texto_multipla)
                for op in jogos_multipla:
                    jogos_enviados[op["jogo_id"]] = agora_br + timedelta(hours=24)
                    salvar_aposta_banco(op, 0.5)

            # --- 2. RANQUEAMENTO ELITE DOS SINGLES ---
            singles =[op for op in oportunidades_globais if op["jogo_id"] not in jogos_multipla_ids]
            
            # Ordena TODAS pelo Super Score Institucional
            singles.sort(key=lambda x: x["ranking_score"], reverse=True)
            
            soccer_ops = [op for op in singles if op["esporte"] == "soccer"]
            basket_ops = [op for op in singles if op["esporte"] == "basketball"]
            
            # Pegamos os melhores absolutos (Teto de 10 Futs e 5 Basket)
            melhores_finais = soccer_ops[:10] + basket_ops[:5]
            melhores_finais.sort(key=lambda x: x["horario_br"])
            
            for op in melhores_finais:
                ev_real, prob_justa, odd_bookie, esporte = op["ev_real"], op["prob_justa"], op["odd_bookie"], op["esporte"]
                emoji = "🏀" if esporte == "basketball" else "⚽"
                
                # SINALIZADORES VISUAIS
                alerta_extra = ""
                if op["is_dropping"]: alerta_extra += "\n🚨 <b>ALERTA:</b> Odd derretendo na Pinnacle (Sharp Money)!"
                if op.get("is_line_error"): alerta_extra += "\n⚠️ <b>ERRO DE LINHA:</b> Casa desajustada com a Pinnacle!"

                if op["is_dropping"] or op.get("is_line_error"):
                    cabecalho, confianca, kelly_pct = f"📉 <b>{emoji} SMART MONEY (ENTRADA ELITE)</b>", "🔥 ELITE", 2.0
                elif esporte == "basketball":
                    if ev_real >= 0.04: cabecalho, confianca, kelly_pct = f"{emoji} <b>NBA/EURO: SNIPER</b>", "🔥 ELITE", 2.0
                    else: cabecalho, confianca, kelly_pct = f"{emoji} <b>NBA/EURO: SÓLIDA</b>", "💪 FORTE", 1.5
                else:
                    if odd_bookie <= 1.70 and prob_justa >= 0.60:
                        cabecalho, confianca, kelly_pct = f"{emoji} <b>ALTA PROBABILIDADE</b>", "🔥 ELITE", 2.0
                    elif ev_real >= 0.06:
                        cabecalho, confianca, kelly_pct = f"{emoji} <b>SNIPER INSTITUCIONAL</b>", "🔥 ELITE", 2.0
                    elif odd_bookie >= 3.50:
                        cabecalho, confianca, kelly_pct = f"{emoji} <b>ZEBRA DE VALOR (+EV ALTO)</b>", "👍 BOA", 0.5
                    else:
                        cabecalho, confianca, kelly_pct = f"{emoji} <b>VALUE BET (MODERADA)</b>", "💪 FORTE", 1.0

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
                    f"📈 <b>Odd Atual:</b> {odd_bookie:.2f} (Pinnacle: {op['odd_pinnacle']:.2f})\n\n"
                    f"💰 <b>Gestão/Stake:</b> {kelly_pct:.1f}% Unidades\n"
                    f"🛡️ <b>Confiança:</b> {confianca}\n"
                    f"📊 <b>Vantagem Matemática (+EV):</b> +{ev_real*100:.2f}%\n"
                    f"✅ <b>Probabilidade Real:</b> {prob_justa*100:.1f}%{alerta_extra}\n"
                )
                await enviar_telegram_async(session, texto_msg)
                jogos_enviados[op["jogo_id"]] = agora_br + timedelta(hours=24)
                salvar_aposta_banco(op, kelly_pct)

async def loop_infinito():
    while True:
        print("\n🔎 VARREDURA GERAL INICIADA (Buscando CLV, Erros de Linha e Smart Money)")
        await gerenciar_varreduras_e_enviar()
        print(f"\n⏳ Bot dormindo por {SCAN_INTERVAL//3600} horas...")
        await asyncio.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    inicializar_banco()
    carregar_memoria_banco()
    print("🤖 BOT SINDICATO ASIÁTICO V12 ELITE INICIADO")
    print("🎯 MODO: Algoritmos Separados | CLV Tracking | Smart Score Ativado")
    asyncio.run(loop_infinito())
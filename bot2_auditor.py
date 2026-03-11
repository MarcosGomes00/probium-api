import sqlite3
import aiohttp
import asyncio
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dataclasses import dataclass
from typing import List, Dict, Tuple
from collections import defaultdict
import statistics

# ==========================================
# CONFIGURAÇÕES BOT 2 - AUDITOR PRO
# ==========================================

# APIs THE-ODDS-API (9 chaves - rotação automática)
API_KEYS_ODDS = [
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

TELEGRAM_TOKEN = "8185027087:AAH1JQJKtlWy_oUQpAvqvHEsFIVOK3ScYBc"
CHAT_ID_ADMIN = "-1003814625223"
DB_FILE = "probum.db"

MIN_AMOSTRAS_PADRAO = 10
LIMITE_WINRATE_ALERTA = 35.0
LIMITE_ROI_ALERTA = -10.0

# Controle de chaves
chave_atual = 0
chaves_falhas = set()
api_lock = asyncio.Lock()
last_request_time = 0
REQUEST_DELAY = 1.0

# ==========================================
# ESTRUTURAS
# ==========================================

@dataclass
class MetricasPeriodo:
    total_apostas: int
    greens: int
    reds: int
    voids: int
    lucro_total: float
    investimento: float
    winrate: float
    roi: float
    media_odd: float
    media_ev: float

@dataclass
class AnalisePadrao:
    categoria: str
    item: str
    amostras: int
    winrate: float
    roi: float
    lucro_total: float
    tendencia: str
    sugestao: str

# ==========================================
# BANCO DE DADOS
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
            stake REAL DEFAULT 1.5,
            status TEXT DEFAULT 'PENDENTE',
            lucro REAL DEFAULT 0,
            data_hora TEXT,
            pinnacle_odd REAL,
            ranking_score REAL,
            nivel_confianca TEXT,
            justificativa TEXT,
            stats_home TEXT,
            stats_away TEXT,
            horario_envio TEXT,
            tier_liga REAL,
            linha REAL,
            processado_em TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS analises_historicas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_analise TEXT,
            categoria TEXT,
            item TEXT,
            amostras INTEGER,
            winrate REAL,
            roi REAL,
            sugestao_gerada TEXT,
            aplicada BOOLEAN DEFAULT 0
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alertas_sistema (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_alerta TEXT,
            tipo TEXT,
            mensagem TEXT,
            categoria_afetada TEXT,
            gravidade TEXT,
            resolvido BOOLEAN DEFAULT 0
        )
    """)
    
    conn.commit()
    conn.close()

# ==========================================
# TELEGRAM
# ==========================================

async def enviar_telegram_async(session: aiohttp.ClientSession, texto: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID_ADMIN,
        "text": texto,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        async with session.post(url, json=payload, timeout=10) as r:
            return r.status == 200
    except:
        return False

# ==========================================
# API COM FAILOVER AUTOMÁTICO
# ==========================================

async def rate_limit():
    global last_request_time
    agora = datetime.now().timestamp()
    tempo_passado = agora - last_request_time
    if tempo_passado < REQUEST_DELAY:
        await asyncio.sleep(REQUEST_DELAY - tempo_passado)
    last_request_time = datetime.now().timestamp()

def get_proxima_chave():
    """Retorna próxima chave válida"""
    global chave_atual
    tentativas = 0
    while tentativas < len(API_KEYS_ODDS):
        chave = API_KEYS_ODDS[chave_atual]
        if chave not in chaves_falhas:
            return chave
        chave_atual = (chave_atual + 1) % len(API_KEYS_ODDS)
        tentativas += 1
    return None

async def obter_resultados_api(session: aiohttp.ClientSession, esporte: str):
    global chave_atual, chaves_falhas
    
    url = f"https://api.the-odds-api.com/v4/sports/{esporte}/scores/"
    params = {"daysFrom": 3, "dateFormat": "iso"}
    
    # Reset chaves se muitas falharam
    if len(chaves_falhas) >= len(API_KEYS_ODDS) - 2:
        chaves_falhas.clear()
    
    for tentativa in range(len(API_KEYS_ODDS)):
        await rate_limit()
        
        async with api_lock:
            chave = get_proxima_chave()
            if not chave:
                print("❌ Todas as chaves falharam!")
                return []
            params["apiKey"] = chave
        
        try:
            async with session.get(url, params=params, timeout=15) as r:
                if r.status == 200:
                    return await r.json()
                elif r.status in [401, 429]:
                    print(f"⚠️ Auditor - Chave falhou: {r.status}")
                    async with api_lock:
                        chaves_falhas.add(chave)
                        chave_atual = (chave_atual + 1) % len(API_KEYS_ODDS)
                else:
                    return await r.json()
        except Exception as e:
            print(f"Erro API Auditor: {e}")
            continue
        
        await asyncio.sleep(1)
    
    return []

def resolver_aposta_completa(aposta: sqlite3.Row, placar: Dict) -> Tuple[str, float, str]:
    mercado = aposta['mercado'].upper()
    selecao = aposta['selecao']
    odd = aposta['odd']
    stake = aposta['stake']
    
    scores = placar.get("scores", [])
    if not scores:
        return "PENDENTE", 0, "Sem placar"
    
    h_team = placar["home_team"]
    a_team = placar["away_team"]
    h_score = next((int(s["score"]) for s in scores if s["name"] == h_team), 0)
    a_score = next((int(s["score"]) for s in scores if s["name"] == a_team), 0)
    total = h_score + a_score
    status = "RED"
    detalhes = ""
    
    if aposta['esporte'] == 'soccer':
        if "H2H" in mercado or "VENCEDOR" in mercado:
            if "1" in selecao and h_score > a_score:
                status = "GREEN"
                detalhes = f"{h_team} venceu {h_score}x{a_score}"
            elif "2" in selecao and a_score > h_score:
                status = "GREEN"
                detalhes = f"{a_team} venceu {a_score}x{h_score}"
            elif ("X" in selecao or "EMPATE" in selecao) and h_score == a_score:
                status = "GREEN"
                detalhes = f"Empate {h_score}x{a_score}"
        
        elif "BTTS" in mercado or "AMBAS" in mercado:
            if "SIM" in selecao.upper() and h_score > 0 and a_score > 0:
                status = "GREEN"
                detalhes = "Ambas marcaram"
            elif "NÃO" in selecao.upper() and (h_score == 0 or a_score == 0):
                status = "GREEN"
                detalhes = "Pelo menos um não marcou"
        
        elif "TOTAL" in mercado or "GOLS" in mercado:
            try:
                linha = float(''.join(c for c in selecao if c.isdigit() or c == '.'))
                if "OVER" in selecao.upper() and total > linha:
                    status = "GREEN"
                    detalhes = f"Over {total} > {linha}"
                elif "UNDER" in selecao.upper() and total < linha:
                    status = "GREEN"
                    detalhes = f"Under {total} < {linha}"
                elif total == linha:
                    status = "REEMBOLSO"
                    detalhes = f"Push {total}"
            except:
                pass
    
    elif aposta['esporte'] == 'basketball':
        if "H2H" in mercado or "VENCEDOR" in mercado:
            if h_team in selecao and h_score > a_score:
                status = "GREEN"
                detalhes = f"{h_team} venceu {h_score}x{a_score}"
            elif a_team in selecao and a_score > h_score:
                status = "GREEN"
                detalhes = f"{a_team} venceu {a_score}x{h_score}"
        
        elif "SPREAD" in mercado or "HANDICAP" in mercado:
            try:
                linha = float(''.join(c for c in selecao if c.isdigit() or c in '.-'))
                if h_team in selecao:
                    resultado = h_score + linha - a_score
                    time_apostado = h_team
                else:
                    resultado = a_score + linha - h_score
                    time_apostado = a_team
                
                if resultado > 0:
                    status = "GREEN"
                    detalhes = f"{time_apostado} cobriu {linha}"
                elif resultado == 0:
                    status = "REEMBOLSO"
                    detalhes = "Push spread"
                else:
                    detalhes = f"{time_apostado} não cobriu"
            except:
                pass
        
        elif "TOTAL" in mercado or "PONTOS" in mercado:
            try:
                linha = float(''.join(c for c in selecao if c.isdigit() or c == '.'))
                if "OVER" in selecao.upper() and total > linha:
                    status = "GREEN"
                    detalhes = f"Over {total} > {linha}"
                elif "UNDER" in selecao.upper() and total < linha:
                    status = "GREEN"
                    detalhes = f"Under {total} < {linha}"
                elif total == linha:
                    status = "REEMBOLSO"
                    detalhes = f"Push {total}"
            except:
                pass
    
    if status == "GREEN":
        lucro = (stake * odd) - stake
    elif status == "REEMBOLSO":
        lucro = 0
    else:
        lucro = -stake
    
    return status, lucro, detalhes

# ==========================================
# ANÁLISE ESTATÍSTICA
# ==========================================

def calcular_metricas(apostas: List[sqlite3.Row]) -> MetricasPeriodo:
    if not apostas:
        return MetricasPeriodo(0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    
    total = len(apostas)
    greens = sum(1 for a in apostas if a['status'] == 'GREEN')
    reds = sum(1 for a in apostas if a['status'] == 'RED')
    voids = sum(1 for a in apostas if a['status'] == 'REEMBOLSO')
    lucro_total = sum(a['lucro'] for a in apostas)
    investimento = sum(a['stake'] for a in apostas)
    winrate = (greens / (greens + reds) * 100) if (greens + reds) > 0 else 0
    roi = (lucro_total / investimento * 100) if investimento > 0 else 0
    odds = [a['odd'] for a in apostas if a['odd']]
    media_odd = statistics.mean(odds) if odds else 0
    evs = [a['ev'] for a in apostas if a['ev']]
    media_ev = statistics.mean(evs) if evs else 0
    
    return MetricasPeriodo(total, greens, reds, voids, lucro_total, investimento, winrate, roi, media_odd, media_ev)

def analisar_padroes(conn: sqlite3.Connection, dias_historico: int = 14) -> List[AnalisePadrao]:
    data_corte = (datetime.now(ZoneInfo("America/Sao_Paulo")) - timedelta(days=dias_historico)).strftime('%d/%m/%Y')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM operacoes_tipster WHERE data_hora >= ? AND status != 'PENDENTE'", (data_corte,))
    apostas = cursor.fetchall()
    
    if len(apostas) < MIN_AMOSTRAS_PADRAO:
        return []
    
    analises = []
    
    # Por mercado
    mercados = defaultdict(list)
    for a in apostas:
        mercados[a['mercado']].append(a)
    for mercado, lista in mercados.items():
        if len(lista) >= MIN_AMOSTRAS_PADRAO:
            m = calcular_metricas(lista)
            if m.roi < LIMITE_ROI_ALERTA:
                analises.append(AnalisePadrao('mercado', mercado, len(lista), m.winrate, m.roi, m.lucro_total, 'negativa', f"Revisar {mercado} (ROI: {m.roi:.1f}%)"))
            elif m.roi > 15:
                analises.append(AnalisePadrao('mercado', mercado, len(lista), m.winrate, m.roi, m.lucro_total, 'positiva', f"Priorizar {mercado} (ROI: {m.roi:.1f}%)"))
    
    # Por liga
    ligas = defaultdict(list)
    for a in apostas:
        ligas[a['liga']].append(a)
    for liga, lista in ligas.items():
        if len(lista) >= MIN_AMOSTRAS_PADRAO:
            m = calcular_metricas(lista)
            if m.winrate < LIMITE_WINRATE_ALERTA:
                analises.append(AnalisePadrao('liga', liga, len(lista), m.winrate, m.roi, m.lucro_total, 'negativa', f"Pausar {liga} (Winrate: {m.winrate:.1f}%)"))
            elif m.winrate > 60 and m.roi > 10:
                analises.append(AnalisePadrao('liga', liga, len(lista), m.winrate, m.roi, m.lucro_total, 'positiva', f"Focar em {liga} (Winrate: {m.winrate:.1f}%)"))
    
    return analises

# ==========================================
# AUDITORIA
# ==========================================

async def rotina_auditoria_completa(session: aiohttp.ClientSession):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM operacoes_tipster WHERE status='PENDENTE'")
    pendentes = cursor.fetchall()
    
    if not pendentes:
        print("☕ Nenhuma aposta pendente.")
        conn.close()
        return
    
    print(f"🔍 Auditando {len(pendentes)} apostas...")
    
    esportes = set(p['esporte'] for p in pendentes)
    resultados_por_esporte = {}
    
    for esporte in esportes:
        resultados = await obter_resultados_api(session, esporte)
        if resultados:
            resultados_por_esporte[esporte] = resultados
    
    atualizadas = []
    for aposta in pendentes:
        esporte = aposta['esporte']
        if esporte not in resultados_por_esporte:
            continue
        
        for placar in resultados_por_esporte[esporte]:
            if not placar.get("completed"):
                continue
            
            if aposta['id_aposta'].startswith(placar['id']):
                status, lucro, detalhes = resolver_aposta_completa(aposta, placar)
                if status != "PENDENTE":
                    agora = datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat()
                    cursor.execute(
                        "UPDATE operacoes_tipster SET status=?, lucro=?, processado_em=?, justificativa=COALESCE(justificativa,'') || ' | ' || ? WHERE id_aposta=?",
                        (status, lucro, agora, detalhes, aposta['id_aposta'])
                    )
                    atualizadas.append((aposta, status, lucro))
                    print(f"  ✅ {aposta['jogo']}: {status}")
                break
    
    conn.commit()
    
    if atualizadas:
        padroes = analisar_padroes(conn)
        for padrao in padroes:
            if padrao.tendencia == 'negativa':
                cursor.execute(
                    "SELECT id FROM alertas_sistema WHERE categoria_afetada=? AND tipo=? AND resolvido=0",
                    (padrao.categoria, padrao.item)
                )
                if not cursor.fetchone():
                    cursor.execute(
                        "INSERT INTO alertas_sistema (data_alerta, tipo, mensagem, categoria_afetada, gravidade) VALUES (?, ?, ?, ?, ?)",
                        (datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(), padrao.item, padrao.sugestao, padrao.categoria, 'ALTA' if padrao.roi < -20 else 'MÉDIA')
                    )
        conn.commit()
        
        alertas_novos = [p for p in padroes if p.tendencia == 'negativa']
        if alertas_novos:
            await enviar_alertas(session, alertas_novos)
    
    conn.close()
    print(f"✅ {len(atualizadas)} apostas atualizadas.")

async def enviar_alertas(session: aiohttp.ClientSession, alertas: List[AnalisePadrao]):
    texto = "🚨 <b>ALERTAS DO SISTEMA</b>\n\nPadrões detectados:\n\n"
    for alerta in alertas[:5]:
        emoji = "🔴" if alerta.roi < -20 else "🟡"
        texto += f"{emoji} <b>{alerta.categoria.upper()}:</b> {alerta.item}\nAmostras: {alerta.amostras} | Winrate: {alerta.winrate:.1f}% | ROI: {alerta.roi:.1f}%\n💡 {alerta.sugestao}\n\n"
    texto += "⚠️ <i>Ajustar filtros dos bots conforme sugestões.</i>"
    await enviar_telegram_async(session, texto)

# ==========================================
# RELATÓRIOS
# ==========================================

async def gerar_relatorio_diario(session: aiohttp.ClientSession):
    data_alvo = (datetime.now(ZoneInfo("America/Sao_Paulo")) - timedelta(days=1)).strftime('%d/%m/%Y')
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM operacoes_tipster WHERE data_hora=? AND status!='PENDENTE'", (data_alvo,))
    apostas_dia = cursor.fetchall()
    
    if not apostas_dia:
        await enviar_telegram_async(session, f"📊 <b>RELATÓRIO DIÁRIO ({data_alvo})</b>\n\nNenhuma aposta finalizada.")
        conn.close()
        return
    
    metricas = calcular_metricas(apostas_dia)
    futebol = [a for a in apostas_dia if a['esporte'] == 'soccer']
    basquete = [a for a in apostas_dia if a['esporte'] == 'basketball']
    m_fut = calcular_metricas(futebol)
    m_bas = calcular_metricas(basquete)
    
    padroes = analisar_padroes(conn, dias_historico=7)
    oportunidades = [p for p in padroes if p.tendencia == 'positiva']
    problemas = [p for p in padroes if p.tendencia == 'negativa']
    
    emoji = "💰" if metricas.lucro_total >= 0 else "🩸"
    
    texto = (
        f"📊 <b>RELATÓRIO DIÁRIO SINDICATO ({data_alvo})</b>\n\n"
        f"<b>📈 RESUMO GERAL</b>\n"
        f"Total: {metricas.total_apostas} | ✅ Greens: {metricas.greens} | ❌ Reds: {metricas.reds} | 🔄 Void: {metricas.voids}\n"
        f"🎯 Winrate: {metricas.winrate:.1f}% | 💵 Investido: {metricas.investimento:.2f}u\n"
        f"{emoji} Resultado: {metricas.lucro_total:+.2f}u | 📊 ROI: {metricas.roi:.2f}%\n"
        f"📉 Odd média: {metricas.media_odd:.2f} | EV médio: {metricas.media_ev*100:.2f}%\n\n"
    )
    
    if futebol:
        emoji_fut = "🟢" if m_fut.lucro_total >= 0 else "🔴"
        texto += f"<b>⚽ FUTEBOL (Bot 1)</b>\nApostas: {m_fut.total_apostas} | Winrate: {m_fut.winrate:.1f}%\nResultado: {emoji_fut} {m_fut.lucro_total:+.2f}u (ROI: {m_fut.roi:.1f}%)\n\n"
    
    if basquete:
        emoji_bas = "🟢" if m_bas.lucro_total >= 0 else "🔴"
        texto += f"<b>🏀 BASQUETE (Bot 3)</b>\nApostas: {m_bas.total_apostas} | Winrate: {m_bas.winrate:.1f}%\nResultado: {emoji_bas} {m_bas.lucro_total:+.2f}u (ROI: {m_bas.roi:.1f}%)\n\n"
    
    if oportunidades:
        texto += f"<b>💎 OPORTUNIDADES (7 dias)</b>\n"
        for opp in oportunidades[:3]:
            texto += f"✨ {opp.categoria}: {opp.item} (Winrate: {opp.winrate:.1f}%, ROI: {opp.roi:.1f}%)\n"
        texto += "\n"
    
    if problemas:
        texto += f"<b>⚠️ ATENÇÃO</b>\n"
        for prob in problemas[:2]:
            texto += f"🔍 {prob.sugestao}\n"
        texto += "\n"
    
    inicio_mes = datetime.now(ZoneInfo("America/Sao_Paulo")).replace(day=1).strftime('%d/%m/%Y')
    cursor.execute("SELECT * FROM operacoes_tipster WHERE data_hora >= ? AND status!='PENDENTE'", (inicio_mes,))
    apostas_mes = cursor.fetchall()
    m_mes = calcular_metricas(apostas_mes)
    
    texto += (
        f"<b>📅 ACUMULADO DO MÊS</b>\n"
        f"Apostas: {m_mes.total_apostas} | Winrate: {m_mes.winrate:.1f}%\n"
        f"Resultado: {'💰' if m_mes.lucro_total >= 0 else '🩸'} {m_mes.lucro_total:+.2f}u | ROI: {m_mes.roi:.2f}%"
    )
    
    conn.close()
    await enviar_telegram_async(session, texto)

async def gerar_relatorio_semanal(session: aiohttp.ClientSession):
    hoje = datetime.now(ZoneInfo("America/Sao_Paulo"))
    inicio_semana = (hoje - timedelta(days=7)).strftime('%d/%m/%Y')
    
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM operacoes_tipster WHERE data_hora >= ? AND status!='PENDENTE'", (inicio_semana,))
    apostas = cursor.fetchall()
    
    if len(apostas) < 5:
        conn.close()
        return
    
    metricas = calcular_metricas(apostas)
    resultados = [a['status'] for a in apostas]
    sequencia_atual = 0
    for r in reversed(resultados):
        if r == 'GREEN':
            sequencia_atual += 1
        else:
            break
    
    dias = defaultdict(list)
    for a in apostas:
        dias[a['data_hora']].append(a)
    lucro_por_dia = {d: sum(a['lucro'] for a in lista) for d, lista in dias.items()}
    melhor_dia = max(lucro_por_dia.items(), key=lambda x: x[1])
    pior_dia = min(lucro_por_dia.items(), key=lambda x: x[1])
    
    texto = (
        f"📈 <b>RELATÓRIO SEMANAL</b>\n\n"
        f"<b>Período:</b> {inicio_semana} a {hoje.strftime('%d/%m/%Y')}\n\n"
        f"<b>📊 Métricas</b>\n"
        f"Total: {metricas.total_apostas} | Winrate: {metricas.winrate:.1f}% | ROI: {metricas.roi:.2f}%\n"
        f"Lucro: {'💰' if metricas.lucro_total >= 0 else '🩸'} {metricas.lucro_total:+.2f}u\n"
        f"Sequência atual: {sequencia_atual} greens\n\n"
        f"<b>📅 Por Dia</b>\n"
        f"🟢 Melhor: {melhor_dia[0]} ({melhor_dia[1]:+.2f}u)\n"
        f"🔴 Pior: {pior_dia[0]} ({pior_dia[1]:+.2f}u)\n\n"
        f"<b>💡 Recomendações</b>\n"
    )
    
    padroes = analisar_padroes(conn, dias_historico=7)
    positivos = [p for p in padroes if p.tendencia == 'positiva']
    negativos = [p for p in padroes if p.tendencia == 'negativa']
    
    if positivos:
        texto += "✅ <b>Continuar:</b>\n"
        for p in positivos[:2]:
            texto += f"   • {p.categoria}: {p.item}\n"
    
    if negativos:
        texto += "\n⚠️ <b>Revisar:</b>\n"
        for p in negativos[:2]:
            texto += f"   • {p.categoria}: {p.item}\n"
    
    conn.close()
    await enviar_telegram_async(session, texto)

# ==========================================
# LOOP
# ==========================================

async def loop_principal():
    inicializar_banco()
    async with aiohttp.ClientSession() as session:
        while True:
            agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
            await rotina_auditoria_completa(session)
            
            if agora.hour == 9 and agora.minute < 5:
                await gerar_relatorio_diario(session)
                await asyncio.sleep(300)
            
            if agora.weekday() == 0 and agora.hour == 10 and agora.minute < 5:
                await gerar_relatorio_semanal(session)
                await asyncio.sleep(300)
            
            await asyncio.sleep(3600)

# ==========================================
# START
# ==========================================

if __name__ == "__main__":
    asyncio.run(loop_principal())
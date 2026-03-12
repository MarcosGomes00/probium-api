"""
BOT 2 - AUDITOR MULTIPROVIDER
Compatível com Bot 1 (Futebol) e Bot 3 (Basquete)
"""
import sqlite3, aiohttp, asyncio, json, statistics, re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from collections import defaultdict

# CONFIGURAÇÕES
ODDS_API_KEYS =["6249ca36b148b2542bb433d23e4ace65a97c896b7dc3b93c79b4a6715b29ea7d","b29dcd347f5f26ddebb469eaa9e5f98fb75ca20be03cc47117027604d0a9f029","528e79310c9161f769a282b8d2aa61be2bb332e0cc036a51e44acee5ca7bd66f"]
BALLDONTLIE_KEYS =["a8d9ab5d-7c93-469a-8c3a-924fd4e5e7b4","8033f045-a2b3-47c6-919a-9141145c742c","3ddaee43-d801-4559-84fd-e233e8f4bb9c","afaca1cf-3bbe-47cc-93f5-6e7a1adfd195","d1559bc7-3ceb-4c0d-8171-0d2298988cf5"]
TELEGRAM_TOKENS = {"bot1":"8725909088:AAGQMNr-9RVQB7hWmePCLmm0GwaGuzOVy-A","bot2":"8185027087:AAH1JQJKtlWy_oUQpAvqvHEsFIVOK3ScYBc","bot3":"8413563055:AAGyovCDMJOxiAukTbXwaJPm3ZDckIf7qJU"}
TELEGRAM_TOKEN = TELEGRAM_TOKENS["bot2"]
CHAT_ID_ADMIN = "-1003814625223"
DB_FILE = "probum.db"

@dataclass
class ProvedorHealth:
    latencias: List[float] = field(default_factory=list)
    erros_consecutivos: int = 0
    score: float = 100.0
    def registrar_sucesso(self, latencia_ms: float):
        self.latencias.append(latencia_ms)
        if len(self.latencias) > 10: self.latencias.pop(0)
        self.erros_consecutivos = 0
        self.score = min(100.0, self.score + 10.0)
    def registrar_erro(self):
        self.erros_consecutivos += 1
        self.score = max(0.0, self.score - (15 * self.erros_consecutivos))
    def esta_saudavel(self): return self.score > 30 and self.erros_consecutivos < 3

class APIProviderManager:
    PRIORIDADE_PROVEDORES =["odds_api","balldontlie"]
    def __init__(self):
        self.chaves_por_provedor = {"odds_api": ODDS_API_KEYS, "balldontlie": BALLDONTLIE_KEYS}
        self.health_por_provedor = {p: ProvedorHealth() for p in self.PRIORIDADE_PROVEDORES}
        self.provedor_atual_idx = 0
    def get_provedor_atual(self):
        disponiveis =[p for p in self.PRIORIDADE_PROVEDORES if p not in provedores_falhos and self.health_por_provedor[p].esta_saudavel()]
        if not disponiveis: disponiveis =[p for p in self.PRIORIDADE_PROVEDORES if p not in provedores_falhos]
        if not disponiveis: return None
        disponiveis.sort(key=lambda p: self.health_por_provedor[p].score, reverse=True)
        return disponiveis[0]

provider_manager = APIProviderManager()
provedores_falhos = set()
last_request_time = 0

async def rate_limit():
    global last_request_time
    import time
    agora = time.time()
    if agora - last_request_time < 1.0:
        await asyncio.sleep(1.0 - (agora - last_request_time))
    last_request_time = time.time()

async def enviar_telegram_async(session, texto):
    for token in[TELEGRAM_TOKENS["bot2"], TELEGRAM_TOKENS["bot1"], TELEGRAM_TOKENS["bot3"]]:
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {"chat_id": CHAT_ID_ADMIN, "text": texto, "parse_mode": "HTML"}
            async with session.post(url, json=payload, timeout=10) as r:
                if r.status == 200: return True
        except: continue
    return False

def inicializar_banco():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS operacoes_tipster (
            id_aposta TEXT PRIMARY KEY, esporte TEXT, jogo TEXT, liga TEXT,
            mercado TEXT, selecao TEXT, odd REAL, prob REAL, ev REAL,
            stake REAL DEFAULT 1.5, status TEXT DEFAULT 'PENDENTE', lucro REAL DEFAULT 0,
            data_hora TEXT, pinnacle_odd REAL, ranking_score REAL, nivel_confianca TEXT,
            justificativa TEXT, stats_home TEXT, stats_away TEXT, mercados_sugeridos TEXT,
            horario_envio TEXT, tier_liga REAL, linha REAL, processado_em TEXT, fonte_dados TEXT
        )""")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON operacoes_tipster(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_esporte ON operacoes_tipster(esporte)")
    conn.commit()
    conn.close()

def extrair_linha(selecao):
    nums = re.findall(r'-?\d+\.\d+|-?\d+', str(selecao))
    return float(nums[0]) if nums else None

def identificar_time(selecao, home, away):
    s, h, a = str(selecao).lower(), home.lower(), away.lower()
    if h in s or any(p in s for p in h.split()): return home
    if a in s or any(p in s for p in a.split()): return away
    return None

def resolver_aposta(aposta, placar):
    esporte, mercado = aposta['esporte'], str(aposta['mercado']).upper()
    selecao, odd, stake = str(aposta['selecao']).upper(), aposta['odd'], aposta['stake']
    h_team = placar.get("home_team", "")
    a_team = placar.get("away_team", "")
    scores = placar.get("scores",[])
    
    # CORREÇÃO APLICADA AQUI: Fechamento dos parênteses da função int()
    h_score = int(next((s.get("score", 0) for s in scores if s.get("name") == h_team), 0)) if scores else 0
    a_score = int(next((s.get("score", 0) for s in scores if s.get("name") == a_team), 0)) if scores else 0
    total = h_score + a_score

    if esporte == 'soccer':
        if any(m in mercado for m in ["H2H", "VENCEDOR", "1X2"]):
            if selecao == "1" and h_score > a_score: return "GREEN", (stake * odd) - stake, f"{h_team} venceu"
            if selecao == "2" and a_score > h_score: return "GREEN", (stake * odd) - stake, f"{a_team} venceu"
            if selecao == "X" and h_score == a_score: return "GREEN", (stake * odd) - stake, "Empate"
            return "RED", -stake, f"Placar: {h_score}x{a_score}"
        elif "BTTS" in mercado or "AMBAS" in mercado:
            if "SIM" in selecao and h_score > 0 and a_score > 0: return "GREEN", (stake * odd) - stake, "Ambas marcaram"
            if "NÃO" in selecao and (h_score == 0 or a_score == 0): return "GREEN", (stake * odd) - stake, "Não ambas"
            return "RED", -stake, f"Resultado: {h_score}x{a_score}"
        elif "TOTAL" in mercado or "GOLS" in mercado:
            linha = extrair_linha(selecao) or aposta.get('linha')
            if linha:
                if "OVER" in selecao and total > linha: return "GREEN", (stake * odd) - stake, f"Over {total}>{linha}"
                if "UNDER" in selecao and total < linha: return "GREEN", (stake * odd) - stake, f"Under {total}<{linha}"
                if total == linha: return "REEMBOLSO", 0, f"Push {total}"
                return "RED", -stake, f"Total {total}"

    elif esporte == 'basketball':
        if any(m in mercado for m in["H2H", "VENCEDOR"]):
            time_ap = identificar_time(selecao, h_team, a_team)
            if time_ap == h_team and h_score > a_score: return "GREEN", (stake * odd) - stake, f"{h_team} venceu"
            if time_ap == a_team and a_score > h_score: return "GREEN", (stake * odd) - stake, f"{a_team} venceu"
            return "RED", -stake, f"Placar: {h_score}x{a_score}"
        elif "SPREAD" in mercado or "HANDICAP" in mercado:
            linha = extrair_linha(selecao) or aposta.get('linha')
            if linha is not None:
                time_ap = identificar_time(selecao, h_team, a_team) or h_team
                if time_ap == h_team:
                    res = h_score + linha - a_score
                    if res > 0: return "GREEN", (stake * odd) - stake, f"Handicap coberto"
                    if res == 0: return "REEMBOLSO", 0, "Push"
                    return "RED", -stake, "Handicap não coberto"
        elif "TOTAL" in mercado or "PONTOS" in mercado:
            linha = extrair_linha(selecao) or aposta.get('linha')
            if linha:
                if "OVER" in selecao and total > linha: return "GREEN", (stake * odd) - stake, f"Over {total}>{linha}"
                if "UNDER" in selecao and total < linha: return "GREEN", (stake * odd) - stake, f"Under {total}<{linha}"
                if total == linha: return "REEMBOLSO", 0, f"Push {total}"
                return "RED", -stake, f"Total {total}"

    return "PENDENTE", 0, f"Não resolvido: {mercado}"

async def obter_resultados_balldontlie(session):
    if not BALLDONTLIE_KEYS: return[]
    for chave in BALLDONTLIE_KEYS:
        try:
            await rate_limit()
            ontem = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
            hoje = datetime.now().strftime('%Y-%m-%d')
            url = "https://api.balldontlie.io/v1/games"
            headers = {"Authorization": chave}
            params = {"start_date": ontem, "end_date": hoje, "per_page": 100}
            async with session.get(url, headers=headers, params=params, timeout=15) as r:
                if r.status == 200:
                    data = await r.json()
                    return [{"id": str(g["id"]), "completed": True,
                            "home_team": g["home_team"]["full_name"],
                            "away_team": g["visitor_team"]["full_name"],
                            "scores": [{"name": g["home_team"]["full_name"], "score": g["home_team_score"]},
                                      {"name": g["visitor_team"]["full_name"], "score": g["visitor_team_score"]}]}
                           for g in data.get("data",[]) if g.get("status") == "Final"]
        except: continue
    return[]

async def obter_resultados_odds_api(session, sport_key):
    for chave in ODDS_API_KEYS:
        try:
            await rate_limit()
            url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/scores/"
            params = {"apiKey": chave, "daysFrom": 3, "dateFormat": "iso"}
            async with session.get(url, params=params, timeout=15) as r:
                if r.status == 200: return await r.json()
        except: continue
    return[]

async def auditoria_completa(session):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM operacoes_tipster WHERE status='PENDENTE'")
    pendentes = cursor.fetchall()

    if not pendentes:
        print("☕ Nenhuma aposta pendente")
        conn.close()
        return

    futebol = [p for p in pendentes if p['esporte'] == 'soccer']
    basquete = [p for p in pendentes if p['esporte'] == 'basketball']
    print(f"🔍 Auditando: {len(futebol)} Futebol + {len(basquete)} Basquete")

    resultados =[]
    if futebol: resultados.extend(await obter_resultados_odds_api(session, "soccer_epl"))
    if basquete: resultados.extend(await obter_resultados_balldontlie(session))

    resultados_por_id = {r['id']: r for r in resultados}
    atualizadas = 0

    for aposta in pendentes:
        jogo_id = aposta['id_aposta'].split("_")[0]
        placar = resultados_por_id.get(jogo_id)

        if not placar:
            for r in resultados:
                if r['home_team'].lower() in aposta['jogo'].lower() and r['away_team'].lower() in aposta['jogo'].lower():
                    placar = r
                    break

        if not placar or not placar.get("completed"): continue

        status, lucro, detalhes = resolver_aposta(aposta, placar)
        if status != "PENDENTE":
            agora = datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat()
            cursor.execute("UPDATE operacoes_tipster SET status=?, lucro=?, processado_em=?, justificativa=COALESCE(justificativa,'') || ' | ' || ? WHERE id_aposta=?",
                         (status, lucro, agora, detalhes, aposta['id_aposta']))
            atualizadas += 1
            emoji = "✅" if status == "GREEN" else "🔄" if status == "REEMBOLSO" else "❌"
            print(f"  {emoji} {aposta['jogo'][:30]}: {status}")

    conn.commit()
    conn.close()
    print(f"✅ {atualizadas} apostas atualizadas")

async def relatorio_diario(session):
    ontem = (datetime.now(ZoneInfo("America/Sao_Paulo")) - timedelta(days=1)).strftime('%d/%m/%Y')
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM operacoes_tipster WHERE data_hora=? AND status!='PENDENTE'", (ontem,))
    apostas = cursor.fetchall()
    conn.close()

    if not apostas:
        await enviar_telegram_async(session, f"📊 {ontem}: Sem apostas finalizadas")
        return

    def calc_metrics(lista):
        if not lista: return {"total": 0, "greens": 0, "reds": 0, "lucro": 0, "roi": 0, "wr": 0}
        greens = sum(1 for a in lista if a['status'] == 'GREEN')
        reds = sum(1 for a in lista if a['status'] == 'RED')
        lucro = sum(a['lucro'] for a in lista)
        inv = sum(a['stake'] for a in lista)
        return {"total": len(lista), "greens": greens, "reds": reds, "lucro": lucro,
                "roi": (lucro/inv*100) if inv else 0, "wr": (greens/(greens+reds)*100) if (greens+reds) else 0}

    geral = calc_metrics(apostas)
    fut = calc_metrics([a for a in apostas if a['esporte'] == 'soccer'])
    bas = calc_metrics([a for a in apostas if a['esporte'] == 'basketball'])

    texto = f"""📊 <b>RELATÓRIO {ontem}</b>

<b>Geral:</b> {geral['total']} apostas | WR: {geral['wr']:.1f}% | ROI: {geral['roi']:.1f}%
Lucro: {'💰' if geral['lucro'] >= 0 else '🩸'} {geral['lucro']:+.2f}u

⚽ <b>Futebol:</b> {fut['total']} | WR: {fut['wr']:.1f}% | {'💰' if fut['lucro'] >= 0 else '🩸'} {fut['lucro']:+.2f}u
🏀 <b>Basquete:</b> {bas['total']} | WR: {bas['wr']:.1f}% | {'💰' if bas['lucro'] >= 0 else '🩸'} {bas['lucro']:+.2f}u"""

    await enviar_telegram_async(session, texto)

async def main():
    inicializar_banco()
    print("🚀 Bot Auditor iniciado (Futebol + Basquete)")

    async with aiohttp.ClientSession() as session:
        while True:
            agora = datetime.now(ZoneInfo("America/Sao_Paulo"))

            # Auditoria a cada hora
            await auditoria_completa(session)

            # Relatório às 9h
            if agora.hour == 9 and agora.minute < 5:
                await relatorio_diario(session)
                await asyncio.sleep(300)

            print(f"💤 Próxima auditoria em 1h ({agora.strftime('%H:%M')})")
            await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
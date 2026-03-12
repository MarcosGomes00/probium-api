import asyncio
import aiohttp
import sqlite3
import unicodedata
import time
import json
import heapq
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple
import statistics
from collections import defaultdict
import random

# ==========================================
# CONFIGURAÇÕES BOT MULTIPROVIDER OTIMIZADO
# ==========================================

# ==========================================
# CHAVES DE API - VALIDADAS E ORGANIZADAS
# ==========================================

# 1. ODDS API (Odds-API.io) - 3 chaves
ODDS_API_KEYS = [
    "6249ca36b148b2542bb433d23e4ace65a97c896b7dc3b93c79b4a6715b29ea7d",
    "b29dcd347f5f26ddebb469eaa9e5f98fb75ca20be03cc47117027604d0a9f029",
    "528e79310c9161f769a282b8d2aa61be2bb332e0cc036a51e44acee5ca7bd66f"
]

# 2. Sports Game Odds (SGO) - 2 chaves
SGO_API_KEYS = [
    "e38185eb8b9eff32802ff016db544dc3",
    "2b8b25840b9605c1133845549d08b879"
]

# 3. API-Football (API-Sports) - 3 chaves (100 req/dia cada)
API_FOOTBALL_KEYS = [
    "da86ad79bf29f8ec19e1addb90247771",
    "4671a78ca6443a7970d2ed8efe4cbdba",
    "54e4ec4343a1abe56fe74a2eabc58ff7"
]

# 4. Sportmonks - 3 chaves (180 req/hora cada)
SPORTMONKS_KEYS = [
    "J2b3qS2pn660ss8pJUhTijsHHMmbDPQuxN3rnHhO7nnsUrI8qctzpla1LwQU",
    "rEpIQOEpH6QCHPGzqBBcoarRTZbtuHM1cIyNqOZP86CU34qEjMMT2gGtfD4s",
    "G62dXIQwZNuSpg0Fz2Ax8ngOdWpSihYIHtB8mMHN9K0ge8btuby665AqDr9N"
]

# 5. The Odds Token (OddsPapi) - 8 chaves (duplicada removida)
THE_ODDS_TOKEN_KEYS = [
    "b668851102c3e0a56c33220161c029ec",
    "0d43575dd39e175ba670fb91b2230442",
    "d32378e66e89f159688cc2239f38a6a4",
    "713146de690026b224dd8bbf0abc0339",  # Apenas uma instância
    "wk_9973be016f72a4a9775eafaefbd71740",
    "0ecb237829d0f800181538e1a4fa2494",
    "5ee1c6a8c611b6c3d6aff8043764555f",
    "4790419cc795932ffaeb0152fa5818c8"
]

# 6. The Odds API (Legado - backup) - 5 chaves
THE_ODDS_API_LEGACY_KEYS = [
    "6a1c0078b3ed09b42fbacee8f07e7cc3",
    "4949c49070dd3eff2113bd1a07293165",
    "0ecb237829d0f800181538e1a4fa2494",
    "4790419cc795932ffaeb0152fa5818c8",
    "5ee1c6a8c611b6c3d6aff8043764555f"
]

# 7. SportsDB (sportsdb.dev) - 4 chaves
SPORTSDB_KEYS = [
    "f8W9DfG71LPWMeU2TxkMtK1PEmWVwGzWW2B1Lmk9",
    "z7Dzdk5NlGtFvg5SqfL1IZWGkjOkXnOsv7tiPRrS",
    "ftAAx0FNerTm0lFMxFnWmxEbFKn7BSEMF83yosTf",
    "w1SolKpreujO7wmAKJmrW1lvfB7zK3Vv6ORnFc1t"
]

# 8. BallDontLie API (NOVO - NBA) - 5 chaves
BALLDONTLIE_KEYS = [
    "a8d9ab5d-7c93-469a-8c3a-924fd4e5e7b4",
    "8033f045-a2b3-47c6-919a-9141145c742c",
    "3ddaee43-d801-4559-84fd-e233e8f4bb9c",
    "afaca1cf-3bbe-47cc-93f5-6e7a1adfd195",
    "d1559bc7-3ceb-4c0d-8171-0d2298988cf5"
]

# 9. iSport API - 2 chaves (adicionadas mas marcadas como não testadas)
ISPORT_KEYS = [
    "Gen4hwFLN6bWTFlX",
    "edKqegQiRBfg2Vm6"
]

# Configurações de Tokens do Telegram
TELEGRAM_TOKENS = {
    "bot1": "8725909088:AAGQMNr-9RVQB7hWmePCLmm0GwaGuzOVy-A",
    "bot2": "8185027087:AAH1JQJKtlWy_oUQpAvqvHEsFIVOK3ScYBc",
    "bot3": "8413563055:AAGyovCDMJOxiAukTbXwaJPm3ZDckIf7qJU"
}

# Usando Bot1 como principal
TELEGRAM_TOKEN = TELEGRAM_TOKENS["bot1"]
CHAT_ID = "-1003814625223"
DB_FILE = "probum.db"

SCAN_INTERVAL = 21600  # 6 horas
REQUEST_DELAY = 1.5  # Segundos entre requisições

# Limites por provedor (ajustados conforme documentação)
MAX_REQ_POR_CHAVE_DIA = {
    "odds_api": 2400,        # 100/hora * 24 = 2400/dia
    "sgo": 1000,             # 1.000 objetos/mês
    "api_football": 100,     # 100/dia
    "sportmonks": 4320,      # 180/hora * 24 = 4320/dia
    "the_odds_token": 500,   # Estimado conservador
    "the_odds_api_legacy": 80,
    "sportsdb": 1000,        # Estimado
    "balldontlie": 100,      # Plano free limitado
    "isport": 500            # Estimado
}

SOFT_BOOKIES = [
    "bet365", "betano", "1xbet", "draftkings", 
    "williamhill", "unibet", "888sport", "betfair_ex_eu"
]

SHARP_BOOKIE = "pinnacle"
TODAS_CASAS = SOFT_BOOKIES + [SHARP_BOOKIE]

LEAGUE_TIERS = {
    "soccer_uefa_champs_league": 1.5,
    "soccer_epl": 1.5,
    "soccer_spain_la_liga": 1.2,
    "soccer_germany_bundesliga": 1.2,
    "soccer_italy_serie_a": 1.2,
    "soccer_brazil_campeonato": 1.0,
    "soccer_conmebol_copa_libertadores": 1.0,
    "soccer_france_ligue_one": 1.0,
    "soccer_portugal_primeira_liga": 1.0,
    "soccer_brazil_copa_do_brasil": 1.0,
    "soccer_netherlands_eredivisie": 1.1,
    "soccer_england_efl_championship": 1.1,
    "soccer_mexico_ligamx": 0.9,
    "soccer_argentina_primeradivision": 0.9,
    "soccer_belgium_first_division": 1.0,
    "soccer_turkey_super_lig": 1.0,
    "soccer_denmark_superliga": 0.9,
    "soccer_austria_bundesliga": 0.9
}

LIGAS = list(LEAGUE_TIERS.keys())

# ==========================================
# ESTRUTURAS E CONTROLE
# ==========================================

@dataclass
class EstatisticasTime:
    nome: str
    ultimos_jogos: List[Dict] = field(default_factory=list)
    media_gols_marcados: float = 0.0
    media_gols_sofridos: float = 0.0
    jogos_sem_sofrer_gol: int = 0
    jogos_marcou_gol: int = 0
    over_15: float = 0.0
    over_25: float = 0.0
    btts_sim: float = 0.0
    forma: str = ""
    xg_medio: Optional[float] = None
    posicao_tabela: Optional[int] = None

@dataclass
class AnaliseJogo:
    jogo_id: str
    home_team: str
    away_team: str
    liga: str
    horario_br: datetime
    stats_home: Optional[EstatisticasTime]
    stats_away: Optional[EstatisticasTime]
    h2h: List[Dict]
    mercado_nome: str
    selecao_nome: str
    odd_bookie: float
    odd_pinnacle: float
    nome_bookie: str
    prob_justa: float
    ev_real: float
    ranking_score: float
    nivel_confianca: str
    melhor_entrada: str
    mercados_interessantes: List[str]
    fonte_dados: str = ""
    linha: Optional[float] = None

jogos_enviados = {}
api_lock = asyncio.Lock()
request_count = {}
last_request_time = 0
chaves_falhas = {}
provedores_falhos = set()

# ==========================================
# SISTEMA DE HEALTH CHECK PARA PROVEDORES
# ==========================================

@dataclass
class ProvedorHealth:
    latencias: List[float] = field(default_factory=list)
    erros_consecutivos: int = 0
    sucessos_consecutivos: int = 0
    ultimo_sucesso: datetime = field(default_factory=datetime.now)
    score: float = 100.0
    total_requisicoes: int = 0
    total_erros: int = 0
    
    def registrar_sucesso(self, latencia_ms: float):
        self.latencias.append(latencia_ms)
        if len(self.latencias) > 10:
            self.latencias.pop(0)
        self.erros_consecutivos = 0
        self.sucessos_consecutivos += 1
        self.ultimo_sucesso = datetime.now()
        self.score = min(100.0, self.score + 10.0)
        self.total_requisicoes += 1
    
    def registrar_erro(self):
        self.erros_consecutivos += 1
        self.sucessos_consecutivos = 0
        penalidade = 15 * self.erros_consecutivos
        self.score = max(0.0, self.score - penalidade)
        self.total_requisicoes += 1
        self.total_erros += 1
    
    def esta_saudavel(self) -> bool:
        return self.score > 30 and self.erros_consecutivos < 3
    
    def latencia_media(self) -> float:
        if not self.latencias:
            return 0.0
        return statistics.mean(self.latencias)
    
    def taxa_erro(self) -> float:
        if self.total_requisicoes == 0:
            return 0.0
        return (self.total_erros / self.total_requisicoes) * 100

# ==========================================
# SISTEMA DE CACHE DISTRIBUÍDO DE ODDS
# ==========================================

class OddsCache:
    def __init__(self, db_file="odds_cache_futebol.db"):
        self.db = db_file
        self.init_db()
        self.cache_hits = 0
        self.cache_misses = 0
    
    def init_db(self):
        conn = sqlite3.connect(self.db)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS odds_cache (
                jogo_id TEXT PRIMARY KEY,
                liga TEXT,
                dados_json TEXT,
                provedor TEXT,
                timestamp REAL,
                ttl INTEGER DEFAULT 300
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_liga ON odds_cache(liga)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON odds_cache(timestamp)")
        conn.commit()
        conn.close()
    
    def get(self, jogo_id: str) -> Optional[dict]:
        conn = sqlite3.connect(self.db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT dados_json, timestamp, ttl FROM odds_cache WHERE jogo_id=?",
            (jogo_id,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            dados, ts, ttl = row
            agora = datetime.now().timestamp()
            if agora - ts < ttl:
                self.cache_hits += 1
                return json.loads(dados)
        
        self.cache_misses += 1
        return None
    
    def set(self, jogo_id: str, dados: dict, provedor: str, ttl: int = 300):
        conn = sqlite3.connect(self.db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO odds_cache 
            (jogo_id, liga, dados_json, provedor, timestamp, ttl)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            jogo_id,
            dados.get("sport_key", "unknown"),
            json.dumps(dados),
            provedor,
            datetime.now().timestamp(),
            ttl
        ))
        conn.commit()
        conn.close()
    
    def limpar_expirados(self):
        conn = sqlite3.connect(self.db)
        cursor = conn.cursor()
        agora = datetime.now().timestamp()
        cursor.execute("DELETE FROM odds_cache WHERE ? - timestamp > ttl", (agora,))
        deletados = cursor.rowcount
        conn.commit()
        conn.close()
        return deletados
    
    def estatisticas(self) -> dict:
        total = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total * 100) if total > 0 else 0
        return {
            "hits": self.cache_hits,
            "misses": self.cache_misses,
            "hit_rate": hit_rate,
            "economia_requisicoes": self.cache_hits
        }

odds_cache = OddsCache()

# ==========================================
# SISTEMA DE FAILOVER MULTIPROVIDER COM ROTAÇÃO SIMULTÂNEA
# ==========================================

class APIProviderManager:
    PRIORIDADE_PROVEDORES = [
        "odds_api",
        "sgo", 
        "the_odds_token",
        "the_odds_api_legacy",
        "api_football",
        "sportmonks",
        "balldontlie",  # NBA
        "sportsdb",
        "isport"
    ]
    
    def __init__(self):
        self.chaves_por_provedor = {
            "odds_api": ODDS_API_KEYS,
            "sgo": SGO_API_KEYS,
            "api_football": API_FOOTBALL_KEYS,
            "sportmonks": SPORTMONKS_KEYS,
            "the_odds_token": THE_ODDS_TOKEN_KEYS,
            "the_odds_api_legacy": THE_ODDS_API_LEGACY_KEYS,
            "sportsdb": SPORTSDB_KEYS,
            "balldontlie": BALLDONTLIE_KEYS,
            "isport": ISPORT_KEYS
        }
        
        # Índices de rotação para cada provedor (rotação simultânea)
        self.indices_rotacao = {p: 0 for p in self.PRIORIDADE_PROVEDORES}
        
        # Contadores de uso por chave para balanceamento igualitário
        self.uso_por_chave = defaultdict(int)
        
        self.provedor_atual_idx = 0
        self.health_por_provedor = {
            p: ProvedorHealth() for p in self.PRIORIDADE_PROVEDORES
        }
        
        # Chaves validadas (serão preenchidas após teste)
        self.chaves_validadas = {p: [] for p in self.PRIORIDADE_PROVEDORES}
    
    async def validar_todas_chaves(self, session):
        """Valida todas as chaves no startup e mantém apenas as funcionais"""
        print("🔍 Iniciando validação de chaves...")
        
        for provedor, chaves in self.chaves_por_provedor.items():
            chaves_funcionais = []
            
            for chave in chaves:
                valido = await self._testar_chave(session, provedor, chave)
                if valido:
                    chaves_funcionais.append(chave)
                    print(f"  ✅ {provedor}: {chave[:8]}...{chave[-4:]} OK")
                else:
                    print(f"  ❌ {provedor}: {chave[:8]}...{chave[-4:]} FALHOU")
                await asyncio.sleep(0.5)  # Rate limit na validação
            
            self.chaves_validadas[provedor] = chaves_funcionais
            
        # Atualiza chaves por provedor apenas com as validadas
        for provedor in self.PRIORIDADE_PROVEDORES:
            if self.chaves_validadas[provedor]:
                self.chaves_por_provedor[provedor] = self.chaves_validadas[provedor]
                print(f"📊 {provedor}: {len(self.chaves_validadas[provedor])}/{len(chaves)} chaves válidas")
            else:
                print(f"⚠️ {provedor}: Nenhuma chave válida!")
    
    async def _testar_chave(self, session, provedor: str, chave: str) -> bool:
        """Testa uma chave específica"""
        try:
            if provedor == "balldontlie":
                url = "https://api.balldontlie.io/v1/games"
                headers = {"Authorization": chave}
                async with session.get(url, headers=headers, params={"per_page": 1}, timeout=10) as resp:
                    return resp.status == 200
                    
            elif provedor == "api_football":
                url = "https://v3.football.api-sports.io/status"
                headers = {"x-apisports-key": chave}
                async with session.get(url, headers=headers, timeout=10) as resp:
                    return resp.status == 200
                    
            elif provedor in ["odds_api", "the_odds_token", "the_odds_api_legacy"]:
                url = "https://api.the-odds-api.com/v4/sports/"
                params = {"apiKey": chave}
                async with session.get(url, params=params, timeout=10) as resp:
                    return resp.status == 200
                    
            elif provedor == "sportsgameodds":
                url = "https://api.sportsgameodds.com/v1/sports"
                headers = {"Authorization": f"Bearer {chave}"}
                async with session.get(url, headers=headers, timeout=10) as resp:
                    return resp.status == 200
                    
            elif provedor == "sportmonks":
                url = "https://api.sportmonks.com/v3/football/leagues"
                params = {"api_token": chave}
                async with session.get(url, params=params, timeout=10) as resp:
                    return resp.status == 200
                    
            elif provedor == "sportsdb":
                url = f"https://www.thesportsdb.com/api/v1/json/{chave}/all_leagues.php"
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return "leagues" in data
                    return False
                    
            elif provedor == "isport":
                # iSport é experimental, assume válido se não der erro de conexão
                return True
                
        except Exception as e:
            print(f"    Erro testando {provedor}: {e}")
            return False
        
        return False
    
    def get_provedor_atual(self) -> Optional[str]:
        disponiveis = [p for p in self.PRIORIDADE_PROVEDORES 
                      if p not in provedores_falhos 
                      and self.chaves_por_provedor.get(p)
                      and self.health_por_provedor.get(p, ProvedorHealth()).esta_saudavel()]
        
        if not disponiveis:
            disponiveis = [p for p in self.PRIORIDADE_PROVEDORES 
                          if p not in provedores_falhos and self.chaves_por_provedor.get(p)]
        
        if not disponiveis:
            return None
        
        # Ordena por health score
        disponiveis.sort(key=lambda p: self.health_por_provedor.get(p, ProvedorHealth()).score, reverse=True)
        return disponiveis[0]
    
    def get_proxima_chave(self, provedor: str) -> Tuple[Optional[str], int]:
        """
        Retorna a próxima chave usando rotação round-robin para uso igualitário.
        Isso garante que todas as chaves expirem por igual.
        """
        chaves = self.chaves_por_provedor.get(provedor, [])
        if not chaves:
            return None, 0
        
        # Pega o índice atual e incrementa
        idx = self.indices_rotacao[provedor] % len(chaves)
        self.indices_rotacao[provedor] = (self.indices_rotacao[provedor] + 1) % len(chaves)
        
        chave = chaves[idx]
        
        # Verifica se a chave não está marcada como falha recente
        falhas_provedor = chaves_falhas.get(provedor, {})
        ultima_falha = falhas_provedor.get(chave, 0)
        
        if (datetime.now().timestamp() - ultima_falha) > 3600:
            self.uso_por_chave[f"{provedor}_{chave}"] += 1
            return chave, idx
        
        # Se estiver falha, tenta a próxima
        tentativas = 0
        while tentativas < len(chaves):
            idx = self.indices_rotacao[provedor] % len(chaves)
            chave = chaves[idx]
            self.indices_rotacao[provedor] = (self.indices_rotacao[provedor] + 1) % len(chaves)
            
            falhas_provedor = chaves_falhas.get(provedor, {})
            ultima_falha = falhas_provedor.get(chave, 0)
            
            if (datetime.now().timestamp() - ultima_falha) > 3600:
                self.uso_por_chave[f"{provedor}_{chave}"] += 1
                return chave, idx
            
            tentativas += 1
        
        return None, 0
    
    def marcar_chave_falha(self, provedor: str, chave: str):
        if provedor not in chaves_falhas:
            chaves_falhas[provedor] = {}
        chaves_falhas[provedor][chave] = datetime.now().timestamp()
        if provedor in self.health_por_provedor:
            self.health_por_provedor[provedor].registrar_erro()
        print(f"⚠️ Chave {chave[:8]}... do {provedor} marcada como falha")
    
    def marcar_sucesso(self, provedor: str, latencia_ms: float):
        if provedor in self.health_por_provedor:
            self.health_por_provedor[provedor].registrar_sucesso(latencia_ms)
    
    def marcar_provedor_offline(self, provedor: str):
        provedores_falhos.add(provedor)
        print(f"🚫 Provedor {provedor} marcado como offline temporariamente")
        asyncio.create_task(self.reativar_provedor(provedor, 1800))
    
    async def reativar_provedor(self, provedor: str, delay: int):
        await asyncio.sleep(delay)
        if provedor in provedores_falhos:
            provedores_falhos.remove(provedor)
            if provedor in self.health_por_provedor:
                self.health_por_provedor[provedor].score = 50
            print(f"✅ Provedor {provedor} reativado")
    
    def get_health_report(self) -> str:
        linhas = ["📊 Health Check Provedores:"]
        for provedor in self.PRIORIDADE_PROVEDORES:
            if provedor in self.health_por_provedor:
                h = self.health_por_provedor[provedor]
                status = "🟢" if h.esta_saudavel() else "🔴"
                chaves_count = len(self.chaves_por_provedor.get(provedor, []))
                linhas.append(f"{status} {provedor}: Score={h.score:.0f} | Chaves={chaves_count} | Lat={h.latencia_media():.0f}ms")
        return "\n".join(linhas)
    
    def get_balanceamento_chaves(self) -> str:
        """Mostra estatísticas de uso das chaves para verificar balanceamento"""
        linhas = ["⚖️ Balanceamento de Chaves:"]
        for provedor in self.PRIORIDADE_PROVEDORES:
            chaves = self.chaves_por_provedor.get(provedor, [])
            if chaves:
                usos = [self.uso_por_chave.get(f"{provedor}_{c}", 0) for c in chaves]
                if usos:
                    avg = sum(usos) / len(usos)
                    max_dev = max(abs(u - avg) for u in usos) if len(usos) > 1 else 0
                    linhas.append(f"  {provedor}: média={avg:.1f} | desvio máx={max_dev:.0f}")
        return "\n".join(linhas)

provider_manager = APIProviderManager()

# ==========================================
# FUNÇÕES AUXILIARES
# ==========================================

def normalizar_nome(nome):
    if not isinstance(nome, str):
        return str(nome)
    return ''.join(
        c for c in unicodedata.normalize('NFD', nome)
        if unicodedata.category(c) != 'Mn'
    ).lower().strip()

async def rate_limit():
    global last_request_time
    agora = datetime.now().timestamp()
    tempo_passado = agora - last_request_time
    if tempo_passado < REQUEST_DELAY:
        await asyncio.sleep(REQUEST_DELAY - tempo_passado)
    last_request_time = datetime.now().timestamp()

def calcular_nivel_confianca(ev: float, tier_liga: float, 
                             stats_home: Optional[EstatisticasTime],
                             stats_away: Optional[EstatisticasTime]) -> str:
    score = ev * 100
    if tier_liga >= 1.5:
        score += 5
    if stats_home and stats_away:
        consistencia = abs(stats_home.over_25 - stats_away.over_25)
        if consistencia < 15:
            score += 3
    if score >= 8:
        return "🔥 Alto"
    elif score >= 5:
        return "⚡ Médio"
    return "⚠️ Baixo"

def obter_mercados_interessantes(stats_home: Optional[EstatisticasTime], 
                                  stats_away: Optional[EstatisticasTime],
                                  h2h: List[Dict]) -> List[str]:
    mercados = []
    
    if not stats_home or not stats_away:
        return mercados
    
    media_total_gols = (stats_home.media_gols_marcados + stats_home.media_gols_sofridos +
                       stats_away.media_gols_marcados + stats_away.media_gols_sofridos) / 2
    
    if media_total_gols > 2.8:
        mercados.append("Over 2.5 Gols")
    elif media_total_gols > 2.2:
        mercados.append("Over 1.5 Gols")
    elif media_total_gols < 2.0:
        mercados.append("Under 2.5 Gols")
    
    btts_media = (stats_home.btts_sim + stats_away.btts_sim) / 2
    if btts_media > 55:
        mercados.append("BTTS Sim")
    elif btts_media < 40:
        mercados.append("BTTS Não")
    
    if stats_home.forma.count('W') >= 3 and stats_away.forma.count('L') >= 3:
        mercados.append(f"Vitória {stats_home.nome}")
    elif stats_away.forma.count('W') >= 3 and stats_home.forma.count('L') >= 3:
        mercados.append(f"Vitória {stats_away.nome}")
    
    if stats_home.jogos_sem_sofrer_gol >= 3:
        mercados.append(f"Dupla Chance 1X")
    elif stats_away.jogos_sem_sofrer_gol >= 3:
        mercados.append(f"Dupla Chance X2")
    
    return mercados

# ==========================================
# BANCO DE DADOS
# ==========================================

def carregar_memoria_banco():
    global jogos_enviados
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id_aposta FROM operacoes_tipster WHERE status='PENDENTE'"
        )
        for (id_aposta,) in cursor.fetchall():
            jogos_enviados[id_aposta.split("_")[0]] = datetime.now(
                ZoneInfo("America/Sao_Paulo")
            ) + timedelta(hours=24)
        conn.close()
    except:
        pass

def salvar_aposta_banco(op, stake, analise):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        id_aposta = f"{op['jogo_id']}_{op['mercado_nome'][:4]}_{op['selecao_nome'][:4]}".replace(" ", "")
        hoje = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime('%d/%m/%Y')
        
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
                status TEXT,
                lucro REAL,
                data_hora TEXT,
                pinnacle_odd REAL,
                ranking_score REAL,
                nivel_confianca TEXT,
                stats_home TEXT,
                stats_away TEXT,
                mercados_sugeridos TEXT,
                fonte_dados TEXT,
                linha REAL
            )
        """)
        
        cursor.execute(
            """
            INSERT OR IGNORE INTO operacoes_tipster
            (id_aposta,esporte,jogo,liga,mercado,selecao,odd,prob,ev,stake,status,lucro,data_hora,pinnacle_odd,ranking_score,nivel_confianca,stats_home,stats_away,mercados_sugeridos,fonte_dados,linha)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                id_aposta, "soccer", f"{op['home_team']} x {op['away_team']}",
                op["evento"]["sport_title"], op["mercado_nome"], op["selecao_nome"],
                op["odd_bookie"], op["prob_justa"], op["ev_real"], stake, 'PENDENTE', 0, hoje,
                op["odd_pinnacle"], op["ranking_score"], analise.nivel_confianca,
                json.dumps(analise.stats_home.__dict__ if analise.stats_home else {}),
                json.dumps(analise.stats_away.__dict__ if analise.stats_away else {}),
                json.dumps(analise.mercados_interessantes),
                analise.fonte_dados,
                op.get("linha")
            )
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erro ao salvar: {e}")

# ==========================================
# TELEGRAM - MULTIBOT FAILOVER
# ==========================================

async def enviar_telegram_async(session, analise: AnaliseJogo):
    bots = [TELEGRAM_TOKENS["bot1"], TELEGRAM_TOKENS["bot2"], TELEGRAM_TOKENS["bot3"]]
    
    for token in bots:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        
        stats_txt = ""
        if analise.stats_home and analise.stats_away:
            stats_txt = (
                f"\n📊 <b>Estatísticas:</b>\n"
                f"  {analise.home_team}: {analise.stats_home.media_gols_marcados:.1f} gols/jogo | Forma: {analise.stats_home.forma}\n"
                f"  {analise.away_team}: {analise.stats_away.media_gols_marcados:.1f} gols/jogo | Forma: {analise.stats_away.forma}\n"
            )
        
        h2h_txt = ""
        if analise.h2h:
            ultimos_h2h = analise.h2h[:3]
            resultados = []
            for jogo in ultimos_h2h:
                home = jogo.get("teams", {}).get("home", {}).get("name", "")
                away = jogo.get("teams", {}).get("away", {}).get("name", "")
                gols_home = jogo.get("goals", {}).get("home", 0)
                gols_away = jogo.get("goals", {}).get("away", 0)
                resultados.append(f"{home} {gols_home}x{gols_away} {away}")
            h2h_txt = f"\n🔄 <b>Últimos H2H:</b>\n  " + "\n  ".join(resultados) + "\n"
        
        mercados_txt = "\n".join([f"  • {m}" for m in analise.mercados_interessantes[:4]]) if analise.mercados_interessantes else "  • Dados insuficientes"
        
        txt = (
            f"⚽ <b>ANÁLISE PROFISSIONAL - VALOR ENCONTRADO</b>\n"
            f"<i>Fonte: {analise.fonte_dados}</i>\n\n"
            f"🏆 <b>{analise.liga}</b>\n"
            f"⚔️ <b>Jogo:</b> {analise.home_team} x {analise.away_team}\n"
            f"⏰ <b>Horário:</b> {analise.horario_br.strftime('%d/%m %H:%M')}\n"
            f"{stats_txt}"
            f"{h2h_txt}\n"
            f"🎯 <b>Mercado Principal:</b> {analise.mercado_nome}\n"
            f"👉 <b>Entrada:</b> {analise.selecao_nome}\n"
            f"🏛️ <b>Casa:</b> {analise.nome_bookie.upper()}\n"
            f"📈 <b>Odd:</b> {analise.odd_bookie:.2f} (Pinnacle: {analise.odd_pinnacle:.2f})\n"
            f"📊 <b>EV:</b> +{analise.ev_real*100:.1f}% | <b>Prob Real:</b> {analise.prob_justa*100:.1f}%\n\n"
            f"💡 <b>Mercados Interessantes:</b>\n{mercados_txt}\n\n"
            f"✅ <b>Melhor Entrada:</b> {analise.selecao_nome} @ {analise.odd_bookie:.2f}\n"
            f"{analise.nivel_confianca} <b>Nível de Confiança</b>\n\n"
            f"⚠️ Aposte com responsabilidade. Análise baseada em probabilidade e estatística."
        )
        
        payload = {
            "chat_id": CHAT_ID,
            "text": txt,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        
        try:
            async with session.post(url, json=payload, timeout=10) as resp:
                if resp.status == 200:
                    return True
                else:
                    print(f"⚠️ Bot falhou com status {resp.status}, tentando próximo...")
        except Exception as e:
            print(f"Erro Telegram com bot: {e}")
    
    print("❌ Todos os bots falharam!")
    return False

# ==========================================
# REQUISIÇÕES MULTIPROVIDER COM FAILOVER E ROTAÇÃO SIMULTÂNEA
# ==========================================

async def fazer_requisicao_odds_multiprovider(session, liga_key: str, tentativas_max: int = 10):
    """
    Faz requisição com rotação simultânea de chaves.
    Cada requisição usa a próxima chave em ordem round-robin.
    """
    for tentativa in range(tentativas_max):
        provedor = provider_manager.get_provedor_atual()
        
        if not provedor:
            print("❌ Nenhum provedor disponível! Aguardando 5 minutos...")
            await asyncio.sleep(300)
            provedores_falhos.clear()
            continue
        
        # Usa o novo sistema de rotação simultânea
        chave, idx = provider_manager.get_proxima_chave(provedor)
        
        if not chave:
            print(f"⚠️ Todas as chaves do {provedor} esgotadas/falhas")
            provider_manager.marcar_provedor_offline(provedor)
            continue
        
        await rate_limit()
        
        inicio_req = time.time()
        url, parametros = construir_requisicao_provedor(provedor, liga_key, chave)
        
        try:
            hoje = datetime.now().strftime("%Y%m%d")
            chave_hoje = f"{provedor}_{chave}_{hoje}"
            
            async with api_lock:
                request_count[chave_hoje] = request_count.get(chave_hoje, 0) + 1
                
                if request_count[chave_hoje] >= MAX_REQ_POR_CHAVE_DIA.get(provedor, 100):
                    print(f"⚠️ Limite diário atingido para {provedor} chave {idx}")
                    provider_manager.marcar_chave_falha(provedor, chave)
                    continue
            
            async with session.get(url, params=parametros, timeout=15) as r:
                latencia_ms = (time.time() - inicio_req) * 1000
                
                if r.status == 200:
                    dados = await r.json()
                    provider_manager.marcar_sucesso(provedor, latencia_ms)
                    print(f"✅ Dados obtidos via {provedor} (chave {idx}) em {latencia_ms:.0f}ms")
                    return dados, provedor
                elif r.status in [401, 429, 403]:
                    print(f"⚠️ {provedor} retornou {r.status} na chave {idx}")
                    provider_manager.marcar_chave_falha(provedor, chave)
                else:
                    print(f"⚠️ {provedor} retornou {r.status}, tentando próximo...")
                    provider_manager.health_por_provedor[provedor].registrar_erro()
                    
        except asyncio.TimeoutError:
            print(f"⏱️ Timeout no {provedor}")
            provider_manager.health_por_provedor[provedor].registrar_erro()
        except Exception as e:
            print(f"Erro no {provedor}: {e}")
            provider_manager.health_por_provedor[provedor].registrar_erro()
        
        await asyncio.sleep(0.5)
    
    return None, None

def construir_requisicao_provedor(provedor: str, liga_key: str, chave: str) -> Tuple[str, Dict]:
    if provedor == "odds_api":
        return (
            f"https://api.the-odds-api.com/v4/sports/{liga_key}/odds/",
            {
                "apiKey": chave,
                "regions": "eu",
                "markets": "h2h,btts,totals",
                "bookmakers": ",".join(TODAS_CASAS)
            }
        )
    
    elif provedor == "sgo":
        return (
            "https://api.sportsgameodds.com/v1/events",
            {
                "apiKey": chave,
                "sport": "soccer",
                "league": liga_key.replace("soccer_", ""),
                "markets": "h2h,btts,totals"
            }
        )
    
    elif provedor == "api_football":
        return (
            "https://v3.football.api-sports.io/odds",
            {
                "league": mapear_liga_api_football(liga_key),
                "season": datetime.now().year,
                "bookmaker": "1"
            }
        )
    
    elif provedor == "sportmonks":
        return (
            f"https://api.sportmonks.com/v3/football/fixtures/upcoming",
            {
                "api_token": chave,
                "leagues": mapear_liga_sportmonks(liga_key),
                "include": "odds"
            }
        )
    
    elif provedor == "balldontlie":
        # BallDontLie é para NBA, não futebol - retorna vazio para manter compatibilidade
        return (
            "https://api.balldontlie.io/v1/games",
            {
                "Authorization": chave,
                "per_page": 25
            }
        )
    
    elif provedor in ["the_odds_token", "the_odds_api_legacy"]:
        return (
            f"https://api.the-odds-api.com/v4/sports/{liga_key}/odds/",
            {
                "apiKey": chave,
                "regions": "eu",
                "markets": "h2h,btts,totals",
                "bookmakers": ",".join(TODAS_CASAS)
            }
        )
    
    else:
        return (
            f"https://api.the-odds-api.com/v4/sports/{liga_key}/odds/",
            {"apiKey": chave, "regions": "eu", "markets": "h2h"}
        )

def mapear_liga_api_football(liga_key: str) -> str:
    mapeamento = {
        "soccer_uefa_champs_league": "2",
        "soccer_epl": "39",
        "soccer_spain_la_liga": "140",
        "soccer_germany_bundesliga": "78",
        "soccer_italy_serie_a": "135",
        "soccer_brazil_campeonato": "71",
        "soccer_france_ligue_one": "61"
    }
    return mapeamento.get(liga_key, "39")

def mapear_liga_sportmonks(liga_key: str) -> str:
    mapeamento = {
        "soccer_uefa_champs_league": "2",
        "soccer_epl": "8",
        "soccer_spain_la_liga": "564",
        "soccer_germany_bundesliga": "82",
        "soccer_italy_serie_a": "384",
        "soccer_brazil_campeonato": "325"
    }
    return mapeamento.get(liga_key, "8")

def validar_futebol(odd, ev, liga):
    if not (1.40 <= odd <= 10.0):
        return False
    if ev > 0.20:
        return False
    min_ev = 0.015 if LEAGUE_TIERS.get(liga, 1.0) >= 1.2 else 0.025
    return ev >= min_ev

# ==========================================
# PROCESSAMENTO
# ==========================================

async def processar_liga_async(session, liga_key, agora_br):
    data, provedor = await fazer_requisicao_odds_multiprovider(session, liga_key)
    
    if not data or not isinstance(data, list):
        print(f"❌ Não foi possível obter dados para {liga_key}")
        return
    
    if provedor == "api_football":
        eventos = parse_api_football(data)
    elif provedor == "sportmonks":
        eventos = parse_sportmonks(data)
    else:
        eventos = data
    
    for evento in eventos:
        jogo_id = str(evento.get("id", evento.get("fixture_id", 0)))
        
        # Verifica cache primeiro
        cached = odds_cache.get(jogo_id)
        if cached:
            print(f"♻️ Jogo {jogo_id} encontrado no cache, pulando...")
            continue
        
        if jogo_id in jogos_enviados:
            continue
        
        home_team = evento.get("home_team", evento.get("home", {}).get("name", "Desconhecido"))
        away_team = evento.get("away_team", evento.get("away", {}).get("name", "Desconhecido"))
        
        commence_time = evento.get("commence_time", evento.get("date", datetime.now().isoformat()))
        try:
            horario_br = datetime.fromisoformat(
                commence_time.replace("Z", "+00:00")
            ).astimezone(ZoneInfo("America/Sao_Paulo"))
        except:
            horario_br = datetime.now(ZoneInfo("America/Sao_Paulo")) + timedelta(hours=2)
        
        minutos = (horario_br - agora_br).total_seconds() / 60
        if not (30 <= minutos <= 1440):
            continue
        
        bookmakers = extrair_bookmakers(evento, provedor)
        
        pinnacle = next((b for b in bookmakers if b.get("key") == SHARP_BOOKIE or 
                        "pinnacle" in b.get("title", "").lower()), None)
        
        if not pinnacle:
            pinnacle = next((b for b in bookmakers if any(ref in b.get("key", "") 
                          for ref in ["betfair", "matchbook", "smarkets"])), None)
        
        if not pinnacle:
            continue
        
        stats_home, stats_away, h2h = None, None, []
        
        oportunidades = []
        
        for soft in bookmakers:
            soft_key = soft.get("key", "").lower()
            if not any(sb in soft_key for sb in SOFT_BOOKIES):
                continue
            
            markets = soft.get("markets", soft.get("odds", []))
            pin_markets = pinnacle.get("markets", pinnacle.get("odds", []))
            
            for m_key in ["h2h", "btts", "totals", "1x2", "match_winner"]:
                pin_m = next((m for m in pin_markets if m.get("key") == m_key or 
                             m.get("name", "").lower() in [m_key, "match winner"]), None)
                soft_m = next((m for m in markets if m.get("key") == m_key or 
                              m.get("name", "").lower() in [m_key, "match winner"]), None)
                
                if pin_m and soft_m:
                    outcomes_pin = pin_m.get("outcomes", pin_m.get("values", []))
                    outcomes_soft = soft_m.get("outcomes", soft_m.get("values", []))
                    
                    margem = sum(1/o.get("price", o.get("odd", 999)) for o in outcomes_pin 
                                if o.get("price", o.get("odd", 0)) > 0)
                    if margem <= 0:
                        continue
                    
                    for s_out in outcomes_soft:
                        s_price = s_out.get("price", s_out.get("odd", 0))
                        s_name = s_out.get("name", s_out.get("value", "Desconhecido"))
                        
                        p_match = next(
                            (p for p in outcomes_pin
                             if normalizar_nome(p.get("name", p.get("value", ""))) == normalizar_nome(s_name)
                             and p.get("point") == s_out.get("point")),
                            None
                        )
                        
                        if p_match:
                            p_price = p_match.get("price", p_match.get("odd", 1))
                            prob_real = (1 / p_price) / margem
                            ev = (prob_real * s_price) - 1
                            
                            if validar_futebol(s_price, ev, liga_key):
                                score = ev * LEAGUE_TIERS.get(liga_key, 1.0)
                                
                                nivel = calcular_nivel_confianca(ev, LEAGUE_TIERS.get(liga_key, 1.0), stats_home, stats_away)
                                mercados = []
                                
                                oportunidades.append({
                                    "jogo_id": jogo_id, "evento": evento,
                                    "home_team": home_team, "away_team": away_team,
                                    "horario_br": horario_br, "mercado_nome": m_key.upper(),
                                    "selecao_nome": f"{s_name} {s_out.get('point','')}",
                                    "odd_bookie": s_price, "odd_pinnacle": p_price,
                                    "prob_justa": prob_real, "ev_real": ev,
                                    "nome_bookie": soft.get("title", soft_key),
                                    "ranking_score": score,
                                    "stats_home": stats_home, "stats_away": stats_away,
                                    "h2h": h2h, "nivel_confianca": nivel,
                                    "mercados_interessantes": mercados,
                                    "fonte_dados": provedor,
                                    "linha": s_out.get("point")
                                })
        
        if oportunidades:
            melhor = max(oportunidades, key=lambda x: x["ranking_score"])
            
            mercado_nome = (
                "Vencedor (1X2)" if melhor["mercado_nome"] == "H2H"
                else "Ambas Marcam" if melhor["mercado_nome"] == "BTTS"
                else "Gols Mais/Menos"
            )
            
            analise = AnaliseJogo(
                jogo_id=melhor["jogo_id"],
                home_team=melhor["home_team"],
                away_team=melhor["away_team"],
                liga=melhor["evento"]["sport_title"],
                horario_br=melhor["horario_br"],
                stats_home=melhor["stats_home"],
                stats_away=melhor["stats_away"],
                h2h=melhor["h2h"],
                mercado_nome=mercado_nome,
                selecao_nome=melhor["selecao_nome"].replace("Yes", "Sim").replace("No", "Não"),
                odd_bookie=melhor["odd_bookie"],
                odd_pinnacle=melhor["odd_pinnacle"],
                nome_bookie=melhor["nome_bookie"],
                prob_justa=melhor["prob_justa"],
                ev_real=melhor["ev_real"],
                ranking_score=melhor["ranking_score"],
                nivel_confianca=melhor["nivel_confianca"],
                melhor_entrada=f"{melhor['selecao_nome']} @ {melhor['odd_bookie']:.2f}",
                mercados_interessantes=melhor["mercados_interessantes"],
                fonte_dados=provedor.upper(),
                linha=melhor.get("linha")
            )
            
            sucesso = await enviar_telegram_async(session, analise)
            if sucesso:
                jogos_enviados[jogo_id] = agora_br + timedelta(hours=24)
                salvar_aposta_banco(melhor, 1.5, analise)
                odds_cache.set(jogo_id, {"status": "enviado", "analise": analise.__dict__}, provedor, ttl=86400)

def extrair_bookmakers(evento: Dict, provedor: str) -> List[Dict]:
    if provedor == "api_football":
        return evento.get("bookmakers", [])
    elif provedor == "sportmonks":
        return evento.get("odds", {}).get("bookmakers", [])
    else:
        return evento.get("bookmakers", [])

def parse_api_football(data: Dict) -> List[Dict]:
    return data.get("response", [])

def parse_sportmonks(data: Dict) -> List[Dict]:
    return data.get("data", [])

# ==========================================
# LOOP PRINCIPAL
# ==========================================

async def loop_infinito():
    carregar_memoria_banco()
    
    print("🚀 Bot Futebol iniciado com sistema multiprovider!")
    print(f"🔑 Provedores configurados: {len(provider_manager.PRIORIDADE_PROVEDORES)}")
    print(f"🔑 Total de chaves: {sum(len(v) for v in provider_manager.chaves_por_provedor.values())}")
    print(f"💾 Cache: odds_cache_futebol.db")
    print(f"🤖 Bots Telegram: 3 (failover automático)")
    print("=" * 50)
    
    async with aiohttp.ClientSession() as session:
        # Valida todas as chaves no startup
        await provider_manager.validar_todas_chaves(session)
        
        print("\n" + "=" * 50)
        print("🚀 Iniciando loop principal...")
        print("=" * 50)
    
    while True:
        async with aiohttp.ClientSession() as session:
            agora_br = datetime.now(ZoneInfo("America/Sao_Paulo"))
            print(f"⚽ Varredura Futebol: {agora_br.strftime('%H:%M')}")
            print(f"📊 Provedores ativos: {[p for p in provider_manager.PRIORIDADE_PROVEDORES if p not in provedores_falhos]}")
            
            for i in range(0, len(LIGAS), 3):
                batch = LIGAS[i:i+3]
                await asyncio.gather(*[processar_liga_async(session, liga, agora_br) for liga in batch])
                await asyncio.sleep(5)
            
            if provedores_falhos:
                print(f"🔄 Limpando {len(provedores_falhos)} provedores falhos")
                provedores_falhos.clear()
            
            limpos = odds_cache.limpar_expirados()
            if limpos > 0:
                print(f"🧹 {limpos} entradas de cache removidas")
            
            hoje = datetime.now().strftime("%Y%m%d")
            total_req = sum(v for k, v in request_count.items() if k.endswith(f"_{hoje}"))
            cache_stats = odds_cache.estatisticas()
            
            print(f"📊 Total requisições hoje: {total_req}")
            print(f"💾 Cache hit rate: {cache_stats['hit_rate']:.1f}%")
            print(f"💾 Jogos em memória: {len(jogos_enviados)}")
            print(provider_manager.get_health_report())
            print(provider_manager.get_balanceamento_chaves())  # Mostra balanceamento
            print("=" * 50)
        
        await asyncio.sleep(SCAN_INTERVAL)

# ==========================================
# START
# ==========================================

if __name__ == "__main__":
    try:
        asyncio.run(loop_infinito())
    except KeyboardInterrupt:
        print("\n🛑 Bot Futebol encerrado")
        print(f"📊 Estatísticas finais: {odds_cache.estatisticas()}")
        print(provider_manager.get_balanceamento_chaves())
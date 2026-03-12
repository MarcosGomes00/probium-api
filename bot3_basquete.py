import asyncio
import aiohttp
import sqlite3
import unicodedata
import heapq
import time
import statistics
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Set
import json

# ==========================================
# CONFIGURAÇÕES BOT 3 - BASQUETE PRO MULTIPROVIDER
# ==========================================

# ==========================================
# CHAVES DE API - COM VALIDAÇÃO AUTOMÁTICA
# ==========================================

# Todas as chaves organizadas por provedor (serão validadas no startup)
TODAS_CHAVES_BALLDONTLIE = [
    "a8d9ab5d-7c93-469a-8c3a-924fd4e5e7b4",
    "8033f045-a2b3-47c6-919a-9141145c742c",
    "3ddaee43-d801-4559-84fd-e233e8f4bb9c",
    "afaca1cf-3bbe-47cc-93f5-6e7a1adfd195",
    "d1559bc7-3ceb-4c0d-8171-0d2298988cf5"
]

TODAS_CHAVES_ODDS_API = [
    "6249ca36b148b2542bb433d23e4ace65a97c896b7dc3b93c79b4a6715b29ea7d",
    "b29dcd347f5f26ddebb469eaa9e5f98fb75ca20be03cc47117027604d0a9f029",
    "528e79310c9161f769a282b8d2aa61be2bb332e0cc036a51e44acee5ca7bd66f"
]

TODAS_CHAVES_SGO = [
    "e38185eb8b9eff32802ff016db544dc3",
    "2b8b25840b9605c1133845549d08b879"
]

TODAS_CHAVES_THE_ODDS_TOKEN = [
    "b668851102c3e0a56c33220161c029ec",
    "0d43575dd39e175ba670fb91b2230442",
    "d32378e66e89f159688cc2239f38a6a4",
    "713146de690026b224dd8bbf0abc0339"
]

TODAS_CHAVES_THE_ODDS_API_LEGACY = [
    "6a1c0078b3ed09b42fbacee8f07e7cc3",
    "0ecb237829d0f800181538e1a4fa2494",
    "4790419cc795932ffaeb0152fa5818c8",
    "5ee1c6a8c611b6c3d6aff8043764555f",
    "b668851102c3e0a56c33220161c029ec",
    "0d43575dd39e175ba670fb91b2230442",
    "d32378e66e89f159688cc2239f38a6a4",
    "713146de690026b224dd8bbf0abc0339",
    "wk_9973be016f72a4a9775eafaefbd71740"
]

TODAS_CHAVES_SPORTDB = [
    "f8W9DfG71LPWMeU2TxkMtK1PEmWVwGzWW2B1Lmk9",
    "z7Dzdk5NlGtFvg5SqfL1IZWGkjOkXnOsv7tiPRrS",
    "ftAAx0FNerTm0lFMxFnWmxEbFKn7BSEMF83yosTf",
    "w1SolKpreujO7wmAKJmrW1lvfB7zK3Vv6ORnFc1t"
]

# Chaves que serão populadas após validação
BALLDONTLIE_KEYS: List[str] = []
ODDS_API_KEYS: List[str] = []
SGO_API_KEYS: List[str] = []
THE_ODDS_TOKEN_KEYS: List[str] = []
THE_ODDS_API_LEGACY_KEYS: List[str] = []
SPORTDB_KEYS: List[str] = []

# Configurações de Tokens do Telegram
TELEGRAM_TOKENS = {
    "bot1": "8725909088:AAGQMNr-9RVQB7hWmePCLmm0GwaGuzOVy-A",
    "bot2": "8185027087:AAH1JQJKtlWy_oUQpAvqvHEsFIVOK3ScYBc",
    "bot3": "8413563055:AAGyovCDMJOxiAukTbXwaJPm3ZDckIf7qJU"
}

TELEGRAM_TOKEN = TELEGRAM_TOKENS["bot3"]
CHAT_ID = "-1003814625223"
DB_FILE = "probum.db"

SCAN_INTERVAL = 21600
MAX_APOSTAS_POR_DIA = 4
MIN_EV_PERCENT = 0.025
MAX_ODD = 3.0
REQUEST_DELAY = 2.0

# Limites por provedor
MAX_REQ_POR_CHAVE_DIA = {
    "odds_api": 2400,
    "sgo": 1000,
    "the_odds_token": 500,
    "the_odds_api_legacy": 50,
    "balldontlie": 1000,
    "sportdb": 1000
}

SOFT_BOOKIES = [
    "bet365", "betano", "1xbet", "draftkings",
    "williamhill", "unibet", "888sport", "betfair_ex_eu"
]

SHARP_BOOKIE = "pinnacle"
TODAS_CASAS = SOFT_BOOKIES + [SHARP_BOOKIE]

LEAGUE_TIERS = {
    "basketball_nba": 1.5,
    "basketball_euroleague": 1.2,
    "basketball_ncaa": 1.0
}

LIGAS = list(LEAGUE_TIERS.keys())

# ==========================================
# ESTRUTURAS DE DADOS
# ==========================================

@dataclass
class EstatisticasTimeBasquete:
    nome: str
    jogos_jogados: int = 0
    vitorias: int = 0
    derrotas: int = 0
    media_pontos_marcados: float = 0.0
    media_pontos_sofridos: float = 0.0
    media_pontos_total: float = 0.0
    over_215: float = 0.0
    over_220: float = 0.0
    under_215: float = 0.0
    forma: List[str] = field(default_factory=list)
    pace: float = 0.0
    offensive_rating: float = 0.0
    defensive_rating: float = 0.0
    eficiencia_arremesso: float = 0.0
    vantagem_casa: float = 0.0
    back_to_back: bool = False
    dias_descanso: int = 2

@dataclass
class AnaliseBasquete:
    jogo_id: str
    home_team: str
    away_team: str
    liga: str
    liga_key: str
    horario_br: datetime
    stats_home: Optional[EstatisticasTimeBasquete]
    stats_away: Optional[EstatisticasTimeBasquete]
    h2h: List[Dict]
    mercado_nome: str
    selecao_nome: str
    linha: Optional[float]
    odd_bookie: float
    odd_pinnacle: float
    nome_bookie: str
    prob_justa: float
    ev_real: float
    score_qualidade: float
    nivel_confianca: str
    mercados_sugeridos: List[str]
    melhor_call: str
    justificativa: str
    contexto: str
    fonte_dados: str = ""

# ==========================================
# CONTROLE GLOBAL
# ==========================================

jogos_enviados = {}
api_lock = asyncio.Lock()
request_count = {}
last_request_time = 0
chaves_falhas: Dict[str, Dict[str, float]] = {}
provedores_falhos: Set[str] = set()
oportunidades_dia: List[tuple] = []
dia_atual = None
lock_oportunidades = asyncio.Lock()

# ==========================================
# SISTEMA DE VALIDAÇÃO DE CHAVES
# ==========================================

class KeyValidator:
    """Valida todas as chaves no startup e mantém apenas as funcionais"""
    
    def __init__(self):
        self.chaves_validas: Dict[str, List[str]] = {}
        self.chaves_invalidas: Dict[str, List[str]] = {}
    
    async def validar_todas_chaves(self, session: aiohttp.ClientSession):
        """Valida todas as chaves de todos os provedores"""
        print("🔍 Iniciando validação de todas as chaves de API...")
        
        # Validar Ball Don't Lie
        self.chaves_validas["balldontlie"], self.chaves_invalidas["balldontlie"] = \
            await self._validar_balldontlie(session, TODAS_CHAVES_BALLDONTLIE)
        
        # Validar Odds API
        self.chaves_validas["odds_api"], self.chaves_invalidas["odds_api"] = \
            await self._validar_odds_api(session, TODAS_CHAVES_ODDS_API)
        
        # Validar SGO
        self.chaves_validas["sgo"], self.chaves_invalidas["sgo"] = \
            await self._validar_sgo(session, TODAS_CHAVES_SGO)
        
        # Validar The Odds Token
        self.chaves_validas["the_odds_token"], self.chaves_invalidas["the_odds_token"] = \
            await self._validar_the_odds_token(session, TODAS_CHAVES_THE_ODDS_TOKEN)
        
        # Validar The Odds API Legacy
        self.chaves_validas["the_odds_api_legacy"], self.chaves_invalidas["the_odds_api_legacy"] = \
            await self._validar_the_odds_api_legacy(session, TODAS_CHAVES_THE_ODDS_API_LEGACY)
        
        # Validar SportDB
        self.chaves_validas["sportdb"], self.chaves_invalidas["sportdb"] = \
            await self._validar_sportdb(session, TODAS_CHAVES_SPORTDB)
        
        # Popular variáveis globais apenas com chaves válidas
        global BALLDONTLIE_KEYS, ODDS_API_KEYS, SGO_API_KEYS
        global THE_ODDS_TOKEN_KEYS, THE_ODDS_API_LEGACY_KEYS, SPORTDB_KEYS
        
        BALLDONTLIE_KEYS = self.chaves_validas.get("balldontlie", [])
        ODDS_API_KEYS = self.chaves_validas.get("odds_api", [])
        SGO_API_KEYS = self.chaves_validas.get("sgo", [])
        THE_ODDS_TOKEN_KEYS = self.chaves_validas.get("the_odds_token", [])
        THE_ODDS_API_LEGACY_KEYS = self.chaves_validas.get("the_odds_api_legacy", [])
        SPORTDB_KEYS = self.chaves_validas.get("sportdb", [])
        
        # Resumo
        print("\n" + "="*50)
        print("📊 RESUMO DA VALIDAÇÃO:")
        for provedor, validas in self.chaves_validas.items():
            invalidas = self.chaves_invalidas.get(provedor, [])
            total = len(validas) + len(invalidas)
            if total > 0:
                status = "✅" if len(validas) > 0 else "❌"
                print(f"{status} {provedor}: {len(validas)}/{total} chaves válidas")
                if invalidas:
                    print(f"   ❌ Invalidas: {[c[:8]+'...' for c in invalidas[:3]]}")
        print("="*50 + "\n")
        
        # Alerta se poucas chaves
        total_validas = sum(len(v) for v in self.chaves_validas.values())
        if total_validas < 5:
            print("🚨 ALERTA: Poucas chaves válidas! Verifique suas APIs.")
    
    async def _validar_balldontlie(self, session: aiohttp.ClientSession, chaves: List[str]) -> Tuple[List[str], List[str]]:
        """Valida chaves Ball Don't Lie"""
        validas, invalidas = [], []
        for chave in chaves:
            try:
                url = "https://api.balldontlie.io/v1/teams"
                headers = {"Authorization": chave}
                async with session.get(url, headers=headers, timeout=10) as r:
                    if r.status == 200:
                        validas.append(chave)
                        print(f"  ✅ Ball Don't Lie: {chave[:8]}... OK")
                    else:
                        invalidas.append(chave)
                        print(f"  ❌ Ball Don't Lie: {chave[:8]}... Falha ({r.status})")
            except Exception as e:
                invalidas.append(chave)
                print(f"  ❌ Ball Don't Lie: {chave[:8]}... Erro ({str(e)[:30]})")
            await asyncio.sleep(0.5)
        return validas, invalidas
    
    async def _validar_odds_api(self, session: aiohttp.ClientSession, chaves: List[str]) -> Tuple[List[str], List[str]]:
        """Valida chaves Odds-API.io"""
        validas, invalidas = [], []
        for chave in chaves:
            try:
                url = "https://api.the-odds-api.com/v4/sports/basketball_nba/odds/"
                params = {
                    "apiKey": chave,
                    "regions": "eu",
                    "markets": "h2h",
                    "bookmakers": "pinnacle"
                }
                async with session.get(url, params=params, timeout=10) as r:
                    if r.status == 200:
                        validas.append(chave)
                        print(f"  ✅ Odds API: {chave[:8]}... OK")
                    elif r.status == 401:
                        invalidas.append(chave)
                        print(f"  ❌ Odds API: {chave[:8]}... Invalida (401)")
                    else:
                        invalidas.append(chave)
                        print(f"  ❌ Odds API: {chave[:8]}... Falha ({r.status})")
            except Exception as e:
                invalidas.append(chave)
                print(f"  ❌ Odds API: {chave[:8]}... Erro ({str(e)[:30]})")
            await asyncio.sleep(0.5)
        return validas, invalidas
    
    async def _validar_sgo(self, session: aiohttp.ClientSession, chaves: List[str]) -> Tuple[List[str], List[str]]:
        """Valida chaves Sports Game Odds"""
        validas, invalidas = [], []
        for chave in chaves:
            try:
                url = "https://api.sportsgameodds.com/v1/events"
                params = {
                    "apiKey": chave,
                    "sport": "basketball",
                    "league": "nba"
                }
                async with session.get(url, params=params, timeout=10) as r:
                    if r.status in [200, 201]:
                        validas.append(chave)
                        print(f"  ✅ SGO: {chave[:8]}... OK")
                    else:
                        invalidas.append(chave)
                        print(f"  ❌ SGO: {chave[:8]}... Falha ({r.status})")
            except Exception as e:
                invalidas.append(chave)
                print(f"  ❌ SGO: {chave[:8]}... Erro ({str(e)[:30]})")
            await asyncio.sleep(0.5)
        return validas, invalidas
    
    async def _validar_the_odds_token(self, session: aiohttp.ClientSession, chaves: List[str]) -> Tuple[List[str], List[str]]:
        """Valida chaves The Odds Token"""
        validas, invalidas = [], []
        for chave in chaves:
            try:
                url = "https://api.the-odds-api.com/v4/sports/basketball_nba/odds/"
                params = {
                    "apiKey": chave,
                    "regions": "eu",
                    "markets": "h2h"
                }
                async with session.get(url, params=params, timeout=10) as r:
                    if r.status == 200:
                        validas.append(chave)
                        print(f"  ✅ The Odds Token: {chave[:8]}... OK")
                    else:
                        invalidas.append(chave)
                        print(f"  ❌ The Odds Token: {chave[:8]}... Falha ({r.status})")
            except Exception as e:
                invalidas.append(chave)
                print(f"  ❌ The Odds Token: {chave[:8]}... Erro ({str(e)[:30]})")
            await asyncio.sleep(0.5)
        return validas, invalidas
    
    async def _validar_the_odds_api_legacy(self, session: aiohttp.ClientSession, chaves: List[str]) -> Tuple[List[str], List[str]]:
        """Valida chaves The Odds API Legacy"""
        validas, invalidas = [], []
        for chave in chaves:
            try:
                url = "https://api.the-odds-api.com/v4/sports/basketball_nba/odds/"
                params = {
                    "apiKey": chave,
                    "regions": "eu",
                    "markets": "h2h"
                }
                async with session.get(url, params=params, timeout=10) as r:
                    if r.status == 200:
                        validas.append(chave)
                        print(f"  ✅ The Odds API Legacy: {chave[:8]}... OK")
                    elif r.status == 429:
                        # Rate limit ainda indica chave válida mas esgotada
                        validas.append(chave)
                        print(f"  ⚠️ The Odds API Legacy: {chave[:8]}... Rate limit (válida mas esgotada)")
                    else:
                        invalidas.append(chave)
                        print(f"  ❌ The Odds API Legacy: {chave[:8]}... Falha ({r.status})")
            except Exception as e:
                invalidas.append(chave)
                print(f"  ❌ The Odds API Legacy: {chave[:8]}... Erro ({str(e)[:30]})")
            await asyncio.sleep(0.5)
        return validas, invalidas
    
    async def _validar_sportdb(self, session: aiohttp.ClientSession, chaves: List[str]) -> Tuple[List[str], List[str]]:
        """Valida chaves SportDB"""
        validas, invalidas = [], []
        for chave in chaves:
            try:
                url = f"https://www.thesportsdb.com/api/v1/json/{chave}/searchteams.php"
                params = {"t": "Lakers"}
                async with session.get(url, params=params, timeout=10) as r:
                    if r.status == 200:
                        data = await r.json()
                        if data and "teams" in data:
                            validas.append(chave)
                            print(f"  ✅ SportDB: {chave[:8]}... OK")
                        else:
                            invalidas.append(chave)
                            print(f"  ❌ SportDB: {chave[:8]}... Resposta inválida")
                    else:
                        invalidas.append(chave)
                        print(f"  ❌ SportDB: {chave[:8]}... Falha ({r.status})")
            except Exception as e:
                invalidas.append(chave)
                print(f"  ❌ SportDB: {chave[:8]}... Erro ({str(e)[:30]})")
            await asyncio.sleep(0.5)
        return validas, invalidas

# Instância global do validador
key_validator = KeyValidator()

# ==========================================
# SISTEMA DE ROTAÇÃO SIMULTÂNEA (ROUND-ROBIN)
# ==========================================

class RotacaoSimultanea:
    """
    Sistema de rotação que distribui requisições igualmente entre todas as chaves
    para que expirem por igual, evitando que uma única chave seja esgotada primeiro
    """
    
    def __init__(self):
        self.indices: Dict[str, int] = {}
        self.contadores: Dict[str, Dict[str, int]] = {}  # Contador por chave
        self.lock = asyncio.Lock()
    
    def inicializar(self, provedores: Dict[str, List[str]]):
        """Inicializa índices para cada provedor"""
        for provedor, chaves in provedores.items():
            if chaves:  # Só inicializa se tiver chaves válidas
                self.indices[provedor] = 0
                self.contadores[provedor] = {chave: 0 for chave in chaves}
                print(f"  🔄 Rotação {provedor}: {len(chaves)} chaves configuradas")
    
    async def proxima_chave(self, provedor: str, chaves: List[str]) -> Optional[str]:
        """Retorna a próxima chave na rotação round-robin"""
        if not chaves:
            return None
        
        async with self.lock:
            if provedor not in self.indices:
                self.indices[provedor] = 0
                self.contadores[provedor] = {chave: 0 for chave in chaves}
            
            # Encontra a chave com menor contador (menos usada)
            chave_menos_usada = min(chaves, key=lambda c: self.contadores[provedor].get(c, 0))
            
            # Incrementa contador
            self.contadores[provedor][chave_menos_usada] += 1
            
            return chave_menos_usada
    
    def get_estatisticas(self) -> Dict[str, Dict]:
        """Retorna estatísticas de uso por provedor"""
        stats = {}
        for provedor, contadores in self.contadores.items():
            if contadores:
                total = sum(contadores.values())
                media = total / len(contadores) if contadores else 0
                stats[provedor] = {
                    "total_requisicoes": total,
                    "media_por_chave": media,
                    "distribuicao": {k[:8]+"...": v for k, v in contadores.items()}
                }
        return stats

# Instância global da rotação
rotacao = RotacaoSimultanea()

# ==========================================
# SISTEMA DE HEALTH CHECK
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

# ==========================================
# SISTEMA DE CACHE
# ==========================================

class OddsCache:
    def __init__(self, db_file="odds_cache_basquete.db"):
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
                esporte TEXT,
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
            (jogo_id, liga, esporte, dados_json, provedor, timestamp, ttl)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            jogo_id,
            dados.get("sport_key", "unknown"),
            dados.get("sport_title", "unknown"),
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
# SISTEMA DE FAILOVER MULTIPROVIDER
# ==========================================

class APIProviderManager:
    PRIORIDADE_PROVEDORES = [
        "odds_api",
        "sgo",
        "the_odds_token",
        "the_odds_api_legacy",
    ]
    
    def __init__(self):
        self.provedor_atual_idx = 0
        self.health_por_provedor = {
            p: ProvedorHealth() for p in self.PRIORIDADE_PROVEDORES
        }
    
    def get_provedor_atual(self) -> Optional[str]:
        disponiveis = [p for p in self.PRIORIDADE_PROVEDORES 
                      if p not in provedores_falhos and self.health_por_provedor[p].esta_saudavel()]
        
        if not disponiveis:
            disponiveis = [p for p in self.PRIORIDADE_PROVEDORES if p not in provedores_falhos]
        
        if not disponiveis:
            return None
        
        disponiveis.sort(key=lambda p: self.health_por_provedor[p].score, reverse=True)
        return disponiveis[0]
    
    def proximo_provedor(self):
        self.provedor_atual_idx = (self.provedor_atual_idx + 1) % len(self.PRIORIDADE_PROVEDORES)
    
    def marcar_sucesso(self, provedor: str, latencia_ms: float):
        self.health_por_provedor[provedor].registrar_sucesso(latencia_ms)
    
    def marcar_erro(self, provedor: str):
        self.health_por_provedor[provedor].registrar_erro()
    
    def marcar_provedor_offline(self, provedor: str):
        provedores_falhos.add(provedor)
        print(f"🚫 Basquete: Provedor {provedor} marcado como offline")
        asyncio.create_task(self.reativar_provedor(provedor, 1800))
    
    async def reativar_provedor(self, provedor: str, delay: int):
        await asyncio.sleep(delay)
        if provedor in provedores_falhos:
            provedores_falhos.remove(provedor)
            self.health_por_provedor[provedor].score = 50
            print(f"✅ Basquete: Provedor {provedor} reativado")
    
    def get_health_report(self) -> str:
        linhas = ["📊 Health Check:"]
        for provedor in self.PRIORIDADE_PROVEDORES:
            h = self.health_por_provedor[provedor]
            status = "🟢" if h.esta_saudavel() else "🔴"
            linhas.append(f"{status} {provedor}: Score={h.score:.0f} | Lat={h.latencia_media():.0f}ms")
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

def calcular_score_qualidade(ev, tier_liga, stats_home, stats_away, mercado):
    score = 0.0
    score += min(ev * 1000, 40)
    score += (tier_liga / 1.5) * 20
    
    if stats_home and stats_away:
        diff_pontos = abs(stats_home.media_pontos_total - stats_away.media_pontos_total)
        if diff_pontos < 15:
            score += 10
        
        forma_home = stats_home.forma.count('W') / max(len(stats_home.forma), 1)
        forma_away = stats_away.forma.count('W') / max(len(stats_away.forma), 1)
        if abs(forma_home - forma_away) > 0.4:
            score += 10
        
        if abs(stats_home.pace - stats_away.pace) < 3:
            score += 5
    
    if mercado == "totals":
        score += 15
    elif mercado == "spreads":
        score += 12
    else:
        score += 8
    
    return score

def determinar_nivel_confianca(score, ev, stats_disponiveis):
    if score >= 75 and ev >= 0.04 and stats_disponiveis:
        return "🔥 Alto"
    elif score >= 60 and ev >= 0.03:
        return "⚡ Médio"
    else:
        return "⚠️ Baixo"

def gerar_mercados_sugeridos(stats_home, stats_away, media_total):
    mercados = []
    
    if media_total > 225:
        mercados.append(f"Over {int(media_total - 5)}.5 pontos")
        mercados.append(f"Over {int(media_total - 10)}.5 pontos (alternativa)")
    elif media_total < 215:
        mercados.append(f"Under {int(media_total + 5)}.5 pontos")
    
    if stats_home and stats_away:
        diff_vitorias = (stats_home.forma.count('W') - stats_away.forma.count('W'))
        if diff_vitorias >= 3:
            mercados.append(f"Handicap -4.5 {stats_home.nome}")
        elif diff_vitorias <= -3:
            mercados.append(f"Handicap -4.5 {stats_away.nome}")
        
        if stats_home.media_pontos_marcados > 115:
            mercados.append(f"Over {int(stats_home.media_pontos_marcados - 5)}.5 pontos {stats_home.nome}")
        if stats_away.media_pontos_marcados > 115:
            mercados.append(f"Over {int(stats_away.media_pontos_marcados - 5)}.5 pontos {stats_away.nome}")
    
    return mercados[:4]

def gerar_justificativa(analise):
    partes = []
    
    if analise.stats_home and analise.stats_away:
        forma_h = analise.stats_home.forma.count('W')
        forma_a = analise.stats_away.forma.count('W')
        
        if forma_h > forma_a:
            partes.append(f"{analise.home_team} vem em melhor forma ({forma_h} vitórias nos últimos 5)")
        elif forma_a > forma_h:
            partes.append(f"{analise.away_team} vem em melhor forma ({forma_a} vitórias nos últimos 5)")
        
        if abs(analise.stats_home.pace - analise.stats_away.pace) < 2:
            partes.append("Times com ritmo de jogo similar")
        
        if analise.stats_home.back_to_back or analise.stats_away.back_to_back:
            partes.append("Atenção: back-to-back pode afetar desempenho")
    
    if "Over" in analise.selecao_nome:
        partes.append("Tendência ofensiva identificada nas estatísticas")
    elif "Under" in analise.selecao_nome:
        partes.append("Defesas sólidas sugerem jogo truncado")
    
    return " | ".join(partes) if partes else "Valor identificado na discrepância de odds"

# ==========================================
# BANCO DE DADOS
# ==========================================

def carregar_memoria_banco():
    global jogos_enviados
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id_aposta FROM operacoes_tipster WHERE status='PENDENTE' AND esporte='basketball'"
        )
        for (id_aposta,) in cursor.fetchall():
            jogos_enviados[id_aposta.split("_")[0]] = datetime.now(
                ZoneInfo("America/Sao_Paulo")
            ) + timedelta(hours=24)
        conn.close()
    except:
        pass

def salvar_aposta_banco(analise, stake):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        id_aposta = f"{analise.jogo_id}_{analise.mercado_nome[:4]}_{analise.selecao_nome[:4]}".replace(" ", "")
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
                justificativa TEXT,
                stats_home TEXT,
                stats_away TEXT,
                fonte_dados TEXT
            )
        """)

        cursor.execute(
            """
            INSERT OR IGNORE INTO operacoes_tipster
            (id_aposta,esporte,jogo,liga,mercado,selecao,odd,prob,ev,stake,status,lucro,data_hora,pinnacle_odd,ranking_score,nivel_confianca,justificativa,stats_home,stats_away,fonte_dados)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                id_aposta,
                "basketball",
                f"{analise.home_team} x {analise.away_team}",
                analise.liga,
                analise.mercado_nome,
                analise.selecao_nome,
                analise.odd_bookie,
                analise.prob_justa,
                analise.ev_real,
                stake,
                'PENDENTE',
                0,
                hoje,
                analise.odd_pinnacle,
                analise.score_qualidade,
                analise.nivel_confianca,
                analise.justificativa,
                json.dumps(analise.stats_home.__dict__ if analise.stats_home else {}),
                json.dumps(analise.stats_away.__dict__ if analise.stats_away else {}),
                analise.fonte_dados
            )
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erro ao salvar: {e}")

# ==========================================
# APIs DE ESTATÍSTICAS - MULTIPROVIDER COM ROTAÇÃO SIMULTÂNEA
# ==========================================

class StatsProviderManager:
    def __init__(self):
        pass  # Rotação é gerenciada globalmente
    
    async def buscar_stats(self, session, team_name):
        stats = await self._buscar_balldontlie(session, team_name)
        if stats:
            return stats
        
        stats = await self._buscar_sportdb(session, team_name)
        if stats:
            return stats
        
        return None
    
    async def _buscar_balldontlie(self, session, team_name):
        if not BALLDONTLIE_KEYS:
            return None
        
        await rate_limit()
        
        # Usa rotação simultânea para distribuir carga
        chave = await rotacao.proxima_chave("balldontlie", BALLDONTLIE_KEYS)
        if not chave:
            return None
        
        try:
            url = "https://api.balldontlie.io/v1/teams"
            headers = {"Authorization": chave}
            
            async with session.get(url, headers=headers, timeout=10) as r:
                if r.status == 200:
                    data = await r.json()
                    team_id = None
                    for team in data.get("data", []):
                        if normalizar_nome(team_name) in normalizar_nome(team["full_name"]):
                            team_id = team["id"]
                            break
                    
                    if not team_id:
                        return None
                    
                    await rate_limit()
                    games_url = f"https://api.balldontlie.io/v1/games?team_ids[]={team_id}&per_page=10"
                    
                    # Rotação para requisição de jogos também
                    chave_jogos = await rotacao.proxima_chave("balldontlie", BALLDONTLIE_KEYS)
                    
                    async with session.get(games_url, headers={"Authorization": chave_jogos}, timeout=10) as r2:
                        if r2.status == 200:
                            games_data = await r2.json()
                            games = games_data.get("data", [])
                            
                            if not games:
                                return None
                            
                            pontos_marcados = []
                            pontos_sofridos = []
                            forma = []
                            
                            for game in games:
                                if game["home_team"]["id"] == team_id:
                                    pontos_marcados.append(game["home_team_score"])
                                    pontos_sofridos.append(game["visitor_team_score"])
                                    forma.append('W' if game["home_team_score"] > game["visitor_team_score"] else 'L')
                                else:
                                    pontos_marcados.append(game["visitor_team_score"])
                                    pontos_sofridos.append(game["home_team_score"])
                                    forma.append('W' if game["visitor_team_score"] > game["home_team_score"] else 'L')
                            
                            media_marcados = sum(pontos_marcados) / len(pontos_marcados)
                            media_sofridos = sum(pontos_sofridos) / len(pontos_sofridos)
                            total_jogos = len(games)
                            
                            overs_215 = sum(1 for i in range(total_jogos) 
                                           if (pontos_marcados[i] + pontos_sofridos[i]) > 215.5) / total_jogos * 100
                            overs_220 = sum(1 for i in range(total_jogos) 
                                           if (pontos_marcados[i] + pontos_sofridos[i]) > 220.5) / total_jogos * 100
                            
                            return EstatisticasTimeBasquete(
                                nome=team_name,
                                jogos_jogados=total_jogos,
                                vitorias=forma.count('W'),
                                derrotas=forma.count('L'),
                                media_pontos_marcados=media_marcados,
                                media_pontos_sofridos=media_sofridos,
                                media_pontos_total=media_marcados + media_sofridos,
                                over_215=overs_215,
                                over_220=overs_220,
                                under_215=100 - overs_215,
                                forma=forma[:5],
                                pace=100.0,
                                offensive_rating=media_marcados / 100 * 100,
                                defensive_rating=media_sofridos / 100 * 100,
                                eficiencia_arremesso=0.45,
                                vantagem_casa=3.5,
                                back_to_back=False,
                                dias_descanso=2
                            )
                elif r.status in [401, 429]:
                    print(f"⚠️ Ball Don't Lie chave falhou: {r.status}")
        except Exception as e:
            print(f"Erro Ball Don't Lie: {e}")
        
        return None
    
    async def _buscar_sportdb(self, session, team_name):
        if not SPORTDB_KEYS:
            return None
        
        await rate_limit()
        
        chave = await rotacao.proxima_chave("sportdb", SPORTDB_KEYS)
        if not chave:
            return None
        
        try:
            url = f"https://www.thesportsdb.com/api/v1/json/{chave}/searchteams.php"
            params = {"t": team_name}
            
            async with session.get(url, params=params, timeout=10) as r:
                if r.status == 200:
                    data = await r.json()
                    teams = data.get("teams", [])
                    if not teams:
                        return None
                    
                    team_id = teams[0].get("idTeam")
                    
                    await rate_limit()
                    chave_events = await rotacao.proxima_chave("sportdb", SPORTDB_KEYS)
                    events_url = f"https://www.thesportsdb.com/api/v1/json/{chave_events}/eventslast.php"
                    
                    async with session.get(events_url, params={"id": team_id}, timeout=10) as r2:
                        if r2.status == 200:
                            events_data = await r2.json()
                            results = events_data.get("results", [])
                            
                            if not results:
                                return None
                            
                            pontos_marcados = []
                            forma = []
                            
                            for event in results[:10]:
                                home_score = int(event.get("intHomeScore", 0) or 0)
                                away_score = int(event.get("intAwayScore", 0) or 0)
                                
                                if event.get("idHomeTeam") == team_id:
                                    pontos_marcados.append(home_score)
                                    forma.append('W' if home_score > away_score else 'L')
                                else:
                                    pontos_marcados.append(away_score)
                                    forma.append('W' if away_score > home_score else 'L')
                            
                            if not pontos_marcados:
                                return None
                            
                            media_marcados = sum(pontos_marcados) / len(pontos_marcados)
                            
                            return EstatisticasTimeBasquete(
                                nome=team_name,
                                jogos_jogados=len(pontos_marcados),
                                vitorias=forma.count('W'),
                                derrotas=forma.count('L'),
                                media_pontos_marcados=media_marcados,
                                media_pontos_sofridos=0,
                                media_pontos_total=media_marcados,
                                over_215=0,
                                over_220=0,
                                under_215=0,
                                forma=forma[:5],
                                pace=0,
                                offensive_rating=0,
                                defensive_rating=0,
                                eficiencia_arremesso=0,
                                vantagem_casa=0,
                                back_to_back=False,
                                dias_descanso=2
                            )
        except Exception as e:
            print(f"Erro SportDB: {e}")
        
        return None

stats_manager = StatsProviderManager()

async def buscar_h2h_basquete(session, home_team, away_team):
    if not BALLDONTLIE_KEYS:
        return []
    return []

# ==========================================
# TELEGRAM - MULTIBOT FAILOVER
# ==========================================

async def enviar_telegram_profissional(session, analise):
    bots = [TELEGRAM_TOKENS["bot3"], TELEGRAM_TOKENS["bot2"], TELEGRAM_TOKENS["bot1"]]
    
    for token in bots:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        
        stats_txt = ""
        if analise.stats_home and analise.stats_away:
            stats_txt = (
                f"\n📊 <b>Estatísticas Relevantes:</b>\n"
                f"  <i>{analise.home_team}:</i>\n"
                f"    • Média pontos: {analise.stats_home.media_pontos_marcados:.1f}\n"
                f"    • Forma: {' '.join(analise.stats_home.forma[:5])}\n"
                f"    • Over 215.5: {analise.stats_home.over_215:.0f}%\n"
                f"  <i>{analise.away_team}:</i>\n"
                f"    • Média pontos: {analise.stats_away.media_pontos_marcados:.1f}\n"
                f"    • Forma: {' '.join(analise.stats_away.forma[:5])}\n"
                f"    • Over 215.5: {analise.stats_away.over_215:.0f}%\n"
            )
        
        h2h_txt = ""
        if analise.h2h:
            ultimos = analise.h2h[:3]
            resultados = []
            for jogo in ultimos:
                home = jogo.get("home_team", {}).get("name", "Home")
                away = jogo.get("visitor_team", {}).get("name", "Away")
                home_score = jogo.get("home_team_score", 0)
                away_score = jogo.get("visitor_team_score", 0)
                resultados.append(f"{home} {home_score}x{away_score} {away}")
            h2h_txt = f"\n🔄 <b>Últimos H2H:</b>\n  " + "\n  ".join(resultados) + "\n"
        
        mercados_txt = "\n".join([f"  • {m}" for m in analise.mercados_sugeridos]) if analise.mercados_sugeridos else "  • Nenhum mercado adicional identificado"
        
        contexto = analise.contexto if analise.contexto else f"Confronto entre {analise.home_team} e {analise.away_team} na {analise.liga}"
        
        texto = (
            f"🏀 <b>CALL PROFISSIONAL - BASQUETE</b>\n"
            f"<i>Fonte: {analise.fonte_dados}</i>\n\n"
            f"<b>Jogo:</b>\n{analise.home_team} vs {analise.away_team}\n\n"
            f"<b>Análise Geral:</b>\n{contexto}\n"
            f"{stats_txt}"
            f"{h2h_txt}\n"
            f"<b>Mercados Interessantes:</b>\n{mercados_txt}\n\n"
            f"✅ <b>MELHOR CALL:</b>\n"
            f"  {analise.selecao_nome}\n"
            f"  🏛️ Casa: {analise.nome_bookie.upper()}\n"
            f"  📈 Odd: {analise.odd_bookie:.2f} (Pinnacle: {analise.odd_pinnacle:.2f})\n"
            f"  📊 EV: +{analise.ev_real*100:.1f}% | Prob Real: {analise.prob_justa*100:.1f}%\n\n"
            f"💡 <b>Justificativa:</b> {analise.justificativa}\n\n"
            f"{analise.nivel_confianca} <b>Nível de Confiança</b>\n\n"
            f"⚠️ <i>Análise baseada em estatísticas e probabilidade. "
            f"Gerencie sua banca e aposte com responsabilidade.</i>"
        )
        
        payload = {
            "chat_id": CHAT_ID,
            "text": texto,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        
        try:
            async with session.post(url, json=payload, timeout=10) as resp:
                if resp.status == 200:
                    return True
                else:
                    print(f"⚠️ Basquete: Bot falhou com status {resp.status}")
        except Exception as e:
            print(f"Erro Telegram Basquete: {e}")
    
    print("❌ Basquete: Todos os bots falharam!")
    return False

# ==========================================
# REQUISIÇÕES ODDS COM ROTAÇÃO SIMULTÂNEA
# ==========================================

async def fazer_requisicao_odds_multiprovider(session, liga_key, tentativas_max=10):
    for tentativa in range(tentativas_max):
        provedor = provider_manager.get_provedor_atual()
        
        if not provedor:
            print("❌ Basquete: Nenhum provedor disponível!")
            await asyncio.sleep(300)
            provedores_falhos.clear()
            continue
        
        # Obtém chave usando rotação simultânea (menos usada)
        chaves_disponiveis = []
        if provedor == "odds_api":
            chaves_disponiveis = ODDS_API_KEYS
        elif provedor == "sgo":
            chaves_disponiveis = SGO_API_KEYS
        elif provedor == "the_odds_token":
            chaves_disponiveis = THE_ODDS_TOKEN_KEYS
        elif provedor == "the_odds_api_legacy":
            chaves_disponiveis = THE_ODDS_API_LEGACY_KEYS
        
        chave = await rotacao.proxima_chave(provedor, chaves_disponiveis)
        
        if not chave:
            print(f"⚠️ Basquete: Sem chaves para {provedor}")
            provider_manager.marcar_provedor_offline(provedor)
            provider_manager.proximo_provedor()
            continue
        
        await rate_limit()
        inicio_req = time.time()
        
        if provedor == "odds_api":
            url = f"https://api.the-odds-api.com/v4/sports/{liga_key}/odds/"
            params = {
                "apiKey": chave,
                "regions": "eu",
                "markets": "h2h,spreads,totals",
                "bookmakers": ",".join(TODAS_CASAS)
            }
        elif provedor == "sgo":
            url = "https://api.sportsgameodds.com/v1/events"
            params = {
                "apiKey": chave,
                "sport": "basketball",
                "league": liga_key.replace("basketball_", ""),
                "markets": "h2h,spreads,totals"
            }
        else:
            url = f"https://api.the-odds-api.com/v4/sports/{liga_key}/odds/"
            params = {
                "apiKey": chave,
                "regions": "eu",
                "markets": "h2h,spreads,totals",
                "bookmakers": ",".join(TODAS_CASAS)
            }
        
        try:
            hoje = datetime.now().strftime("%Y%m%d")
            chave_hoje = f"{provedor}_{chave}_{hoje}"
            
            async with api_lock:
                request_count[chave_hoje] = request_count.get(chave_hoje, 0) + 1
                
                if request_count[chave_hoje] >= MAX_REQ_POR_CHAVE_DIA.get(provedor, 50):
                    print(f"⚠️ Basquete: Limite diário atingido para chave {chave[:8]}...")
                    continue
            
            async with session.get(url, params=params, timeout=15) as r:
                latencia_ms = (time.time() - inicio_req) * 1000
                
                if r.status == 200:
                    dados = await r.json()
                    provider_manager.marcar_sucesso(provedor, latencia_ms)
                    print(f"✅ Basquete: {provedor} em {latencia_ms:.0f}ms (chave: {chave[:8]}...)")
                    return dados, provedor
                elif r.status in [401, 429, 403]:
                    print(f"⚠️ Basquete: {provedor} retornou {r.status}")
                    provider_manager.marcar_erro(provedor)
                else:
                    print(f"⚠️ Basquete: {provedor} retornou {r.status}")
                    provider_manager.marcar_erro(provedor)
                    provider_manager.proximo_provedor()
                    
        except asyncio.TimeoutError:
            print(f"⏱️ Basquete: Timeout no {provedor}")
            provider_manager.marcar_erro(provedor)
            provider_manager.proximo_provedor()
        except Exception as e:
            print(f"Erro Basquete no {provedor}: {e}")
            provider_manager.marcar_erro(provedor)
            provider_manager.proximo_provedor()
        
        await asyncio.sleep(0.5)
    
    return None, None

def validar_basquete_pro(odd, ev, liga):
    if not (1.30 <= odd <= MAX_ODD):
        return False
    if ev < MIN_EV_PERCENT:
        return False
    if ev > 0.12:
        return False
    return True

# ==========================================
# PROCESSAMENTO
# ==========================================

async def processar_liga_async(session, liga_key, agora_br):
    global oportunidades_dia, dia_atual
    
    data, provedor = await fazer_requisicao_odds_multiprovider(session, liga_key)
    
    if not data or not isinstance(data, list):
        print(f"❌ Basquete: Não foi possível obter dados para {liga_key}")
        return
    
    for evento in data:
        jogo_id = str(evento.get("id", 0))
        
        if jogo_id in jogos_enviados:
            continue
        
        horario_br = datetime.fromisoformat(
            evento["commence_time"].replace("Z", "+00:00")
        ).astimezone(ZoneInfo("America/Sao_Paulo"))
        
        minutos = (horario_br - agora_br).total_seconds() / 60
        if not (30 <= minutos <= 1440):
            continue
        
        bookmakers = evento.get("bookmakers", [])
        pinnacle = next((b for b in bookmakers if b["key"] == SHARP_BOOKIE), None)
        
        if not pinnacle:
            continue
        
        home_team = evento["home_team"]
        away_team = evento["away_team"]
        
        stats_home, stats_away, h2h = None, None, []
        try:
            stats_task = asyncio.gather(
                asyncio.wait_for(stats_manager.buscar_stats(session, home_team), timeout=5),
                asyncio.wait_for(stats_manager.buscar_stats(session, away_team), timeout=5),
                asyncio.wait_for(buscar_h2h_basquete(session, home_team, away_team), timeout=5),
                return_exceptions=True
            )
            results = await stats_task
            stats_home = results[0] if not isinstance(results[0], Exception) else None
            stats_away = results[1] if not isinstance(results[1], Exception) else None
            h2h = results[2] if not isinstance(results[2], Exception) else []
        except:
            pass
        
        for soft in bookmakers:
            if soft["key"] not in SOFT_BOOKIES:
                continue
            
            for m_key in ["h2h", "spreads", "totals"]:
                pin_m = next((m for m in pinnacle.get("markets", []) if m["key"] == m_key), None)
                soft_m = next((m for m in soft.get("markets", []) if m["key"] == m_key), None)
                
                if not (pin_m and soft_m):
                    continue
                
                margem = sum(1/out["price"] for out in pin_m["outcomes"] if out["price"] > 0)
                if margem <= 0:
                    continue
                
                for s_out in soft_m["outcomes"]:
                    p_match = next(
                        (p for p in pin_m["outcomes"]
                         if normalizar_nome(p["name"]) == normalizar_nome(s_out["name"])
                         and p.get("point") == s_out.get("point")),
                        None
                    )
                    
                    if not p_match:
                        continue
                    
                    prob_real = (1 / p_match["price"]) / margem
                    ev = (prob_real * s_out["price"]) - 1
                    
                    if not validar_basquete_pro(s_out["price"], ev, liga_key):
                        continue
                    
                    score = calcular_score_qualidade(
                        ev, LEAGUE_TIERS.get(liga_key, 1.0),
                        stats_home, stats_away, m_key
                    )
                    
                    nivel = determinar_nivel_confianca(
                        score, ev, stats_home is not None and stats_away is not None
                    )
                    
                    media_total = 0
                    if stats_home and stats_away:
                        media_total = (stats_home.media_pontos_total + stats_away.media_pontos_total) / 2
                    
                    mercados = []
                    if stats_home and stats_away:
                        mercados = gerar_mercados_sugeridos(stats_home, stats_away, media_total)
                    
                    mercado_nome = (
                        "Vencedor" if m_key == "h2h"
                        else "Handicap de Pontos" if m_key == "spreads"
                        else "Total de Pontos"
                    )
                    
                    analise = AnaliseBasquete(
                        jogo_id=jogo_id,
                        home_team=home_team,
                        away_team=away_team,
                        liga=evento["sport_title"],
                        liga_key=liga_key,
                        horario_br=horario_br,
                        stats_home=stats_home,
                        stats_away=stats_away,
                        h2h=h2h,
                        mercado_nome=mercado_nome,
                        selecao_nome=f"{s_out['name']} {s_out.get('point', '')}".strip(),
                        linha=s_out.get("point"),
                        odd_bookie=s_out["price"],
                        odd_pinnacle=p_match["price"],
                        nome_bookie=soft["title"],
                        prob_justa=prob_real,
                        ev_real=ev,
                        score_qualidade=score,
                        nivel_confianca=nivel,
                        mercados_sugeridos=mercados,
                        melhor_call=f"{s_out['name']} @ {s_out['price']}",
                        justificativa="",
                        contexto="",
                        fonte_dados=provedor.upper()
                    )
                    
                    analise.justificativa = gerar_justificativa(analise)
                    
                    async with lock_oportunidades:
                        heapq.heappush(oportunidades_dia, (-score, analise))

async def enviar_melhores_do_dia(session):
    global oportunidades_dia, dia_atual
    
    async with lock_oportunidades:
        if not oportunidades_dia:
            print("ℹ️ Basquete: Nenhuma oportunidade de qualidade encontrada hoje")
            return
        
        melhores = []
        while len(melhores) < MAX_APOSTAS_POR_DIA and oportunidades_dia:
            _, analise = heapq.heappop(oportunidades_dia)
            melhores.append(analise)
        
        oportunidades_dia = []
    
    if not melhores:
        return
    
    hoje = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime('%d/%m/%Y')
    fontes = list(set([m.fonte_dados for m in melhores]))
    
    resumo = (
        f"🏀 <b>TOP CALLS DO DIA - {hoje}</b>\n\n"
        f"Selecionadas {len(melhores)} melhores oportunidades de basquete.\n\n"
        f"📊 Fontes: {', '.join(fontes)}\n"
        f"📊 Critérios: EV ≥ {MIN_EV_PERCENT*100:.1f}%, Odd ≤ {MAX_ODD}\n"
        f"⚠️ Máximo {MAX_APOSTAS_POR_DIA} calls por dia"
    )
    
    try:
        await session.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": resumo, "parse_mode": "HTML"},
            timeout=10
        )
    except:
        pass
    
    for i, analise in enumerate(melhores, 1):
        analise.contexto = f"🏆 Ranking #{i} do dia | Score: {analise.score_qualidade:.0f}/100"
        await enviar_telegram_profissional(session, analise)
        salvar_aposta_banco(analise, 1.5)
        jogos_enviados[analise.jogo_id] = datetime.now(ZoneInfo("America/Sao_Paulo")) + timedelta(hours=24)
        await asyncio.sleep(1)

# ==========================================
# LOOP PRINCIPAL
# ==========================================

async def loop_infinito():
    global oportunidades_dia, dia_atual, BALLDONTLIE_KEYS, ODDS_API_KEYS
    global SGO_API_KEYS, THE_ODDS_TOKEN_KEYS, THE_ODDS_API_LEGACY_KEYS, SPORTDB_KEYS
    
    # FASE 1: VALIDAÇÃO DE CHAVES
    print("🔍 FASE 1: VALIDANDO TODAS AS CHAVES DE API...")
    async with aiohttp.ClientSession() as session:
        await key_validator.validar_todas_chaves(session)
    
    # FASE 2: CONFIGURAR ROTAÇÃO SIMULTÂNEA
    print("\n🔄 FASE 2: CONFIGURANDO ROTAÇÃO SIMULTÂNEA...")
    rotacao.inicializar({
        "balldontlie": BALLDONTLIE_KEYS,
        "odds_api": ODDS_API_KEYS,
        "sgo": SGO_API_KEYS,
        "the_odds_token": THE_ODDS_TOKEN_KEYS,
        "the_odds_api_legacy": THE_ODDS_API_LEGACY_KEYS,
        "sportdb": SPORTDB_KEYS
    })
    
    # Estatísticas iniciais
    total_chaves_validas = sum(len(v) for v in key_validator.chaves_validas.values())
    total_chaves_invalidas = sum(len(v) for v in key_validator.chaves_invalidas.values())
    
    print(f"\n{'='*50}")
    print(f"🚀 Bot Basquete iniciado!")
    print(f"✅ Chaves válidas: {total_chaves_validas}")
    print(f"❌ Chaves inválidas: {total_chaves_invalidas}")
    print(f"🔄 Sistema de rotação simultânea ativo")
    print(f"💾 Cache: odds_cache_basquete.db")
    print(f"🤖 Bots Telegram: 3 (failover)")
    print(f"{'='*50}\n")
    
    carregar_memoria_banco()
    
    while True:
        async with aiohttp.ClientSession() as session:
            agora_br = datetime.now(ZoneInfo("America/Sao_Paulo"))
            hoje = agora_br.date()
            
            if dia_atual != hoje:
                async with lock_oportunidades:
                    oportunidades_dia = []
                dia_atual = hoje
                print(f"📅 Novo dia iniciado: {hoje}")
            
            print(f"🏀 Varredura Basquete: {agora_br.strftime('%H:%M')}")
            
            for liga in LIGAS:
                await processar_liga_async(session, liga, agora_br)
                await asyncio.sleep(2)
            
            await enviar_melhores_do_dia(session)
            
            if provedores_falhos:
                print(f"🔄 Limpando {len(provedores_falhos)} provedores falhos")
                provedores_falhos.clear()
            
            limpos = odds_cache.limpar_expirados()
            if limpos > 0:
                print(f"🧹 {limpos} entradas de cache removidas")
            
            # Estatísticas de rotação
            rot_stats = rotacao.get_estatisticas()
            print(f"\n📊 Estatísticas de Rotação:")
            for provedor, stats in rot_stats.items():
                if stats['total_requisicoes'] > 0:
                    print(f"  {provedor}: {stats['total_requisicoes']} reqs (média: {stats['media_por_chave']:.1f}/chave)")
            
            hoje_str = datetime.now().strftime("%Y%m%d")
            total_req = sum(v for k, v in request_count.items() if k.endswith(f"_{hoje_str}"))
            cache_stats = odds_cache.estatisticas()
            
            print(f"\n📊 Total requisições hoje: {total_req}")
            print(f"💾 Cache hit rate: {cache_stats['hit_rate']:.1f}%")
            print(provider_manager.get_health_report())
            print(f"💤 Aguardando {SCAN_INTERVAL/3600:.1f}h...")
            print("="*50)
        
        await asyncio.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    try:
        asyncio.run(loop_infinito())
    except KeyboardInterrupt:
        print("\n🛑 Bot Basquete encerrado")
        print(f"📊 Estatísticas finais de rotação: {rotacao.get_estatisticas()}")
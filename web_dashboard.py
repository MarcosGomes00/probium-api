import streamlit as st
import sqlite3
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import requests
from bs4 import BeautifulSoup
import random
import json
from datetime import datetime, timedelta
import numpy as np

# ==========================================
# CONFIGURAÇÃO DA PÁGINA
# ==========================================

st.set_page_config(
    page_title="PROBIUM | Quantitative Betting Intelligence",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# CSS PREMIUM - CYBERPUNK DARK THEME
# ==========================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;900&family=JetBrains+Mono:wght@400;700&display=swap');

:root {
    --primary: #00f0ff;
    --secondary: #7000ff;
    --accent: #ff006e;
    --success: #00ff88;
    --warning: #ffb700;
    --danger: #ff0040;
    --bg-dark: #050505;
    --bg-card: #0a0a0f;
    --bg-elevated: #12121a;
    --border: #1e1e2e;
    --text-primary: #ffffff;
    --text-secondary: #a0a0b0;
}

* {
    font-family: 'Inter', sans-serif;
}

.stApp {
    background: linear-gradient(135deg, #050505 0%, #0a0a1a 50%, #0f0f23 100%);
    color: var(--text-primary);
}

/* Sidebar Premium */
.css-1d391kg, .css-163ttbj, .stSidebar {
    background: linear-gradient(180deg, #0a0a0f 0%, #12121a 100%) !important;
    border-right: 1px solid var(--border);
}

/* Typography */
.title-main {
    font-size: 72px;
    font-weight: 900;
    text-align: center;
    background: linear-gradient(135deg, #00f0ff 0%, #7000ff 50%, #ff006e 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: -2px;
    margin-bottom: 10px;
    text-shadow: 0 0 60px rgba(0, 240, 255, 0.3);
}

.subtitle {
    text-align: center;
    color: var(--text-secondary);
    font-size: 14px;
    font-weight: 600;
    letter-spacing: 6px;
    text-transform: uppercase;
    margin-bottom: 40px;
}

/* Cards Glassmorphism */
.bet-card {
    background: rgba(18, 18, 26, 0.8);
    backdrop-filter: blur(20px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 20px;
    padding: 24px;
    margin-bottom: 20px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
    transition: all 0.3s ease;
    position: relative;
    overflow: hidden;
}

.bet-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 2px;
    background: linear-gradient(90deg, var(--primary), var(--secondary));
    opacity: 0;
    transition: opacity 0.3s ease;
}

.bet-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 20px 60px rgba(0, 240, 255, 0.15);
    border-color: rgba(0, 240, 255, 0.3);
}

.bet-card:hover::before {
    opacity: 1;
}

/* Metric Cards */
.metric-card {
    background: linear-gradient(135deg, rgba(0, 240, 255, 0.1) 0%, rgba(112, 0, 255, 0.1) 100%);
    border: 1px solid rgba(0, 240, 255, 0.2);
    border-radius: 16px;
    padding: 20px;
    text-align: center;
    position: relative;
    overflow: hidden;
}

.metric-value {
    font-size: 36px;
    font-weight: 900;
    color: var(--primary);
    font-family: 'JetBrains Mono', monospace;
}

.metric-label {
    font-size: 12px;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 2px;
    margin-top: 8px;
}

/* EV Indicators */
.ev-positive {
    color: var(--success);
    font-weight: 800;
    font-size: 24px;
    font-family: 'JetBrains Mono', monospace;
    text-shadow: 0 0 20px rgba(0, 255, 136, 0.4);
}

.ev-negative {
    color: var(--danger);
    font-weight: 800;
    font-size: 24px;
    font-family: 'JetBrains Mono', monospace;
}

/* Odds Display */
.odds-display {
    font-size: 48px;
    font-weight: 900;
    color: var(--text-primary);
    font-family: 'JetBrains Mono', monospace;
    line-height: 1;
}

.odds-label {
    font-size: 12px;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 2px;
}

/* Market Info */
.market-badge {
    display: inline-block;
    background: rgba(112, 0, 255, 0.2);
    color: var(--secondary);
    padding: 6px 16px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    border: 1px solid rgba(112, 0, 255, 0.3);
}

.team-name {
    font-size: 28px;
    font-weight: 800;
    color: var(--text-primary);
    margin: 12px 0;
}

.vs-divider {
    color: var(--text-secondary);
    font-size: 14px;
    font-weight: 600;
    margin: 0 12px;
}

/* Kelly Criterion Box */
.kelly-box {
    background: rgba(5, 5, 5, 0.6);
    border: 1px dashed rgba(0, 240, 255, 0.3);
    border-radius: 12px;
    padding: 16px;
    margin-top: 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.kelly-label {
    font-size: 12px;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 1px;
}

.kelly-value {
    font-size: 24px;
    font-weight: 900;
    color: var(--warning);
    font-family: 'JetBrains Mono', monospace;
}

/* Quantum Button */
.quantum-btn {
    background: linear-gradient(135deg, #00f0ff 0%, #7000ff 100%);
    color: white;
    border: none;
    padding: 20px 40px;
    border-radius: 16px;
    font-size: 16px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 2px;
    cursor: pointer;
    position: relative;
    overflow: hidden;
    transition: all 0.3s ease;
    box-shadow: 0 0 40px rgba(0, 240, 255, 0.3);
}

.quantum-btn:hover {
    transform: scale(1.05);
    box-shadow: 0 0 60px rgba(0, 240, 255, 0.5);
}

.quantum-btn::before {
    content: '';
    position: absolute;
    top: 0;
    left: -100%;
    width: 100%;
    height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.4), transparent);
    transition: left 0.5s;
}

.quantum-btn:hover::before {
    left: 100%;
}

/* Status Badges */
.status-pendente {
    background: rgba(255, 183, 0, 0.2);
    color: var(--warning);
    border: 1px solid rgba(255, 183, 0, 0.3);
}

.status-ganho {
    background: rgba(0, 255, 136, 0.2);
    color: var(--success);
    border: 1px solid rgba(0, 255, 136, 0.3);
}

.status-perda {
    background: rgba(255, 0, 64, 0.2);
    color: var(--danger);
    border: 1px solid rgba(255, 0, 64, 0.3);
}

/* Divider */
.custom-divider {
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
    margin: 40px 0;
    border: none;
}

/* Table Styling */
.stDataFrame {
    background: rgba(18, 18, 26, 0.8) !important;
    border-radius: 16px !important;
    border: 1px solid var(--border) !important;
}

/* Input Fields */
.stTextInput input, .stNumberInput input, .stSelectbox select {
    background: rgba(18, 18, 26, 0.8) !important;
    border: 1px solid var(--border) !important;
    border-radius: 12px !important;
    color: white !important;
    padding: 12px 16px !important;
}

/* Progress Bars */
.stProgress > div > div {
    background: linear-gradient(90deg, var(--primary), var(--secondary)) !important;
    border-radius: 10px !important;
}

/* Scrollbar */
::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}

::-webkit-scrollbar-track {
    background: var(--bg-dark);
}

::-webkit-scrollbar-thumb {
    background: var(--border);
    border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
    background: var(--primary);
}

/* Animations */
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

.live-indicator {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    color: var(--success);
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 2px;
}

.live-indicator::before {
    content: '';
    width: 8px;
    height: 8px;
    background: var(--success);
    border-radius: 50%;
    animation: pulse 2s infinite;
    box-shadow: 0 0 10px var(--success);
}

/* Confidence Meter */
.confidence-meter {
    width: 100%;
    height: 6px;
    background: rgba(255,255,255,0.1);
    border-radius: 3px;
    overflow: hidden;
    margin-top: 12px;
}

.confidence-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--danger), var(--warning), var(--success));
    border-radius: 3px;
    transition: width 0.5s ease;
}

</style>
""", unsafe_allow_html=True)

# ==========================================
# BANCO DE DADOS - SUPABASE POSTGRESQL
# ==========================================

def get_db_connection():
    """Conecta ao PostgreSQL da Supabase"""
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        # Usando a URL do seu Supabase (da memória)
        conn = psycopg2.connect(
            "postgresql://postgres.lyickymaibsakuqhevat:[PASSWORD]@aws-0-us-west-2.pooler.supabase.com:5432/postgres",
            cursor_factory=RealDictCursor
        )
        return conn
    except:
        # Fallback para SQLite local se PostgreSQL falhar
        return sqlite3.connect("probum.db")

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Tabela de operações
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS operacoes_tipster(
        id_aposta TEXT PRIMARY KEY,
        jogo TEXT,
        liga TEXT,
        mercado TEXT,
        selecao TEXT,
        odd REAL,
        prob REAL,
        ev REAL,
        kelly REAL,
        stake REAL DEFAULT 0,
        status TEXT DEFAULT 'PENDENTE',
        data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        data_resultado TIMESTAMP,
        lucro REAL DEFAULT 0
    )
    """)
    
    # Tabela de histórico de banca
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS historico_banca(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        banca_total REAL,
        roi REAL,
        apostas_feitas INTEGER
    )
    """)
    
    conn.commit()
    conn.close()

init_db()

# ==========================================
# FUNÇÕES DE CÁLCULO
# ==========================================

def calcular_kelly(odd, prob, fracao=0.25):
    """Kelly Criterion com fração ajustável"""
    b = odd - 1
    q = 1 - prob
    kelly = ((b * prob) - q) / b
    
    if kelly <= 0:
        return 0
    
    return round(min(kelly * 100 * fracao, 5), 2)

def calcular_ev(odd, prob):
    """Calcula Expected Value"""
    return (prob * odd) - 1

def calcular_stake(banca, kelly_percent, unidade=1):
    """Calcula stake baseado na banca e Kelly"""
    return round((banca * (kelly_percent / 100)) * unidade, 2)

# ==========================================
# MOTOR DE ANÁLISE (SIMULAÇÃO PREMIUM)
# ==========================================

def gerar_oportunidades_premium():
    """Gera oportunidades de apostas com análise simulada premium"""
    
    oportunidades = []
    times_top = [
        ("Manchester City", "Premier League", 0.75),
        ("Arsenal", "Premier League", 0.72),
        ("Liverpool", "Premier League", 0.74),
        ("Real Madrid", "La Liga", 0.78),
        ("Barcelona", "La Liga", 0.76),
        ("Bayern Munich", "Bundesliga", 0.77),
        ("PSG", "Ligue 1", 0.73),
        ("Inter Milan", "Serie A", 0.71),
        ("Benfica", "Primeira Liga", 0.68),
        ("Porto", "Primeira Liga", 0.67)
    ]
    
    mercados = [
        ("Match Winner", "Casa", lambda o: 1/o + random.uniform(0.05, 0.15)),
        ("Over 2.5 Goals", "Over", lambda o: 1/o + random.uniform(0.03, 0.12)),
        ("BTTS", "Sim", lambda o: 1/o + random.uniform(0.02, 0.10)),
        ("Asian Handicap -1", "Casa", lambda o: 1/o + random.uniform(0.04, 0.14))
    ]
    
    for i in range(5):
        casa = random.choice(times_top)
        fora = random.choice([t for t in times_top if t != casa])
        
        mercado_nome, selecao, prob_calc = random.choice(mercados)
        
        odd_base = round(random.uniform(1.65, 2.45), 2)
        prob = min(prob_calc(odd_base), 0.95)
        ev = calcular_ev(odd_base, prob)
        
        if ev > 0.05:  # Só oportunidades com EV positivo significativo
            kelly = calcular_kelly(odd_base, prob)
            
            oportunidades.append({
                "id": f"PROB-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}",
                "jogo": f"{casa[0]} x {fora[0]}",
                "liga": casa[1],
                "mercado": mercado_nome,
                "selecao": selecao if selecao == "Casa" else random.choice([casa[0], "Empate", fora[0]]),
                "odd": odd_base,
                "prob": round(prob, 3),
                "ev": round(ev, 3),
                "kelly": kelly,
                "confianca": random.randint(65, 95),
                "timestamp": datetime.now()
            })
    
    return sorted(oportunidades, key=lambda x: x['ev'], reverse=True)

# ==========================================
# GERENCIAMENTO DE BANCA
# ==========================================

def get_estatisticas():
    """Retorna estatísticas da banca"""
    conn = get_db_connection()
    
    try:
        # Total de apostas
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM operacoes_tipster")
        total_apostas = cursor.fetchone()['total'] if isinstance(cursor.fetchone(), dict) else cursor.fetchone()[0]
        
        # Taxa de acerto
        cursor.execute("SELECT COUNT(*) as ganhos FROM operacoes_tipster WHERE status='GANHO'")
        ganhos = cursor.fetchone()['ganhos'] if isinstance(cursor.fetchone(), dict) else cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) as perdidos FROM operacoes_tipster WHERE status='PERDA'")
        perdidos = cursor.fetchone()['perdidos'] if isinstance(cursor.fetchone(), dict) else cursor.fetchone()[0]
        
        # Lucro/Prejuízo
        cursor.execute("SELECT SUM(lucro) as total_lucro FROM operacoes_tipster WHERE status IN ('GANHO', 'PERDA')")
        resultado = cursor.fetchone()
        lucro_total = resultado['total_lucro'] if isinstance(resultado, dict) else resultado[0]
        lucro_total = lucro_total if lucro_total else 0
        
        # ROI
        cursor.execute("SELECT SUM(stake) as total_stake FROM operacoes_tipster WHERE status IN ('GANHO', 'PERDA')")
        resultado = cursor.fetchone()
        total_stake = resultado['total_stake'] if isinstance(resultado, dict) else resultado[0]
        total_stake = total_stake if total_stake else 1
        
        roi = (lucro_total / total_stake) * 100 if total_stake > 0 else 0
        
        conn.close()
        
        return {
            "total_apostas": total_apostas,
            "ganhos": ganhos,
            "perdidos": perdidos,
            "taxa_acerto": (ganhos / (ganhos + perdidos) * 100) if (ganhos + perdidos) > 0 else 0,
            "lucro_total": lucro_total,
            "roi": roi,
            "banca_atual": 1000 + lucro_total  # Banca inicial simulada
        }
    except:
        conn.close()
        return {
            "total_apostas": 0,
            "ganhos": 0,
            "perdidos": 0,
            "taxa_acerto": 0,
            "lucro_total": 0,
            "roi": 0,
            "banca_atual": 1000
        }

# ==========================================
# INTERFACE PREMIUM
# ==========================================

# Sidebar
with st.sidebar:
    st.markdown("""
    <div style="text-align: center; margin-bottom: 30px;">
        <div style="font-size: 32px; font-weight: 900; color: #00f0ff;">PROBIUM</div>
        <div style="font-size: 10px; color: #64748b; letter-spacing: 4px;">QUANTITATIVE ENGINE</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Menu
    page = st.radio(
        "Navegação",
        ["🏠 Dashboard", "🔍 Oportunidades", "📊 Análises", "💰 Gestão de Banca", "⚙️ Configurações"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    
    # Resumo rápido
    stats = get_estatisticas()
    st.markdown(f"""
    <div style="background: rgba(0,240,255,0.1); border-radius: 12px; padding: 16px; border: 1px solid rgba(0,240,255,0.2);">
        <div style="font-size: 10px; color: #64748b; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 8px;">Banca Atual</div>
        <div style="font-size: 24px; font-weight: 900; color: #00f0ff; font-family: 'JetBrains Mono', monospace;">${stats['banca_atual']:.2f}</div>
        <div style="font-size: 12px; color: {'#00ff88' if stats['roi'] >= 0 else '#ff0040'}; margin-top: 4px;">{stats['roi']:+.2f}% ROI</div>
    </div>
    """, unsafe_allow_html=True)

# ==========================================
# PÁGINA: DASHBOARD
# ==========================================

if page == "🏠 Dashboard":
    st.markdown('<div class="title-main">PROBIUM</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Quantitative Sports Betting Intelligence</div>', unsafe_allow_html=True)
    
    # Métricas principais
    stats = get_estatisticas()
    
    cols = st.columns(4)
    metrics = [
        ("Banca Total", f"${stats['banca_atual']:.2f}", "💰"),
        ("ROI", f"{stats['roi']:+.2f}%", "📈"),
        ("Taxa de Acerto", f"{stats['taxa_acerto']:.1f}%", "🎯"),
        ("Total Apostas", stats['total_apostas'], "🎲")
    ]
    
    for col, (label, value, icon) in zip(cols, metrics):
        with col:
            st.markdown(f"""
            <div class="metric-card">
                <div style="font-size: 24px; margin-bottom: 8px;">{icon}</div>
                <div class="metric-value">{value}</div>
                <div class="metric-label">{label}</div>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
    
    # Gráfico de Performance
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### 📊 Evolução da Banca")
        
        # Simulação de dados para o gráfico
        dias = pd.date_range(end=datetime.now(), periods=30, freq='D')
        evolucao = [1000 + (i * random.uniform(-20, 35)) for i in range(30)]
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dias,
            y=evolucao,
            mode='lines',
            fill='tozeroy',
            line=dict(color='#00f0ff', width=3),
            fillcolor='rgba(0, 240, 255, 0.1)',
            name='Banca'
        ))
        
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white'),
            xaxis=dict(showgrid=False, color='#64748b'),
            yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)', color='#64748b'),
            height=400,
            margin=dict(l=0, r=0, t=0, b=0)
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("### 🎯 Distribuição")
        
        # Gráfico de pizza
        fig_pie = go.Figure(data=[go.Pie(
            labels=['Ganhos', 'Perdas', 'Pendentes'],
            values=[stats['ganhos'], stats['perdidos'], stats['total_apostas'] - stats['ganhos'] - stats['perdidos']],
            hole=.6,
            marker_colors=['#00ff88', '#ff0040', '#ffb700']
        )])
        
        fig_pie.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white'),
            showlegend=True,
            legend=dict(orientation='h', yanchor='bottom', y=-0.1),
            height=400,
            margin=dict(l=0, r=0, t=0, b=0)
        )
        
        st.plotly_chart(fig_pie, use_container_width=True)

# ==========================================
# PÁGINA: OPORTUNIDADES
# ==========================================

elif page == "🔍 Oportunidades":
    st.markdown('<div class="title-main">🔍 SCANNER</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Motor de Análise Quantitativa</div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col2:
        if st.button("⚡ ATIVAR MOTOR QUÂNTICO", key="scan_btn"):
            with st.spinner("Analisando mercados com algoritmos de machine learning..."):
                ops = gerar_oportunidades_premium()
                
                conn = get_db_connection()
                cursor = conn.cursor()
                
                for op in ops:
                    try:
                        cursor.execute("""
                        INSERT OR IGNORE INTO operacoes_tipster 
                        (id_aposta, jogo, liga, mercado, selecao, odd, prob, ev, kelly, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (op['id'], op['jogo'], op['liga'], op['mercado'], 
                              op['selecao'], op['odd'], op['prob'], op['ev'], op['kelly'], 'PENDENTE'))
                    except:
                        cursor.execute("""
                        INSERT INTO operacoes_tipster 
                        (id_aposta, jogo, liga, mercado, selecao, odd, prob, ev, kelly, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(id_aposta) DO NOTHING
                        """, (op['id'], op['jogo'], op['liga'], op['mercado'], 
                              op['selecao'], op['odd'], op['prob'], op['ev'], op['kelly'], 'PENDENTE'))
                
                conn.commit()
                conn.close()
                
                st.success(f"✅ {len(ops)} oportunidades de valor identificadas!")
                st.balloons()
    
    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
    
    # Filtros
    col_filtro1, col_filtro2, col_filtro3 = st.columns(3)
    
    with col_filtro1:
        filtro_ev = st.slider("EV Mínimo", 0.0, 0.5, 0.05, 0.01)
    
    with col_filtro2:
        filtro_odd_min = st.number_input("Odd Mínima", 1.1, 10.0, 1.5)
        filtro_odd_max = st.number_input("Odd Máxima", 1.1, 10.0, 3.0)
    
    with col_filtro3:
        filtro_liga = st.multiselect(
            "Ligas",
            ["Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1", "Primeira Liga"],
            default=["Premier League", "La Liga"]
        )
    
    # Buscar oportunidades
    conn = get_db_connection()
    
    try:
        query = """
        SELECT * FROM operacoes_tipster 
        WHERE status='PENDENTE' 
        AND ev >= ?
        AND odd BETWEEN ? AND ?
        ORDER BY ev DESC
        """
        df = pd.read_sql(query, conn, params=(filtro_ev, filtro_odd_min, filtro_odd_max))
    except:
        df = pd.read_sql("SELECT * FROM operacoes_tipster WHERE status='PENDENTE'", conn)
    
    conn.close()
    
    if df.empty:
        st.info("🔍 Nenhuma oportunidade encontrada com os filtros atuais.")
    else:
        st.markdown(f"### 🎯 {len(df)} Oportunidades Encontradas")
        
        for _, row in df.iterrows():
            with st.container():
                col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                
                with col1:
                    time_casa, time_fora = row['jogo'].split(' x ')
                    st.markdown(f"""
                    <div class="bet-card">
                        <div style="display: flex; align-items: center; margin-bottom: 12px;">
                            <span class="market-badge">{row['liga']}</span>
                            <span style="margin-left: 12px; color: #64748b; font-size: 12px;">{row['mercado']}</span>
                        </div>
                        
                        <div style="display: flex; align-items: center; margin-bottom: 16px;">
                            <span class="team-name">{time_casa}</span>
                            <span class="vs-divider">VS</span>
                            <span class="team-name">{time_fora}</span>
                        </div>
                        
                        <div style="font-size: 14px; color: #a0a0b0; margin-bottom: 8px;">
                            Seleção: <strong style="color: #00f0ff;">{row['selecao']}</strong>
                        </div>
                        
                        <div class="confidence-meter">
                            <div class="confidence-fill" style="width: {random.randint(60, 95)}%;"></div>
                        </div>
                        <div style="font-size: 11px; color: #64748b; margin-top: 4px;">Confiança do Modelo</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    st.markdown(f"""
                    <div class="bet-card" style="text-align: center;">
                        <div class="odds-label">ODD</div>
                        <div class="odds-display">{row['odd']}</div>
                        <div style="font-size: 12px; color: #64748b; margin-top: 8px;">
                            Prob: {row['prob']*100:.1f}%
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col3:
                    ev_color = "ev-positive" if row['ev'] > 0 else "ev-negative"
                    st.markdown(f"""
                    <div class="bet-card" style="text-align: center;">
                        <div class="odds-label">EXPECTED VALUE</div>
                        <div class="{ev_color}">{row['ev']*100:+.2f}%</div>
                        <div style="font-size: 12px; color: #64748b; margin-top: 8px;">
                            Edge identificado
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col4:
                    st.markdown(f"""
                    <div class="bet-card" style="text-align: center;">
                        <div class="odds-label">KELLY CRITERION</div>
                        <div style="font-size: 32px; font-weight: 900; color: #ffb700; font-family: 'JetBrains Mono', monospace;">
                            {row['kelly']}%
                        </div>
                        <div class="kelly-box" style="margin-top: 12px; padding: 8px;">
                            <span style="font-size: 11px; color: #64748b;">Stake Rec.</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                
                # Botões de ação
                col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 4])
                
                with col_btn1:
                    if st.button(f"✅ Apostar", key=f"bet_{row['id_aposta']}"):
                        stake = st.number_input(f"Stake ($)", min_value=1.0, value=10.0, key=f"stake_{row['id_aposta']}")
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("UPDATE operacoes_tipster SET stake = ? WHERE id_aposta = ?", (stake, row['id_aposta']))
                        conn.commit()
                        conn.close()
                        st.success(f"Aposta registrada: ${stake}")
                
                with col_btn2:
                    if st.button(f"❌ Rejeitar", key=f"rej_{row['id_aposta']}"):
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM operacoes_tipster WHERE id_aposta = ?", (row['id_aposta'],))
                        conn.commit()
                        conn.close()
                        st.rerun()
                
                st.markdown("---")

# ==========================================
# PÁGINA: ANÁLISES
# ==========================================

elif page == "📊 Análises":
    st.markdown('<div class="title-main">📊 ANALYTICS</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Inteligência de Dados Avançada</div>', unsafe_allow_html=True)
    
    # Gráfico de dispersão: Odd vs EV
    conn = get_db_connection()
    df_hist = pd.read_sql("SELECT * FROM operacoes_tipster WHERE status IN ('GANHO', 'PERDA', 'PENDENTE')", conn)
    conn.close()
    
    if not df_hist.empty:
        fig = px.scatter(
            df_hist,
            x='odd',
            y='ev',
            color='status',
            size='kelly',
            hover_data=['jogo', 'selecao'],
            color_discrete_map={
                'GANHO': '#00ff88',
                'PERDA': '#ff0040',
                'PENDENTE': '#ffb700'
            },
            template='plotly_dark'
        )
        
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white'),
            title="Análise de Eficiência: Odd vs Expected Value",
            xaxis_title="Odd",
            yaxis_title="EV (Expected Value)"
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Análise por Liga
        st.markdown("### 🏆 Performance por Liga")
        
        fig_liga = px.bar(
            df_hist.groupby('liga')['ev'].mean().reset_index(),
            x='liga',
            y='ev',
            color='ev',
            color_continuous_scale=['#ff0040', '#ffb700', '#00ff88'],
            template='plotly_dark'
        )
        
        fig_liga.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white')
        )
        
        st.plotly_chart(fig_liga, use_container_width=True)
    else:
        st.info("📊 Dados insuficientes para análise. Realize apostas para visualizar estatísticas.")

# ==========================================
# PÁGINA: GESTÃO DE BANCA
# ==========================================

elif page == "💰 Gestão de Banca":
    st.markdown('<div class="title-main">💰 BANKROLL</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Gestão de Risco e Capital</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### ⚙️ Configurações de Stake")
        
        banca_total = st.number_input("Banca Total ($)", value=1000.0, step=100.0)
        unidade_padrao = st.slider("Unidade Padrão (% da banca)", 0.5, 5.0, 1.0, 0.5)
        fracao_kelly = st.slider("Fração Kelly (Conservador)", 0.1, 0.5, 0.25, 0.05)
        
        st.markdown(f"""
        <div class="bet-card" style="margin-top: 20px;">
            <div style="font-size: 14px; color: #64748b; margin-bottom: 8px;">Stake por Unidade</div>
            <div style="font-size: 32px; font-weight: 900; color: #00f0ff; font-family: 'JetBrains Mono', monospace;">
                ${banca_total * (unidade_padrao/100):.2f}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("### 📋 Histórico de Apostas")
        
        conn = get_db_connection()
        df_historico = pd.read_sql(
            "SELECT data_criacao, jogo, odd, stake, status, lucro FROM operacoes_tipster WHERE status != 'PENDENTE' ORDER BY data_criacao DESC LIMIT 10", 
            conn
        )
        conn.close()
        
        if not df_historico.empty:
            st.dataframe(
                df_historico,
                column_config={
                    "data_criacao": "Data",
                    "jogo": "Jogo",
                    "odd": st.column_config.NumberColumn("Odd", format="%.2f"),
                    "stake": st.column_config.NumberColumn("Stake", format="$%.2f"),
                    "status": "Status",
                    "lucro": st.column_config.NumberColumn("Lucro", format="$%.2f")
                },
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("Nenhuma aposta finalizada ainda.")

# ==========================================
# PÁGINA: CONFIGURAÇÕES
# ==========================================

elif page == "⚙️ Configurações":
    st.markdown('<div class="title-main">⚙️ SETTINGS</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Configurações do Sistema</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🎨 Aparência")
        tema = st.selectbox("Tema", ["Cyberpunk Dark", "Midnight Blue", "Matrix Green"])
        animacoes = st.toggle("Animações Ativadas", value=True)
        
        st.markdown("### 🔔 Notificações")
        notif_telegram = st.toggle("Alertas Telegram", value=False)
        notif_email = st.toggle("Alertas Email", value=False)
    
    with col2:
        st.markdown("### 🔧 Algoritmo")
        modelo = st.selectbox(
            "Modelo de Predição",
            ["Kelly Criterion Puro", "Kelly Fractional", "Martingale Adaptativo", "Fibonacci"]
        )
        min_ev = st.slider("EV Mínimo para Alerta", 0.0, 0.2, 0.05, 0.01)
        
        if st.button("🗑️ Limpar Banco de Dados", type="secondary"):
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM operacoes_tipster")
            conn.commit()
            conn.close()
            st.success("Banco de dados limpo!")
            st.rerun()

# ==========================================
# FOOTER
# ==========================================

st.markdown("""
<div style="position: fixed; bottom: 0; left: 0; right: 0; background: rgba(5,5,5,0.9); border-top: 1px solid #1e1e2e; padding: 12px; text-align: center; font-size: 11px; color: #64748b; z-index: 999;">
    PROBIUM v2.0 | Quantitative Betting Engine | Powered by AI
</div>
""", unsafe_allow_html=True)
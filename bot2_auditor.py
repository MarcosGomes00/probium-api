import sqlite3
import requests
import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# ==========================================
# 1. CONFIGURAÇÕES
# ==========================================
# Use a sua chave principal da The Odds API para checar resultados
API_KEY_ODDS = "6a1c0078b3ed09b42fbacee8f07e7cc3" 

TELEGRAM_TOKEN = "8725909088:AAGQMNr-9RVQB7hWmePCLmm0GwaGuzOVy-A"
CHAT_ID = "-1003814625223"
DB_FILE = "probum.db"

def enviar_telegram(texto):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": texto, "parse_mode": "HTML"}
    try: requests.post(url, json=payload, timeout=10)
    except: pass

def obter_resultados_api(esporte):
    """Busca os placares finais dos jogos encerrados nas últimas 48h"""
    url = f"https://api.the-odds-api.com/v4/sports/{esporte}/scores/"
    params = {"apiKey": API_KEY_ODDS, "daysFrom": 2}
    try:
        res = requests.get(url, params=params, timeout=15)
        if res.status_code == 200:
            return res.json()
    except: pass
    return[]

def resolver_aposta(aposta, placar):
    """Lógica que decide se foi Green ou Red baseado no placar e na aposta"""
    mercado = aposta['mercado']
    selecao = aposta['selecao']
    odd = aposta['odd']
    stake = aposta['stake']
    
    # Extrai pontuações do placar da API
    scores = placar.get("scores",[])
    if not scores or len(scores) < 2: return "PENDENTE", 0
    
    home_score = int(scores[0]["score"])
    away_score = int(scores[1]["score"])
    total_gols = home_score + away_score

    status = "RED"
    lucro = -stake # Perdeu a stake
    
    # 1. VALIDAÇÃO VENCEDOR (1X2)
    if mercado == "Vencedor (1X2)":
        if "Empate" in selecao and home_score == away_score: status = "GREEN"
        elif placar["home_team"] in selecao and home_score > away_score: status = "GREEN"
        elif placar["away_team"] in selecao and away_score > home_score: status = "GREEN"

    # 2. VALIDAÇÃO AMBAS MARCAM (BTTS)
    elif mercado == "Ambas Marcam":
        if selecao == "Sim" and home_score > 0 and away_score > 0: status = "GREEN"
        elif selecao == "Não" and (home_score == 0 or away_score == 0): status = "GREEN"

    # 3. VALIDAÇÃO GOLS/PONTOS (OVER/UNDER)
    elif "Gols/Pontos" in mercado:
        try:
            linha = float(selecao.split(" ")[1])
            if "Over" in selecao and total_gols > linha: status = "GREEN"
            elif "Under" in selecao and total_gols < linha: status = "GREEN"
        except: pass

    # Se bateu (GREEN), o lucro é a Stake vezes a Odd (tirando o investimento inicial)
    if status == "GREEN":
        lucro = (stake * odd) - stake
        
    return status, lucro

def rotina_fechamento_diario():
    agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
    print(f"[{agora.strftime('%H:%M:%S')}] Iniciando Auditoria e Dashboard...")
    
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. BUSCA TODAS AS APOSTAS PENDENTES NO BANCO DE DADOS
    cursor.execute("SELECT * FROM operacoes_tipster WHERE status = 'PENDENTE'")
    pendentes = cursor.fetchall()
    
    if pendentes:
        # Agrupa os esportes pendentes para não gastar requisições atoa
        esportes_pendentes = set(p["esporte"] for p in pendentes)
        placares_globais = {}
        
        for esporte in esportes_pendentes:
            placares = obter_resultados_api(esporte)
            for p in placares:
                if p.get("completed"): # Apenas jogos que já acabaram
                    placares_globais[p["id"]] = p
                    
        # 2. RESOLVE AS APOSTAS
        apostas_resolvidas = 0
        for aposta in pendentes:
            jogo_id_api = aposta["id_aposta"].split("_")[0]
            
            if jogo_id_api in placares_globais:
                placar_jogo = placares_globais[jogo_id_api]
                novo_status, lucro = resolver_aposta(aposta, placar_jogo)
                
                if novo_status != "PENDENTE":
                    cursor.execute("""
                        UPDATE operacoes_tipster 
                        SET status = ?, lucro = ? 
                        WHERE id_aposta = ?
                    """, (novo_status, lucro, aposta["id_aposta"]))
                    apostas_resolvidas += 1
                    
        conn.commit()
        print(f"✅ {apostas_resolvidas} apostas resolvidas no banco de dados!")

    # ===============================================
    # 3. GERADOR DO DASHBOARD (FECHAMENTO DE CAIXA)
    # ===============================================
    ontem = (agora - timedelta(days=1)).strftime('%d/%m/%Y')
    
    cursor.execute("SELECT status, lucro, stake FROM operacoes_tipster WHERE data_hora = ? AND status != 'PENDENTE'", (ontem,))
    operacoes_ontem = cursor.fetchall()
    
    if operacoes_ontem:
        total_greens = sum(1 for op in operacoes_ontem if op["status"] == "GREEN")
        total_reds = sum(1 for op in operacoes_ontem if op["status"] == "RED")
        total_apostas = total_greens + total_reds
        
        win_rate = (total_greens / total_apostas) * 100 if total_apostas > 0 else 0
        lucro_total = sum(op["lucro"] for op in operacoes_ontem)
        unidades_investidas = sum(op["stake"] for op in operacoes_ontem)
        roi = (lucro_total / unidades_investidas) * 100 if unidades_investidas > 0 else 0
        
        emoji_lucro = "💰" if lucro_total >= 0 else "🩸"
        sinal_lucro = "+" if lucro_total >= 0 else ""
        
        dashboard_msg = (
            f"📊 <b>FECHAMENTO DE CAIXA ({ontem})</b> 📊\n"
            f"<i>Auditoria automatizada do Sindicato.</i>\n\n"
            f"📈 <b>Apostas Finalizadas:</b> {total_apostas}\n"
            f"✅ <b>Greens:</b> {total_greens}\n"
            f"❌ <b>Reds:</b> {total_reds}\n"
            f"🎯 <b>Assertividade (Win-Rate):</b> {win_rate:.1f}%\n\n"
            f"💵 <b>Investimento Total:</b> {unidades_investidas:.2f} Unidades\n"
            f"{emoji_lucro} <b>Resultado Líquido:</b> {sinal_lucro}{lucro_total:.2f} Unidades\n"
            f"📈 <b>ROI (Retorno s/ Investimento):</b> {sinal_lucro}{roi:.2f}%\n\n"
            f"<i>*1 Unidade = 1% da sua Banca.</i>"
        )
        enviar_telegram(dashboard_msg)
        print("📲 Dashboard enviado para o Telegram!")
    else:
        print("😴 Nenhuma aposta finalizada ontem para gerar relatório.")

    conn.close()

if __name__ == "__main__":
    print("🤖 BOT 2 (AUDITOR) INICIADO!")
    # Roda a auditoria todo dia de manhã
    while True:
        agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
        # O Bot 2 vai checar os resultados sempre às 08:00 da manhã
        if agora.hour == 8 and agora.minute == 0:
            rotina_fechamento_diario()
            # Espera 61 segundos para não rodar duas vezes no mesmo minuto
            time.sleep(61)
        else:
            time.sleep(30)
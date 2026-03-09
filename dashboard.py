import sqlite3
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

# Configurações do BOT e Canal
TELEGRAM_BOT_TOKEN_2 = "8185027087:AAH1JQJKtlWy_oUQpAvqvHEsFIVOK3ScYBc"
CHAT_ID = "-1003814625223"
DB_FILE = "probum.db"

def enviar_telegram(texto):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN_2}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": texto, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload)
        print("✅ Dashboard Institucional enviado ao Telegram!")
    except Exception as e:
        print(f"Erro ao enviar: {e}")

def gerar_dashboard():
    try:
        # Conecta ao Banco de Dados Oficial
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        hoje = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime('%d/%m/%Y')
        mes_ano = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime('%m/%Y')
        
        # 1. Busca os resultados finalizados DO DIA de hoje
        cursor.execute("SELECT status, lucro, stake FROM operacoes_tipster WHERE data_hora = ? AND status != 'PENDENTE'", (hoje,))
        apostas_hoje = cursor.fetchall()
        
        # 2. Busca os resultados finalizados DO MÊS INTEIRO (Para o Acumulado)
        cursor.execute("SELECT status, lucro, stake FROM operacoes_tipster WHERE data_hora LIKE ? AND status != 'PENDENTE'", (f"%{mes_ano}",))
        apostas_mes = cursor.fetchall()
        
        conn.close()
        
        if not apostas_hoje:
            print("Nenhuma aposta finalizada hoje para gerar o relatório.")
            return

        # --- CÁLCULOS DO DIA ---
        total_hoje = len(apostas_hoje)
        greens_hoje = sum(1 for a in apostas_hoje if a[0] == 'GREEN')
        reds_hoje = sum(1 for a in apostas_hoje if a[0] == 'RED')
        reembolsos_hoje = sum(1 for a in apostas_hoje if a[0] == 'REEMBOLSO')
        
        lucro_hoje = sum(a[1] for a in apostas_hoje)
        stake_investida_hoje = sum(a[2] for a in apostas_hoje)
        
        # Win Rate (Não contabiliza as devolvidas no cálculo)
        apostas_validas = total_hoje - reembolsos_hoje
        win_rate_hoje = (greens_hoje / apostas_validas) * 100 if apostas_validas > 0 else 0
        
        # Yield (O indicador financeiro mais importante)
        yield_hoje = (lucro_hoje / stake_investida_hoje) * 100 if stake_investida_hoje > 0 else 0

        # --- CÁLCULOS DO MÊS ---
        lucro_mes = sum(a[1] for a in apostas_mes)
        stake_mes = sum(a[2] for a in apostas_mes)
        yield_mes = (lucro_mes / stake_mes) * 100 if stake_mes > 0 else 0
        
        # --- FORMATAÇÃO VISUAL PREMIUM ---
        if lucro_hoje > 0:
            saldo_msg = f"🟢 <b>LUCRO DO DIA:</b> +{lucro_hoje:.2f} Unidades"
        elif lucro_hoje < 0:
            saldo_msg = f"🔴 <b>PREJUÍZO:</b> {lucro_hoje:.2f} Unidades"
        else:
            saldo_msg = f"⚪️ <b>EMPATADO:</b> 0.00 Unidades"

        if lucro_mes > 0:
            mes_msg = f"🟢 +{lucro_mes:.2f} Unidades (Yield: {yield_mes:.1f}%)"
        else:
            mes_msg = f"🔴 {lucro_mes:.2f} Unidades (Yield: {yield_mes:.1f}%)"

        mensagem = (
            f"📊 <b>RELATÓRIO DE PERFORMANCE INSTITUCIONAL</b> 📊\n"
            f"🗓 <b>Data:</b> {hoje}\n\n"
            f"🎯 <b>Sinais Finalizados Hoje:</b> {total_hoje}\n"
            f"✅ <b>GREENS:</b> {greens_hoje}\n"
            f"❌ <b>REDS:</b> {reds_hoje}\n"
            f"🔄 <b>DEVOLVIDAS (VOID):</b> {reembolsos_hoje}\n\n"
            f"📈 <b>Taxa de Acerto (Win Rate):</b> {win_rate_hoje:.1f}%\n"
            f"💰 <b>Yield Diário (Retorno):</b> {yield_hoje:.1f}%\n\n"
            f"💵 <b>BALANÇO FINANCEIRO:</b>\n"
            f"{saldo_msg}\n\n"
            f"📆 <b>Acumulado do Mês ({mes_ano}):</b>\n"
            f"{mes_msg}\n\n"
            f"<i>Robô de Análise + Inteligência Artificial Quantitativa</i> 🤖"
        )

        enviar_telegram(mensagem)
        
    except Exception as e:
        print(f"Erro ao gerar dashboard: {e}")

if __name__ == "__main__":
    print("Gerando Dashboard Institucional...")
    gerar_dashboard()
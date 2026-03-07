import requests
from config import Config
from services.database import db
from sqlalchemy import text

# ========== BOT 1: ENVIA OS PALPITES ANTES DO JOGO ==========
def envia_alerta_pre_jogo(aposta):
    texto = (
        f"🎯 <b>OPORTUNIDADE DETECTADA (Bot 1)</b>\n"
        f"⚠️ Faltam menos de 30 minutos para o pontapé inicial!\n\n"
        f"⚽ <b>Confronto:</b> {aposta['jogo']}\n"
        f"🕒 <b>Início:</b> {aposta['horario'][:16].replace('T', ' ')}\n\n"
        f"💰 <b>OPERAÇÃO ESTATÍSTICA:</b> {aposta['mercado']}\n"
        f"📊 <b>Score IA:</b> {aposta['prob']}%\n"
        f"🔥 <i>Validação tripla (Últimos jogos + Defesa vs Ataque)</i>"
    )
    url = f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN_1}/sendMessage"
    resp = requests.post(url, json={"chat_id": Config.TELEGRAM_CHAT_ID, "text": texto, "parse_mode": "HTML"})
    
    # Salva no Banco para auditoria do Bot 2 depois!
    with db.engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO operacoes_tipster (fixture_id, jogo, data_hora, mercado_tipo, odd) "
            f"VALUES ({aposta['fix_id']}, '{aposta['jogo']}', '{aposta['horario']}', '{aposta['mercado_codigo']}', {aposta['odd']})"
        ))

# ========== BOT 2: FECHAMENTO DE CONTA E DASHBOARD ==========
def fechar_operacao_resolvida(jogo_nome, mercado_nome, resultado, odd):
    icone = "✅ GREEN DETECTADO!" if resultado == 'GREEN' else "❌ RED IDENTIFICADO"
    
    msg = f"<b>{icone} (BOT 2)</b>\n\n⚽ <b>Jogo:</b> {jogo_nome}\n💸 <b>Call Oficial:</b> {mercado_nome}\n\n<i>Banco de dados atualizado com o placar final oficial pela API Sports.</i>"
    url = f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN_2}/sendMessage"
    requests.post(url, json={"chat_id": Config.TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"})

def disparar_dashboard_bot2():
    """Puxa o extrato vitalício do SQL e gera a carteira"""
    with db.engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM operacoes_tipster WHERE status IN ('GREEN', 'RED')")).scalar()
        greens = conn.execute(text("SELECT COUNT(*) FROM operacoes_tipster WHERE status = 'GREEN'")).scalar()
        
    if total > 0:
        winrate = round((greens/total) * 100, 1)
        dash = (
            f"📈 <b>DASHBOARD DE OPERAÇÕES OFICIAIS PROBIUM (Longo Prazo)</b> 📈\n\n"
            f"📝 <b>Calls Encerradas (Auditadas Bot 2):</b> {total}\n"
            f"✅ <b>Take Profit (Greens):</b> {greens}\n"
            f"❌ <b>Stop Loss (Reds):</b> {total - greens}\n\n"
            f"🎯 <b>Assertividade Vitalícia (Win Rate):</b> {winrate}%\n"
        )
        url = f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN_2}/sendMessage"
        requests.post(url, json={"chat_id": Config.TELEGRAM_CHAT_ID, "text": dash, "parse_mode": "HTML"})
    else:
        print("Dashboard vazio ainda, pulando.")
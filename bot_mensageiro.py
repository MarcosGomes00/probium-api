import asyncio
import aiohttp
import sqlite3
import time

# ==========================================
# CONFIGURAÇÕES DO TELEGRAM
# ==========================================
TELEGRAM_TOKEN = "8725909088:AAGQMNr-9RVQB7hWmePCLmm0GwaGuzOVy-A"  # Token do seu Bot
CHAT_ID = "-1003814625223"  # ID do seu Grupo/Canal
DB_FILE = "probum.db"

async def enviar_mensagem(session, aposta):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    # Formatação de Luxo para o Telegram
    texto = (
        f"💎 <b>OPERAÇÃO NÍVEL DEUS DETECTADA</b> 💎\n\n"
        f"🏆 <b>Liga:</b> {aposta['liga']}\n"
        f"⚔️ <b>Jogo:</b> {aposta['jogo']}\n\n"
        f"🎯 <b>A OPERAÇÃO:</b> {aposta['mercado']} - {aposta['selecao']}\n"
        f"📈 <b>Odd Capturada:</b> {aposta['odd']:.2f}\n"
        f"📊 <b>EV (Vantagem Matemática):</b> +{(aposta['ev'] * 100):.1f}%\n"
        f"💰 <b>Gestão Kelly (Risco):</b> Usar {aposta['kelly_stake']:.1f}% da banca\n\n"
        f"🧠 <i>Insight do Oráculo:</i> {aposta.get('justificativa', 'Validado pelo consenso Web.')}\n\n"
        f"⚠️ <i>Acesse o Dashboard para ver o gráfico de pressão financeira (Dropping Odds).</i>"
    )
    
    payload = {"chat_id": CHAT_ID, "text": texto, "parse_mode": "HTML"}
    
    try:
        async with session.post(url, json=payload, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"Erro Telegram: {e}")
        return False

async def loop_mensageiro():
    print("🚀 O Mensageiro Nível DEUS está ativo.")
    print("👀 Vigiando o Banco de Dados em tempo real...")
    
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                # Conecta e lê usando WAL (Zero travamentos com o Site)
                conn = sqlite3.connect(DB_FILE)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Busca apenas apostas que o Dashboard encontrou e ainda não foram enviadas
                cursor.execute("SELECT * FROM operacoes_tipster WHERE telegram_enviado = 0 AND status = 'PENDENTE'")
                pendentes = cursor.fetchall()
                
                if pendentes:
                    print(f"⚡ Encontrei {len(pendentes)} novas operações geradas pelo Cérebro Web!")
                    for aposta in pendentes:
                        sucesso = await enviar_mensagem(session, dict(aposta))
                        
                        # Se enviou pro Telegram com sucesso, marca como lido no banco
                        if sucesso:
                            cursor.execute("UPDATE operacoes_tipster SET telegram_enviado = 1 WHERE id_aposta = ?", (aposta['id_aposta'],))
                            conn.commit()
                            print(f"✅ Call {aposta['jogo']} despachada com sucesso!")
                        await asyncio.sleep(2) # Anti-Spam do Telegram
                        
                conn.close()
            except Exception as e:
                print(f"Erro no Mensageiro: {e}")
            
            # Aguarda 10 segundos antes de checar o banco novamente
            await asyncio.sleep(10)

if __name__ == "__main__":
    try:
        asyncio.run(loop_mensageiro())
    except KeyboardInterrupt:
        print("\n🛑 Mensageiro encerrado.")
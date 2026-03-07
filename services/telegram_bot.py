import requests
from config import Config

def mandar_analises_para_grupo(bilhetes):
    if not bilhetes:
        enviar_mensagem("⚠️ <b>Aviso:</b> O sistema rastreou os dados de hoje e não encontrou oportunidades estatísticas viáveis para operar com segurança máxima.")
        return

    for aposta in bilhetes:
        texto_formatado = (
            f"🏆 <b>ANÁLISE DE ALTA PRECISÃO IA</b>\n"
            f"🌐 <b>Torneio:</b> {aposta['liga']}\n\n"
            f"⚽ <b>Confronto:</b> {aposta['jogo']}\n"
            f"🕒 <b>Início:</b> {aposta['horario'][:16].replace('T', ' ')}\n\n"
            f"🎯 <b>PALPITE INDICADO:</b>\n"
            f"💸 {aposta['palpite']}\n\n"
            f"📊 <b>Probabilidade Matemática:</b> {aposta['prob']}%\n"
            f"💹 <b>Odd Justa Projetada:</b> @{aposta['odd']}\n\n"
            f"🔥 <i>Análise fundamentada 100% em retrospecto e Head-to-Head histórico.</i>"
        )
        enviar_mensagem(texto_formatado)

def enviar_mensagem(texto):
    url = f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN_1}/sendMessage"
    payload = {
        "chat_id": Config.TELEGRAM_CHAT_ID,
        "text": texto,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("Sinal enviado ao Telegram com sucesso.")
        else:
            print(f"Erro na comunicação com o Telegram: {response.text}")
    except Exception as e:
        print(f"Falha técnica ao conectar com o Telegram: {e}")

def init_bot():
    print("Módulo do Telegram carregado com êxito.")
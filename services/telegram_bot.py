
from telegram import Bot
import logging

logger = logging.getLogger(__name__)

class TelegramService:

    def __init__(self, token, group):
        self.bot = Bot(token=token)
        self.group = group

    async def send_top10(self, analyses):

        msg = "🏆 TOP 10 PROBIUM - ANÁLISES DO DIA\n\n"

        for i,a in enumerate(analyses,1):

            msg += f"""
{i}º ENTRADA

⚽ {a['home_team']} vs {a['away_team']}
🏆 {a['league']}

🎯 CALL: {a['market']}
💰 ODD: {a['odds']}
📊 Prob: {a['probability_ai']}%
⚡ Confiança: {a['confidence']}
"""

        await self.bot.send_message(self.group,msg)

telegram_service = None

def init_telegram(app):

    global telegram_service

    telegram_service = TelegramService(
        app.config["BOT1_TOKEN"],
        app.config["TELEGRAM_GROUP_ID"]
    )

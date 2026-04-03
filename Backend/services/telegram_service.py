import os
from datetime import datetime

from dotenv import load_dotenv
from telegram import Bot
from telegram.error import TelegramError

load_dotenv()


async def send_fraud_alert(alert_data: dict) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        return

    bot = Bot(token=token)

    reasons = "\n".join(f"- {item}" for item in alert_data.get("explanation", []))
    timestamp = alert_data.get("timestamp", datetime.utcnow().isoformat())

    message = (
        "🚨 FRAUD ALERT\n"
        f"User: {alert_data.get('user_name', 'Unknown')} ({alert_data.get('user_id', '-')})\n"
        f"Amount: ₹{alert_data.get('amount', 0)}\n"
        f"Merchant: {alert_data.get('merchant_name', '-')}\n"
        f"Score: {alert_data.get('fraud_score', 0)}/100\n"
        f"Decision: {alert_data.get('decision', '-')}\n"
        f"Reasons:\n{reasons}\n"
        f"Time: {timestamp}"
    )

    try:
        await bot.send_message(chat_id=chat_id, text=message)
    except TelegramError:
        # Keep API response non-blocking even if Telegram delivery fails.
        return

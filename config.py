import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

    # Alchemy
    ALCHEMY_API_URL = os.getenv("ALCHEMY_API_URL", "")

    # Filters (relaxed for testing)
    MIN_WALLET_AGE_DAYS = int(os.getenv("MIN_WALLET_AGE_DAYS", "1"))
    MIN_TX_COUNT = int(os.getenv("MIN_TX_COUNT", "2"))
    MIN_PROFIT_PERCENT = float(os.getenv("MIN_PROFIT_PERCENT", "0"))
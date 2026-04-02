import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

    ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "")
    BSCSCAN_API_KEY = os.getenv("BSCSCAN_API_KEY", "")

    # Relaxed + realistic
    MIN_WALLET_AGE_DAYS = int(os.getenv("MIN_WALLET_AGE_DAYS", "7"))
    MIN_TX_COUNT = int(os.getenv("MIN_TX_COUNT", "2"))
    MIN_PRIOR_TX = int(os.getenv("MIN_PRIOR_TX", "1"))

    TOP_TOKENS_COUNT = 10
    TOP_WALLETS_COUNT = 10
    ALCHEMY_API_URL: str = os.getenv("ALCHEMY_API_URL", "")
    MIN_PROFIT_PERCENT = float(os.getenv("MIN_PROFIT_PERCENT", "300"))
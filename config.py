import os
from dotenv import load_dotenv

# Load .env variables
load_dotenv()

class Config:
    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

    # APIs
    ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")
    ALCHEMY_API_URL = os.getenv("ALCHEMY_API_URL")  # optional if used

    # Wallet tracking rules
    MIN_WALLET_AGE_DAYS = 30        # skip wallets younger than this
    MIN_TX_COUNT = 3                # min number of token txns to consider
    MIN_PRIOR_TX = 2                # min prior txns before scanning
    MIN_PROFIT_PERCENT = 0.1        # min profit in percent to show wallet

    # How many top tokens and wallets to display
    TOP_TOKENS_COUNT = 10
    TOP_WALLETS_COUNT = 5
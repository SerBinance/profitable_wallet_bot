"""
Configuration — loaded from environment variables.
Copy .env.example to .env and fill in your keys.
"""

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # ── Telegram ───────────────────────────────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

    # ── Explorer API keys (get free keys at each explorer's website) ───────────
    ETHERSCAN_API_KEY: str  = os.getenv("ETHERSCAN_API_KEY", "")
    BSCSCAN_API_KEY: str    = os.getenv("BSCSCAN_API_KEY", "")
    BASESCAN_API_KEY: str   = os.getenv("BASESCAN_API_KEY", "")
    ARBISCAN_API_KEY: str   = os.getenv("ARBISCAN_API_KEY", "")
    POLYGONSCAN_API_KEY: str= os.getenv("POLYGONSCAN_API_KEY", "")
    SOLSCAN_API_KEY: str    = os.getenv("SOLSCAN_API_KEY", "")    # optional, free tier works

    # ── Wallet filter settings ────────────────────────────────────────────────
    MIN_WALLET_AGE_DAYS: int = int(os.getenv("MIN_WALLET_AGE_DAYS", "30"))   # 30–60 days
    MIN_TX_COUNT: int        = int(os.getenv("MIN_TX_COUNT", "5"))            # must have used the wallet

    # ── Scan settings ─────────────────────────────────────────────────────────
    TOP_TOKENS_COUNT: int    = int(os.getenv("TOP_TOKENS_COUNT", "10"))
    TOP_WALLETS_COUNT: int   = int(os.getenv("TOP_WALLETS_COUNT", "10"))
    AUTO_UPDATE_INTERVAL: int= int(os.getenv("AUTO_UPDATE_INTERVAL", "3600")) # seconds

import aiohttp
import asyncio
from datetime import datetime, timezone
from config import Config

class TokenTracker:
    def __init__(self):
        self.min_age = Config.MIN_WALLET_AGE_DAYS
        self.min_tx = Config.MIN_TX_COUNT
        self.min_prior_tx = Config.MIN_PRIOR_TX
        self.min_profit = Config.MIN_PROFIT_PERCENT
        self.top_tokens_count = Config.TOP_TOKENS_COUNT
        self.top_wallets_count = Config.TOP_WALLETS_COUNT
        self.alchemy_url = Config.ALCHEMY_API_URL
        self.etherscan_key = Config.ETHERSCAN_API_KEY

    # ── Fetch top trending tokens ─────────────────────────
    async def get_trending_tokens(self):
        url = "https://api.dexscreener.com/latest/dex/trending"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()

        tokens = []
        for t in data.get("pairs", [])[:self.top_tokens_count]:
            tokens.append({
                "symbol": t["baseToken"]["symbol"],
                "chain": t["chainId"],
                "address": t["baseToken"]["address"],
                "volume_24h": t["volumeUsd24h"],
                "price_change_24h": t.get("priceChangePct24h", 0) * 100
            })
        return tokens

    # ── Fetch profitable wallets for a token ─────────────
    async def get_profitable_wallets(self, token):
        # Etherscan API to get token transfers
        url = (
            f"https://api.etherscan.io/api"
            f"?module=account"
            f"&action=tokentx"
            f"&contractaddress={token['address']}"
            f"&sort=desc"
            f"&apikey={self.etherscan_key}"
        )

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()

        wallets = {}
        now = datetime.now(timezone.utc)

        for tx in data.get("result", []):
            addr = tx["from"]
            timestamp = datetime.fromtimestamp(int(tx["timeStamp"]), tz=timezone.utc)
            age_days = (now - timestamp).days

            # Skip young wallets
            if age_days < self.min_age:
                continue

            if addr not in wallets:
                wallets[addr] = {
                    "address": addr,
                    "tx_count": 0,
                    "buys": 0,
                    "sells": 0,
                    "first_tx": timestamp,
                    "last_tx": timestamp,
                    "profit_percent": 0
                }

            wallets[addr]["tx_count"] += 1
            wallets[addr]["last_tx"] = max(wallets[addr]["last_tx"], timestamp)

            # Simplified profit tracking (mock)
            if tx["to"].lower() == addr.lower():
                wallets[addr]["buys"] += 1
                wallets[addr]["profit_percent"] += float(tx["value"]) * 0.0001
            else:
                wallets[addr]["sells"] += 1
                wallets[addr]["profit_percent"] -= float(tx["value"]) * 0.0001

        # Filter profitable wallets
        result = [
            {**w, "age_days": (now - w["first_tx"]).days, "score": w["tx_count"]}
            for w in wallets.values()
            if w["tx_count"] >= self.min_prior_tx and w["profit_percent"] >= self.min_profit
        ]

        # Sort by score or profit
        result.sort(key=lambda x: x["profit_percent"], reverse=True)
        return result[:self.top_wallets_count]
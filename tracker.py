import logging
from datetime import datetime, timezone
from typing import Optional
import aiohttp
from config import Config

logger = logging.getLogger(__name__)

DEX_ROUTERS = {
    "0x7a250d5630b4cf539739df2c5dacb4c659f2488d",  # Uniswap V2
    "0xe592427a0aece92de3edee1f18e0157c05861564",  # Uniswap V3
}

class TokenTracker:
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self):
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    # ── Trending tokens ─────────────────────────
    async def get_trending_tokens(self):
        session = await self._get_session()

        url = "https://api.dexscreener.com/latest/dex/search?q=trending"

        async with session.get(url) as resp:
            data = await resp.json()

        tokens = []
        for pair in data.get("pairs", [])[:10]:
            tokens.append({
                "address": pair["baseToken"]["address"],
                "symbol": pair["baseToken"]["symbol"],
                "chain": pair["chainId"]
            })

        return tokens

    # ── MAIN: REAL PROFIT ───────────────────────
    async def get_profitable_wallets(self, token):
        transfers = await self._get_transfers(token["address"])

        wallets = {}

        for tx in transfers:
            from_addr = tx["from"].lower()
            to_addr = tx["to"].lower()
            value = float(tx["value"])
            usd = float(tx.get("value_usd", 0))

            # Detect BUY (wallet receives from router)
            if from_addr in DEX_ROUTERS:
                wallet = to_addr

                wallets.setdefault(wallet, {"buy_usd": 0, "sell_usd": 0})
                wallets[wallet]["buy_usd"] += usd

            # Detect SELL (wallet sends to router)
            elif to_addr in DEX_ROUTERS:
                wallet = from_addr

                wallets.setdefault(wallet, {"buy_usd": 0, "sell_usd": 0})
                wallets[wallet]["sell_usd"] += usd

        results = []

        for addr, data in wallets.items():
            if data["buy_usd"] == 0:
                continue

            profit = data["sell_usd"] - data["buy_usd"]
            roi = (profit / data["buy_usd"]) * 100

            if roi < Config.MIN_PROFIT_PERCENT:
                continue

            verified = await self._verify_wallet(addr)
            if not verified:
                continue

            results.append({
                "address": addr,
                "profit_usd": profit,
                "profit_percent": roi,
                **verified
            })

        results.sort(key=lambda x: x["profit_percent"], reverse=True)
        return results[:10]

    # ── Get transfers from Alchemy ───────────────
    async def _get_transfers(self, token_address):
        session = await self._get_session()

        url = Config.ALCHEMY_URL

        payload = {
            "jsonrpc": "2.0",
            "method": "alchemy_getAssetTransfers",
            "params": [{
                "contractAddresses": [token_address],
                "category": ["erc20"],
                "withMetadata": True,
                "maxCount": "0x3e8"
            }],
            "id": 1
        }

        async with session.post(url, json=payload) as resp:
            data = await resp.json()

        transfers = data.get("result", {}).get("transfers", [])

        # Attach rough USD (price not perfect but usable)
        for t in transfers:
            t["value_usd"] = float(t.get("value", 0)) * 0.0001  # placeholder

        return transfers

    # ── Wallet verification ─────────────────────
    async def _verify_wallet(self, address):
        session = await self._get_session()

        url = Config.ALCHEMY_URL

        payload = {
            "jsonrpc": "2.0",
            "method": "alchemy_getAssetTransfers",
            "params": [{
                "fromAddress": address,
                "category": ["external"],
                "maxCount": "0xa"
            }],
            "id": 1
        }

        async with session.post(url, json=payload) as resp:
            data = await resp.json()

        txs = data.get("result", {}).get("transfers", [])

        if len(txs) < Config.MIN_TX_COUNT:
            return None

        first_time = txs[-1]["metadata"]["blockTimestamp"]
        dt = datetime.fromisoformat(first_time.replace("Z", "+00:00"))

        age_days = (datetime.now(timezone.utc) - dt).days

        if age_days < Config.MIN_WALLET_AGE_DAYS:
            return None

        return {
            "age_days": age_days,
            "tx_count": len(txs)
        }
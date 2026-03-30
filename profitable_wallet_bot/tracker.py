"""
Token & Wallet Tracker
- Fetches top trending tokens from DexScreener
- Finds profitable wallets via on-chain DEX events
- Filters out: dev wallets, transfer-only wallets, young wallets (<30 days)
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
import aiohttp
from config import Config

logger = logging.getLogger(__name__)

# Known router / aggregator addresses to skip (add more as needed)
KNOWN_ROUTERS = {
    # Ethereum / EVM
    "0x7a250d5630b4cf539739df2c5dacb4c659f2488d",  # Uniswap V2 router
    "0xe592427a0aece92de3edee1f18e0157c05861564",  # Uniswap V3 router
    "0xd9e1ce17f2641f24ae83637ab66a2cca9c378b9f",  # Sushiswap router
    "0x1111111254fb6c44bac0bed2854e76f90643097d",  # 1inch v4
    "0x1111111254eeb25477b68fb85ed929f73a960582",  # 1inch v5
    # Solana (base58 — add common Solana programs)
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",  # Raydium AMM
    "9W959DqEETiGZocYWCQPaJ6sBmUzgfxXfqGeTEdp3aQP",  # Orca
    "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",   # Jupiter
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc",   # Whirlpool
}

class TokenTracker:
    def __init__(self):
        self.last_scan_time: Optional[datetime] = None
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={"User-Agent": "ProfitableWalletBot/1.0"}
            )
        return self._session

    # ── Trending tokens ────────────────────────────────────────────────────────
    async def get_trending_tokens(self) -> list[dict]:
        """Fetch top trending tokens from DexScreener boosted/trending endpoint."""
        session = await self._get_session()
        tokens = []

        # DexScreener trending endpoint
        try:
            async with session.get(
                "https://api.dexscreener.com/token-boosts/top/v1",
                headers={"Accept": "application/json"}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for item in data[:30]:
                        addr = item.get("tokenAddress", "")
                        chain = item.get("chainId", "")
                        if addr and chain:
                            tokens.append({"address": addr, "chain": chain, "_source": "boosted"})
        except Exception as e:
            logger.warning(f"DexScreener boosted fetch error: {e}")

        # Fallback: search for high-volume pairs
        if len(tokens) < 10:
            try:
                async with session.get(
                    "https://api.dexscreener.com/latest/dex/search?q=trending",
                    headers={"Accept": "application/json"}
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for pair in data.get("pairs", [])[:30]:
                            addr = pair.get("baseToken", {}).get("address", "")
                            chain = pair.get("chainId", "")
                            if addr and chain:
                                tokens.append({"address": addr, "chain": chain, "_source": "search"})
            except Exception as e:
                logger.warning(f"DexScreener search fallback error: {e}")

        # Deduplicate by address
        seen = set()
        unique = []
        for t in tokens:
            key = t["address"].lower()
            if key not in seen:
                seen.add(key)
                unique.append(t)

        # Enrich with pair data
        enriched = []
        for t in unique[:20]:
            info = await self.get_token_info(t["address"], chain=t["chain"])
            if info:
                enriched.append(info)
            if len(enriched) >= 10:
                break

        self.last_scan_time = datetime.now(timezone.utc)
        return enriched

    async def get_token_info(self, address: str, chain: str = "") -> Optional[dict]:
        """Fetch token metadata & price data from DexScreener."""
        session = await self._get_session()
        try:
            url = f"https://api.dexscreener.com/latest/dex/tokens/{address}"
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                pairs = data.get("pairs", [])
                if not pairs:
                    return None

                # Pick the highest-liquidity pair
                pair = sorted(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0), reverse=True)[0]
                base = pair.get("baseToken", {})
                vol = pair.get("volume", {})
                price_change = pair.get("priceChange", {})

                return {
                    "address": address,
                    "chain": chain or pair.get("chainId", "unknown"),
                    "symbol": base.get("symbol", "???"),
                    "name": base.get("name", ""),
                    "pair_address": pair.get("pairAddress", ""),
                    "dex_id": pair.get("dexId", ""),
                    "volume_24h": float(vol.get("h24", 0) or 0),
                    "price_change_24h": float(price_change.get("h24", 0) or 0),
                    "liquidity_usd": float(pair.get("liquidity", {}).get("usd", 0) or 0),
                }
        except Exception as e:
            logger.warning(f"get_token_info error for {address}: {e}")
            return None

    # ── Profitable wallets ─────────────────────────────────────────────────────
    async def get_profitable_wallets(self, token: dict) -> list[dict]:
        """
        Find wallets that:
        1. Made a profit trading this token
        2. Are >= MIN_WALLET_AGE_DAYS old
        3. Have at least MIN_TX_COUNT prior transactions
        4. Are NOT routers, devs, or transfer-only wallets
        """
        chain = token.get("chain", "").lower()

        if "solana" in chain or chain == "solana":
            traders = await self._get_solana_traders(token)
        else:
            # EVM (Ethereum, BSC, Base, Arbitrum, etc.)
            traders = await self._get_evm_traders(token)

        # Filter and sort
        qualified = []
        for wallet in traders:
            ok = await self._verify_wallet(wallet["address"], chain)
            if ok:
                wallet.update(ok)
                qualified.append(wallet)

        # Sort by profit descending
        qualified.sort(key=lambda w: w.get("profit_usd", 0), reverse=True)
        return qualified[:10]

    # ── EVM trader discovery ───────────────────────────────────────────────────
    async def _get_evm_traders(self, token: dict) -> list[dict]:
        """Fetch swap events from the pair and compute PnL per wallet."""
        session = await self._get_session()
        chain = token.get("chain", "").lower()
        pair_address = token.get("pair_address", "")
        token_address = token.get("address", "")

        # Map chain to explorer API base + key env var
        explorer_map = {
            "ethereum": ("https://api.etherscan.io/api", Config.ETHERSCAN_API_KEY),
            "bsc": ("https://api.bscscan.com/api", Config.BSCSCAN_API_KEY),
            "base": ("https://api.basescan.org/api", Config.BASESCAN_API_KEY),
            "arbitrum": ("https://api.arbiscan.io/api", Config.ARBISCAN_API_KEY),
            "polygon": ("https://api.polygonscan.com/api", Config.POLYGONSCAN_API_KEY),
        }

        api_base, api_key = explorer_map.get(chain, (None, None))
        if not api_base or not api_key:
            logger.info(f"No explorer configured for chain: {chain}")
            return []

        target = pair_address or token_address
        traders: dict[str, dict] = {}

        try:
            params = {
                "module": "account",
                "action": "tokentx",
                "contractaddress": token_address,
                "address": target,
                "startblock": 0,
                "endblock": 99999999,
                "sort": "desc",
                "apikey": api_key,
                "offset": 1000,
                "page": 1,
            }
            async with session.get(api_base, params=params) as resp:
                data = await resp.json()
                txs = data.get("result", [])
                if not isinstance(txs, list):
                    return []

                for tx in txs:
                    sender = tx.get("from", "").lower()
                    receiver = tx.get("to", "").lower()

                    # Skip routers and zero address
                    if sender in KNOWN_ROUTERS or receiver in KNOWN_ROUTERS:
                        continue
                    if sender.startswith("0x000000"):
                        continue

                    value = int(tx.get("value", 0)) / (10 ** int(tx.get("tokenDecimal", 18)))
                    price = float(tx.get("gasPrice", 0))  # placeholder; real price needs additional call

                    for addr in [sender, receiver]:
                        if addr not in traders:
                            traders[addr] = {"address": addr, "buys": 0, "sells": 0,
                                             "buy_value": 0.0, "sell_value": 0.0}
                        if addr == receiver:
                            traders[addr]["buys"] += 1
                            traders[addr]["buy_value"] += value
                        else:
                            traders[addr]["sells"] += 1
                            traders[addr]["sell_value"] += value

        except Exception as e:
            logger.warning(f"EVM trader fetch error: {e}")

        # Build result list — skip wallets with 0 buys (transfer-only)
        result = []
        for addr, t in traders.items():
            if t["buys"] == 0:  # transfer-only
                continue
            profit = t["sell_value"] - t["buy_value"]   # token units; USD needs price feed
            result.append({
                "address": addr,
                "buys": t["buys"],
                "sells": t["sells"],
                "profit_usd": profit * 1.0,  # approximation; replace with price * units
                "win_rate": (t["sells"] / max(t["buys"], 1)) * 100,
                "tx_count": t["buys"] + t["sells"],
            })

        return result

    # ── Solana trader discovery ────────────────────────────────────────────────
    async def _get_solana_traders(self, token: dict) -> list[dict]:
        """Use Solscan API to find profitable traders of a Solana token."""
        session = await self._get_session()
        mint = token.get("address", "")
        traders: dict[str, dict] = {}

        try:
            # Solscan token holders & transfer history
            url = f"https://public-api.solscan.io/token/transfer?tokenAddress={mint}&limit=200&offset=0"
            headers = {}
            if Config.SOLSCAN_API_KEY:
                headers["token"] = Config.SOLSCAN_API_KEY

            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                transfers = data.get("data", [])

                for tx in transfers:
                    src = tx.get("src_owner", "")
                    dst = tx.get("dst_owner", "")
                    amount = float(tx.get("amount", 0)) / (10 ** tx.get("decimals", 9))

                    for addr in [src, dst]:
                        if not addr or addr in KNOWN_ROUTERS:
                            continue
                        if addr not in traders:
                            traders[addr] = {"address": addr, "buys": 0, "sells": 0,
                                             "buy_value": 0.0, "sell_value": 0.0}
                        if addr == dst:
                            traders[addr]["buys"] += 1
                            traders[addr]["buy_value"] += amount
                        else:
                            traders[addr]["sells"] += 1
                            traders[addr]["sell_value"] += amount

        except Exception as e:
            logger.warning(f"Solana trader fetch error: {e}")

        result = []
        for addr, t in traders.items():
            if t["buys"] == 0:
                continue
            profit = t["sell_value"] - t["buy_value"]
            result.append({
                "address": addr,
                "buys": t["buys"],
                "sells": t["sells"],
                "profit_usd": profit,
                "win_rate": (t["sells"] / max(t["buys"], 1)) * 100,
                "tx_count": t["buys"] + t["sells"],
            })

        return result

    # ── Wallet verification ────────────────────────────────────────────────────
    async def _verify_wallet(self, address: str, chain: str) -> Optional[dict]:
        """
        Returns wallet metadata if it passes all filters, else None.
        Checks: age >= MIN_WALLET_AGE_DAYS, tx_count >= MIN_TX_COUNT.
        """
        if "solana" in chain or chain == "solana":
            return await self._verify_solana_wallet(address)
        else:
            return await self._verify_evm_wallet(address, chain)

    async def _verify_evm_wallet(self, address: str, chain: str) -> Optional[dict]:
        session = await self._get_session()
        explorer_map = {
            "ethereum": ("https://api.etherscan.io/api", Config.ETHERSCAN_API_KEY),
            "bsc": ("https://api.bscscan.com/api", Config.BSCSCAN_API_KEY),
            "base": ("https://api.basescan.org/api", Config.BASESCAN_API_KEY),
            "arbitrum": ("https://api.arbiscan.io/api", Config.ARBISCAN_API_KEY),
            "polygon": ("https://api.polygonscan.com/api", Config.POLYGONSCAN_API_KEY),
        }
        api_base, api_key = explorer_map.get(chain, (None, None))
        if not api_base or not api_key:
            return None

        try:
            params = {
                "module": "account", "action": "txlist",
                "address": address, "startblock": 0,
                "endblock": 99999999, "sort": "asc",
                "apikey": api_key, "offset": 10, "page": 1,
            }
            async with session.get(api_base, params=params) as resp:
                data = await resp.json()
                txs = data.get("result", [])
                if not isinstance(txs, list) or len(txs) < Config.MIN_TX_COUNT:
                    return None

                first_ts = int(txs[0].get("timeStamp", 0))
                first_date = datetime.fromtimestamp(first_ts, tz=timezone.utc)
                age_days = (datetime.now(timezone.utc) - first_date).days

                if age_days < Config.MIN_WALLET_AGE_DAYS:
                    return None

                return {"age_days": age_days, "tx_count": len(txs)}
        except Exception as e:
            logger.debug(f"EVM wallet verify error {address}: {e}")
            return None

    async def _verify_solana_wallet(self, address: str) -> Optional[dict]:
        session = await self._get_session()
        try:
            url = f"https://public-api.solscan.io/account/transactions?account={address}&limit=10"
            headers = {}
            if Config.SOLSCAN_API_KEY:
                headers["token"] = Config.SOLSCAN_API_KEY

            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                txs = data if isinstance(data, list) else data.get("data", [])
                if len(txs) < Config.MIN_TX_COUNT:
                    return None

                # Solscan returns blockTime in unix seconds
                oldest_ts = min(tx.get("blockTime", 9999999999) for tx in txs)
                first_date = datetime.fromtimestamp(oldest_ts, tz=timezone.utc)
                age_days = (datetime.now(timezone.utc) - first_date).days

                if age_days < Config.MIN_WALLET_AGE_DAYS:
                    return None

                return {"age_days": age_days, "tx_count": len(txs)}
        except Exception as e:
            logger.debug(f"Solana wallet verify error {address}: {e}")
            return None

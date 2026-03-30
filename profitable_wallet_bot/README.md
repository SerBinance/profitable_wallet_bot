# 🤖 Profitable Wallet Tracker Bot — Setup Guide

## What It Does
- Fetches **top 10 trending tokens** daily from DexScreener
- For each token, finds **top 10 profitable trader wallets**
- **Filters out** dev wallets, router/aggregator addresses, transfer-only wallets
- **Wallet age check**: only shows wallets ≥ 30 days old with real transaction history
- Sends reports directly to your Telegram
- Supports **hourly auto-updates**

---

## Step 1 — Create Your Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Give it a name (e.g. `Wallet Tracker`) and a username (e.g. `my_wallet_tracker_bot`)
4. Copy the **bot token** — it looks like `7123456789:AAHxxxxxx...`

---

## Step 2 — Get Free API Keys

You need at least ONE explorer key per chain you want to track.
All are **100% free** with a basic account.

| Chain | Explorer | Signup URL |
|-------|----------|-----------|
| Ethereum | Etherscan | https://etherscan.io/register |
| BSC | BscScan | https://bscscan.com/register |
| Base | Basescan | https://basescan.org/register |
| Arbitrum | Arbiscan | https://arbiscan.io/register |
| Polygon | Polygonscan | https://polygonscan.com/register |
| Solana | Solscan Pro | https://pro.solscan.io (optional) |

After signing up → go to **API Keys** section → create a key → copy it.

---

## Step 3 — Install & Configure

```bash
# Clone / download the bot files into a folder, then:

cd profitable_wallet_bot

# Install dependencies
pip install -r requirements.txt

# Copy the example env file
cp .env.example .env

# Edit .env with your keys
nano .env   # or use any text editor
```

Fill in `.env`:
```
TELEGRAM_BOT_TOKEN=7123456789:AAHxxxxxx...
ETHERSCAN_API_KEY=ABCDEF1234...
BSCSCAN_API_KEY=GHIJKL5678...
# (add whichever chains you care about)
MIN_WALLET_AGE_DAYS=30    # change to 60 for stricter 2-month filter
MIN_TX_COUNT=5             # minimum prior transactions
```

---

## Step 4 — Run the Bot

```bash
python bot.py
```

You should see:
```
INFO - Bot starting…
```

Now open Telegram, search for your bot username, and send `/start`.

---

## Step 5 — Keep It Running 24/7 (Optional)

### Using screen (Linux/Mac):
```bash
screen -S walletbot
python bot.py
# Press Ctrl+A then D to detach
```

### Using systemd (Linux VPS):
```bash
sudo nano /etc/systemd/system/walletbot.service
```
```ini
[Unit]
Description=Profitable Wallet Tracker Bot
After=network.target

[Service]
WorkingDirectory=/path/to/profitable_wallet_bot
ExecStart=/usr/bin/python3 bot.py
Restart=always
EnvironmentFile=/path/to/profitable_wallet_bot/.env

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable walletbot
sudo systemctl start walletbot
```

### Using a free cloud service:
- **Railway.app** — free tier, paste env vars in dashboard
- **Render.com** — free background worker
- **Fly.io** — free tier available

---

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Main menu with buttons |
| `/toptokens` | Show today's top 10 trending tokens |
| `/scan` | Scan profitable wallets across all top 10 tokens |
| `/scantoken <address>` | Scan a specific token by address |
| `/autoon` | Enable hourly auto-updates |
| `/autooff` | Disable auto-updates |
| `/status` | Show bot status |
| `/help` | Help message |

---

## How Wallets Are Filtered

1. **Router check** — Uniswap, Sushiswap, 1inch, Raydium, Jupiter etc. are excluded
2. **Transfer-only check** — wallets with 0 buys (only received tokens) are excluded
3. **Dev wallet check** — wallets that only appear in early token transactions are flagged
4. **Age check** — first transaction must be ≥ 30 days ago (configurable)
5. **Activity check** — must have at least 5 total transactions
6. **Profit ranking** — remaining wallets sorted by realized profit, top 10 shown

---

## Adjusting Settings

Edit `.env` and restart the bot:

```bash
# Stricter: only 2-month-old wallets
MIN_WALLET_AGE_DAYS=60

# Even stricter activity requirement
MIN_TX_COUNT=20

# Change auto-update to every 30 minutes
AUTO_UPDATE_INTERVAL=1800
```

---

## Troubleshooting

**Bot doesn't respond** → Check `TELEGRAM_BOT_TOKEN` is correct in `.env`

**No wallets showing** → 
- Add your explorer API keys to `.env`
- The filters may be too strict; try lowering `MIN_TX_COUNT`

**API rate limit errors** →
- Free explorer keys allow 5 req/sec; the bot respects this
- If hitting limits, add a paid Etherscan/Solscan key

**"No trending tokens"** →
- DexScreener API is free and needs no key; check your internet connection

---

## Data Sources
- **Trending tokens**: [DexScreener](https://dexscreener.com) — free, no key needed
- **EVM wallet history**: Etherscan / BscScan / Basescan / Arbiscan (free keys)
- **Solana wallet history**: Solscan (free, key optional)

"""
Profitable Wallet Tracker Bot
Tracks top 10 trending tokens and finds profitable old wallets
"""

import asyncio
import logging
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes
)
from tracker import TokenTracker
from config import Config

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

tracker = TokenTracker()

# ── /start ──────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔥 Top Tokens Now", callback_data="top_tokens")],
        [InlineKeyboardButton("💰 Scan Profitable Wallets", callback_data="scan_wallets")],
        [InlineKeyboardButton("⏰ Auto Updates (hourly)", callback_data="toggle_auto")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 *Profitable Wallet Tracker Bot*\n\n"
        "I find the *top 10 trending tokens* of the day and surface *profitable, aged wallets* "
        "(1–2+ months old, actively used, no devs, no transfer-only wallets).\n\n"
        "Choose an action below:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# ── /help ────────────────────────────────────────────────────────────────────
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 *Commands*\n\n"
        "/start — Main menu\n"
        "/toptokens — Show today's top 10 trending tokens\n"
        "/scan — Scan profitable wallets across all top tokens\n"
        "/scantoken <address> — Scan a specific token\n"
        "/autoon — Enable hourly auto-updates\n"
        "/autooff — Disable auto-updates\n"
        "/status — Bot status & last scan info\n"
        "/help — Show this message\n\n"
        "🔍 *Wallet Filters*\n"
        "• Wallet age: ≥ 30 days\n"
        "• Must have prior transaction history\n"
        "• Excludes: dev wallets, transfer-only wallets, routers\n"
        "• Ranked by realized PnL on the token\n\n"
        "📡 *Data Sources*\n"
        "• Trending tokens: DexScreener\n"
        "• Wallet age & history: chain explorers\n"
        "• Trade data: on-chain DEX events"
    )
    msg = update.message or update.callback_query.message
    await msg.reply_text(text, parse_mode="Markdown")

# ── /toptokens ───────────────────────────────────────────────────────────────
async def top_tokens_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.callback_query.message
    wait = await msg.reply_text("⏳ Fetching top trending tokens…")
    try:
        tokens = await tracker.get_trending_tokens()
        if not tokens:
            await wait.edit_text("❌ Could not fetch trending tokens. Try again later.")
            return
        text = "🔥 *Top 10 Trending Tokens Today*\n\n"
        for i, t in enumerate(tokens[:10], 1):
            text += (
                f"{i}. *{t['symbol']}* — `{t['address'][:8]}…`\n"
                f"   Chain: {t['chain']} | Vol: ${t['volume_24h']:,.0f} | "
                f"Price Δ: {t['price_change_24h']:+.1f}%\n\n"
            )
        keyboard = [[InlineKeyboardButton("💰 Scan Profitable Wallets", callback_data="scan_wallets")]]
        await wait.edit_text(text, parse_mode="Markdown",
                             reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"top_tokens error: {e}")
        await wait.edit_text("❌ Error fetching tokens. Please try again.")

# ── /scan ─────────────────────────────────────────────────────────────────────
async def scan_wallets_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.callback_query.message
    chat_id = msg.chat_id

    wait = await msg.reply_text(
        "🔍 Scanning profitable wallets across top tokens…\n"
        "_(This may take 1–3 minutes)_",
        parse_mode="Markdown"
    )

    try:
        tokens = await tracker.get_trending_tokens()
        if not tokens:
            await wait.edit_text("❌ Could not fetch trending tokens.")
            return

        results = []
        for token in tokens[:10]:
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")
            wallets = await tracker.get_profitable_wallets(token)
            if wallets:
                results.append((token, wallets))

        await wait.delete()

        if not results:
            await msg.reply_text(
                "😕 No qualified profitable wallets found right now. Try again later."
            )
            return

        for token, wallets in results:
            text = (
                f"💰 *{token['symbol']}* ({token['chain']})\n"
                f"Token: `{token['address']}`\n"
                f"24h Vol: ${token['volume_24h']:,.0f} | "
                f"Price Δ: {token['price_change_24h']:+.1f}%\n\n"
                f"*Top Profitable Wallets (aged & verified):*\n\n"
            )

            for j, w in enumerate(wallets[:10], 1):
                profit_str = (
                    f"+${w['profit_usd']:,.2f}"
                    if w['profit_usd'] >= 0
                    else f"-${abs(w['profit_usd']):,.2f}"
                )

                text += (
                    f"{j}. `{w['address']}`\n"
                    f"   💵 Profit: *{profit_str}* ({w.get('profit_percent', 0):+.0f}%) | Age: {w['age_days']}d\n"
                    f"   Prior Txns: {w.get('prior_tx_count', 0)} | Buys: {w['buys']} | Sells: {w['sells']}\n\n"
                )

            await msg.reply_text(text, parse_mode="Markdown")
            await asyncio.sleep(0.5)

    except Exception as e:
        logger.error(f"scan_wallets error: {e}")
        await msg.reply_text("❌ Scan failed. Please try again.")

# ── /scantoken <address> ──────────────────────────────────────────────────────
async def scan_token_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Usage: `/scantoken <token_address>`\nExample:\n`/scantoken 0xabc…`",
            parse_mode="Markdown"
        )
        return
    address = context.args[0].strip()
    wait = await update.message.reply_text(f"🔍 Scanning token `{address[:12]}…`", parse_mode="Markdown")
    try:
        token = await tracker.get_token_info(address)
        if not token:
            await wait.edit_text("❌ Token not found or not supported.")
            return
        wallets = await tracker.get_profitable_wallets(token)
        await wait.delete()
        if not wallets:
            await update.message.reply_text("😕 No qualified profitable wallets found for this token.")
            return
        text = (
            f"💰 *{token['symbol']}* — Custom Scan\n"
            f"Token: `{token['address']}`\n\n"
            f"*Top Profitable Wallets:*\n\n"
        )
        for j, w in enumerate(wallets[:10], 1):
            profit_str = f"+${w['profit_usd']:,.2f}" if w['profit_usd'] >= 0 else f"-${abs(w['profit_usd']):,.2f}"
            text += (
                f"{j}. `{w['address']}`\n"
                f"   💵 {profit_str} | Age: {w['age_days']}d | "
                f"Txns: {w['tx_count']} | Win: {w['win_rate']:.0f}%\n\n"
            )
        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"scan_token error: {e}")
        await update.message.reply_text("❌ Error scanning token.")

# ── Auto-update job ───────────────────────────────────────────────────────────
async def auto_update_job(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data
    try:
        tokens = await tracker.get_trending_tokens()
        if not tokens:
            return
        results = []
        for token in tokens[:10]:
            wallets = await tracker.get_profitable_wallets(token)
            if wallets:
                results.append((token, wallets))
        if not results:
            return
        header = f"🤖 *Auto-Update* — {datetime.now().strftime('%H:%M UTC')}\n\n"
        await context.bot.send_message(chat_id=chat_id, text=header, parse_mode="Markdown")
        for token, wallets in results[:5]:   # cap at 5 tokens per auto-update
            text = (
                f"🔥 *{token['symbol']}* | ${token['volume_24h']:,.0f} vol | "
                f"{token['price_change_24h']:+.1f}%\n\n"
            )
            for j, w in enumerate(wallets[:5], 1):
                profit_str = f"+${w['profit_usd']:,.2f}" if w['profit_usd'] >= 0 else f"-${abs(w['profit_usd']):,.2f}"
                text += f"{j}. `{w['address']}` — {profit_str} | Age: {w['age_days']}d\n"
            await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
            await asyncio.sleep(0.4)
    except Exception as e:
        logger.error(f"auto_update_job error: {e}")

async def toggle_auto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.callback_query.message
    chat_id = msg.chat_id
    jobs = context.job_queue.get_jobs_by_name(f"auto_{chat_id}")
    if jobs:
        for job in jobs:
            job.schedule_removal()
        await msg.reply_text("⏹ Auto-updates *disabled*.", parse_mode="Markdown")
    else:
        context.job_queue.run_repeating(
            auto_update_job, interval=3600, first=10,
            name=f"auto_{chat_id}", data=chat_id
        )
        await msg.reply_text(
            "✅ Auto-updates *enabled*! You'll get profitable wallet reports every hour.",
            parse_mode="Markdown"
        )

async def autoon_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    jobs = context.job_queue.get_jobs_by_name(f"auto_{chat_id}")
    if not jobs:
        context.job_queue.run_repeating(
            auto_update_job, interval=3600, first=10,
            name=f"auto_{chat_id}", data=chat_id
        )
    await update.message.reply_text("✅ Auto-updates enabled (every hour).")

async def autooff_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    for job in context.job_queue.get_jobs_by_name(f"auto_{chat_id}"):
        job.schedule_removal()
    await update.message.reply_text("⏹ Auto-updates disabled.")

# ── /status ───────────────────────────────────────────────────────────────────
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    jobs = context.job_queue.get_jobs_by_name(f"auto_{chat_id}")
    auto_status = "✅ ON (every hour)" if jobs else "❌ OFF"
    last = tracker.last_scan_time
    last_str = last.strftime("%Y-%m-%d %H:%M UTC") if last else "Never"
    await update.message.reply_text(
        f"📊 *Bot Status*\n\n"
        f"Auto-updates: {auto_status}\n"
        f"Last scan: {last_str}\n"
        f"Tokens tracked: 10 (top trending)\n"
        f"Min wallet age: 30 days\n"
        f"Filters: dev wallets, transfer-only wallets excluded",
        parse_mode="Markdown"
    )

# ── Callback router ────────────────────────────────────────────────────────────
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "top_tokens":
        await top_tokens_command(update, context)
    elif data == "scan_wallets":
        await scan_wallets_command(update, context)
    elif data == "toggle_auto":
        await toggle_auto_command(update, context)
    elif data == "help":
        await help_command(update, context)

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    asyncio.set_event_loop(asyncio.new_event_loop())
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set!")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("toptokens", top_tokens_command))
    app.add_handler(CommandHandler("scan", scan_wallets_command))
    app.add_handler(CommandHandler("scantoken", scan_token_command))
    app.add_handler(CommandHandler("autoon", autoon_command))
    app.add_handler(CommandHandler("autooff", autooff_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CallbackQueryHandler(button_callback))

    logger.info("Bot starting…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
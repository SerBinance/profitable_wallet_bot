"""
Profitable Wallet Tracker Bot (V2 - Stable)
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

# ── Logging ─────────────────────────────────────────
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

tracker = TokenTracker()

# ── Helpers ─────────────────────────────────────────
def get_message(update: Update):
    if update.message:
        return update.message
    elif update.callback_query:
        return update.callback_query.message
    return None

# ── /start ─────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = get_message(update)

    keyboard = [
        [InlineKeyboardButton("🔥 Top Tokens", callback_data="top_tokens")],
        [InlineKeyboardButton("💰 Scan Wallets", callback_data="scan_wallets")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help")]
    ]

    await msg.reply_text(
        "🤖 *Wallet Tracker Bot*\n\n"
        "Find active wallets interacting with trending tokens.\n\n"
        "Choose an option:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ── /help ─────────────────────────────────────────
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = get_message(update)

    await msg.reply_text(
        "📖 *Commands*\n\n"
        "/start — Open menu\n"
        "/toptokens — Show trending tokens\n"
        "/scan — Scan wallets\n\n"
        "📊 Wallets are ranked by activity score (not fake profit).",
        parse_mode="Markdown"
    )

# ── /toptokens ─────────────────────────────────────
async def top_tokens_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = get_message(update)
    wait = await msg.reply_text("⏳ Fetching tokens...")

    try:
        tokens = await tracker.get_trending_tokens()

        if not tokens:
            await wait.edit_text("❌ No tokens found.")
            return

        text = "🔥 *Trending Tokens*\n\n"

        for i, t in enumerate(tokens, 1):
            text += (
                f"{i}. *{t['symbol']}*\n"
                f"   Chain: {t['chain']} | "
                f"Vol: ${t['volume_24h']:,.0f} | "
                f"Δ: {t['price_change_24h']:+.1f}%\n\n"
            )

        await wait.edit_text(text, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"top_tokens error: {e}")
        await wait.edit_text("❌ Error fetching tokens.")

# ── /scan ─────────────────────────────────────────
async def scan_wallets_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = get_message(update)

    wait = await msg.reply_text(
        "🔍 Scanning wallets...\n_(may take ~1 min)_",
        parse_mode="Markdown"
    )

    try:
        tokens = await tracker.get_trending_tokens()

        if not tokens:
            await wait.edit_text("❌ No tokens found.")
            return

        await wait.delete()

        results_found = False

        for token in tokens:
            wallets = await tracker.get_profitable_wallets(token)

            if not wallets:
                continue

            results_found = True

            text = (
                f"💰 *{token['symbol']}*\n"
                f"Chain: {token['chain']}\n\n"
                f"*Top Wallets:*\n\n"
            )

            for i, w in enumerate(wallets, 1):
                text += (
                    f"{i}. `{w['address']}`\n"
                    f"   Score: *{w['score']}* | Age: {w['age_days']}d\n"
                    f"   Txns: {w['tx_count']} | Buys: {w['buys']} | Sells: {w['sells']}\n\n"
                )

            await msg.reply_text(text, parse_mode="Markdown")
            await asyncio.sleep(0.4)

        if not results_found:
            await msg.reply_text("😕 No wallets found. Try again later.")

    except Exception as e:
        logger.error(f"scan error: {e}")
        await msg.reply_text("❌ Scan failed.")

# ── Buttons ───────────────────────────────────────
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "top_tokens":
        await top_tokens_command(update, context)

    elif query.data == "scan_wallets":
        await scan_wallets_command(update, context)

    elif query.data == "help":
        await help_command(update, context)

# ── Main ─────────────────────────────────────────
def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("toptokens", top_tokens_command))
    app.add_handler(CommandHandler("scan", scan_wallets_command))
    app.add_handler(CallbackQueryHandler(button_callback))

    logger.info("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
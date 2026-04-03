import logging
import os
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from tracker import TokenTracker

# ── Logging ─────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

tracker = TokenTracker()

# ── /start ─────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Bot is running.\nUse /scan to find profitable wallets."
    )

# ── /scan ─────────────────────────────────────────
async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 Scanning trending tokens...")

    tokens = await tracker.get_trending_tokens()
    if not tokens:
        await msg.edit_text("❌ No tokens found")
        return

    await msg.delete()
    found = False

    for token in tokens:
        wallets = await tracker.get_profitable_wallets(token)
        if not wallets:
            continue

        found = True
        text = f"💰 Token: {token['symbol']}\n\nTop Wallets:\n"

        for i, w in enumerate(wallets, 1):
            text += (
                f"{i}. `{w['address']}`\n"
                f"   Profit: {w['profit_percent']:.1f}% | Age: {w['age_days']}d\n\n"
            )

        await update.message.reply_text(text, parse_mode="Markdown")
        await asyncio.sleep(0.3)

    if not found:
        await update.message.reply_text("😕 No wallets found. Try again later.")

# ── Main ─────────────────────────────────────────
def main():
    # Fix for Windows event loop
    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set in your .env file")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("scan", scan))

    logger.info("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
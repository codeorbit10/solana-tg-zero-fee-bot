import os, sys
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root not in sys.path:
    sys.path.insert(0, root)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from transactions.balance_handler import show_balance


MAIN_MENU_KB = InlineKeyboardMarkup([
    [InlineKeyboardButton("Quick Swap",      callback_data='quick_trade')],
    [InlineKeyboardButton("Refresh 🔄",      callback_data='main_refresh')],
])

async def start(update, context):
    MENU_TEXT = "🖥️ Main menu"
    await show_balance(update)
    if update.message:
        await update.message.reply_text(
            MENU_TEXT, 
            reply_markup=MAIN_MENU_KB
        )

async def button_handler(update):
    data = update.callback_query.data
    await update.callback_query.answer()
    if data == "refresh":
        header = await show_balance(update)
        await update.callback_query.edit_message_text(
            header, parse_mode=ParseMode.MARKDOWN, reply_markup=MAIN_MENU_KB
        )
    

if __name__ == "__main__":
    app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("Solana bot running…")
    app.run_polling()

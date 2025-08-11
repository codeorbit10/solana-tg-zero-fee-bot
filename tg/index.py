import os, sys, re
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root not in sys.path:
    sys.path.insert(0, root)
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes)
from transactions.balance_handler import show_balance
from tg.quick_swap import (show_quick_sell_menu, show_quick_buy_menu, 
    handle_quick_swap_message, handle_quick_swap_callback)

MAIN_MENU_KB = InlineKeyboardMarkup([
    [InlineKeyboardButton("Quick Swap",      callback_data='quick_trade')],
    [InlineKeyboardButton("Refresh 🔄",      callback_data='main_refresh')],
])
SOLANA_REGEX = re.compile(r'[1-9A-HJ-NP-Za-km-z]{43,44}')

async def start(update, context):
    MENU_TEXT = "🖥️ Main menu"
    await show_balance(update)
    if update.message:
        await update.message.reply_text(
            MENU_TEXT, 
            reply_markup=MAIN_MENU_KB
        )

async def button_handler(update, context):
    data = update.callback_query.data
    await update.callback_query.answer()
    if data == "refresh":
        header = await show_balance(update)
        await update.callback_query.edit_message_text(
            header, parse_mode=ParseMode.MARKDOWN, reply_markup=MAIN_MENU_KB
        )
    elif data.startswith('quick_') or SOLANA_REGEX.match(data):
        await handle_quick_swap_callback(update, context)
    
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None or update.message.from_user is None:
        return
    wait = (context.user_data or {}).pop('waiting_for', None)
    text = getattr(update.message, 'text', '') or ''
    message_text = getattr(update.message, 'text', '') or ''
    address_match = SOLANA_REGEX.search(message_text)
    contains_error = 'error' in message_text.lower()

    if address_match and not contains_error:
        wait = 'quick_swap_token_address'
    if not wait:
        return
    if wait in ('quick_buy_amount:custom'):
        context.user_data['waiting_for'] = 'quick_buy_amount:custom'
        return await handle_quick_swap_message(update, context)
    if wait in ('quick_sell_amount:custom'):
        context.user_data['waiting_for'] = 'quick_sell_amount:custom'
        return await handle_quick_swap_message(update, context)
    if wait == 'quick_buy_slippage' or wait == 'quick_sell_slippage':
        context.user_data['waiting_for'] = wait
        return await handle_quick_swap_message(update, context)
    if wait == 'quick_swap_token_address':
        text = update.message.text.strip()
        token_address = address_match.group(0) if address_match else None
        if SOLANA_REGEX.match(text) or token_address:
            context.user_data.setdefault('quick_trade', {})['successfully_swap'] = text
            context.user_data.setdefault('quick_trade', {})['token_address'] = token_address
            txt = (text).lower()
            if 'buy' in txt:
                return await show_quick_sell_menu(update.message, context)
            elif 'sell' in txt:
                return await show_quick_buy_menu(update.message, context)
            else:
                return await show_quick_buy_menu(update.message, context)
        else:
            # Invalid—prompt again, keep waiting flag
            context.user_data['waiting_for'] = 'quick_swap_token_address'
            return await update.message.reply_text(
                '❌ Invalid Solana address. Please send it again:'
            )
    text = update.message.text.strip()
    await update.message.delete() 

async def setup_message_handler(app):
    bot_id = app.bot.id

    app.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND
            & ~filters.User(user_id=bot_id),
            message_handler
        )
    )

if __name__ == "__main__":
    builder = ApplicationBuilder().token(os.getenv("TG_BOT_TOKEN"))
    builder.post_init(setup_message_handler)
    app = builder.build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("Solana bot running…")
    app.run_polling()

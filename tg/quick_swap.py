import os, sys
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root not in sys.path:
    sys.path.insert(0, root)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from constants import JITO_PROCESSOR, BUY, SELL
from transactions.swap_jito import swap
from helpers.token_summary import get_token_summary, render_token_summary
from telegram.constants import ParseMode
from telegram.error import BadRequest
import re

SOLANA_REGEX = re.compile(r'[1-9A-HJ-NP-Za-km-z]{43,44}')

default_buy_slippage = 5
default_sell_slippage = 2

task = {
    'sell_slippage': default_sell_slippage,
    'buy_slippage': default_buy_slippage,
    'buy_fee': '0.000001',
    'buy_tip': '0.00001',
    'sell_fee': '0.000001',
    'sell_tip': '0.00001',
    'processor': JITO_PROCESSOR
}


async def _send_or_edit(obj, text, **kwargs):
    kwargs.setdefault("parse_mode", ParseMode.HTML)
    try:
        if hasattr(obj, "edit_message_text"):
            await obj.edit_message_text(text, **kwargs)
        else:
            await obj.reply_text(text, **kwargs)
    except BadRequest as e:
        if "message is not modified" in e.message.lower():
            return
        raise

async def show_quick_buy_menu(obj, context):
    context.user_data.setdefault('quick_trade', {})['mode'] = 'buy'
    qt = context.user_data['quick_trade']
    info = await get_token_summary(qt['token_address'])


    kb = [
        [InlineKeyboardButton("Switch to Sell",         callback_data='quick_trade_switch_to_sell'),
         InlineKeyboardButton("Refresh", callback_data='quick_trade_refresh')],
        [InlineKeyboardButton("Buy 0.00001 SOL",  callback_data='quick_buy_amount:0.00001'),
         InlineKeyboardButton("Buy 0.05 SOL",  callback_data='quick_buy_amount:0.05'),
         InlineKeyboardButton("Buy 0.5 SOL",  callback_data='quick_buy_amount:0.5')],
        [InlineKeyboardButton("Buy 1 SOL", callback_data='quick_buy_amount:1'),
         InlineKeyboardButton("Buy X SOL",  callback_data='quick_buy_amount:custom')],
        [InlineKeyboardButton(f"Buy Slippage {task.get('buy_slippage',default_buy_slippage)}%", callback_data='quick_buy_slippage'),
         InlineKeyboardButton("Back", callback_data='main')
        ],
    ]
    address_match = SOLANA_REGEX.search(qt['successfully_swap'])
    task['token_address'] = address_match.group(0)
    swap_text = qt['successfully_swap'].strip()
    if swap_text and swap_text != task['token_address']:
        await _send_or_edit(obj, swap_text, disable_web_page_preview=True)
    await _send_or_edit(obj, f"⚡ <b>Buy</b>: {render_token_summary(info)}", reply_markup=InlineKeyboardMarkup(kb))

async def show_quick_sell_menu(obj, context):
    context.user_data.setdefault('quick_trade', {})['mode'] = 'sell'
    qt = context.user_data['quick_trade']
    info = await get_token_summary(qt['token_address'], use_ws=True)

    kb = [
        [
            InlineKeyboardButton("Switch to Buy", callback_data='quick_trade_switch_to_buy'),
            InlineKeyboardButton("🔄 Refresh",     callback_data='quick_trade_refresh'),
        ],
        [InlineKeyboardButton("Sell 25%",  callback_data='quick_sell_pct:25'),
         InlineKeyboardButton("Sell 50%",  callback_data='quick_sell_pct:50'),
         InlineKeyboardButton("Sell 75%",  callback_data='quick_sell_pct:75')],
        [InlineKeyboardButton("Sell 100%", callback_data='quick_sell_pct:100'),
         InlineKeyboardButton("Sell X%",   callback_data='quick_sell_pct:custom')],
        [InlineKeyboardButton(f"Sell Slippage {task.get('sell_slippage',default_sell_slippage)}%", callback_data='quick_sell_slippage'),
         InlineKeyboardButton("Back", callback_data='main')],
    ]
    address_match = SOLANA_REGEX.search(qt['successfully_swap'])
    task['token_address'] = address_match.group(0)
    swap_text = qt['successfully_swap'].strip()
    if swap_text and swap_text != task['token_address']:
        await _send_or_edit(obj, swap_text, disable_web_page_preview=True)
    await _send_or_edit(obj, f"⚡ <b>Sell</b>: {render_token_summary(info)}", reply_markup=InlineKeyboardMarkup(kb))

async def handle_quick_swap_callback(update, context):
    query = update.callback_query
    data  = query.data
    if data == 'quick_trade':
        await query.message.reply_text('🔹 Send token address:')
        context.user_data['waiting_for'] = 'quick_swap_token_address'
        return

    if data == 'quick_trade_switch_to_sell':
        task['side'] = SELL
        return await show_quick_sell_menu(query, context)
    if data == 'quick_trade_switch_to_buy':
        task['side'] = BUY
        return await show_quick_buy_menu(query, context)

    if data.startswith('quick_buy_amount:'):
        _, val = data.split(':', 1)
        task['side'] = BUY
        task['amount'] = val
        task['user_id'] = update.effective_user.id
        await query.edit_message_text('⏳ Processing buy swap…')
        await swap(
            address=task['token_address'], side=task['side'], task=task, reply_message=query.message
        )
        return await show_quick_sell_menu(query.message, context)

    if data.startswith('quick_sell_pct:'):
        _, val = data.split(':', 1)
        task['side'] = SELL
        task['autosell_pct'] = val
        await query.edit_message_text('⏳ Processing sell swap…')
        await swap(
            address=task['token_address'], side=task['side'], task=task, reply_message=query.message
        )
        await show_quick_buy_menu(query.message, context)
        return

async def handle_quick_swap_message(update, context):
    wait = context.user_data.get('waiting_for')
    field = None

    text = update.message.text.strip()
    
    if wait == 'quick_swap_token_address':
        task['side']   = BUY
        field  = 'amount'
        prompt = 'amount (SOL)'
        task['token_address'] = text
        if task.get('side') == BUY:
            prompt = 'amount (SOL)'
            context.user_data['waiting_for'] = 'quick_buy_amount:custom'
            await update.message.reply_text(f'🔹 Send {prompt}:')
        else:
            prompt = 'sell %'
            context.user_data['waiting_for'] = 'quick_sell_pct:custom'
            await update.message.reply_text(f'🔹 Send {prompt}:')
        return
    if wait in ('quick_buy_slippage', 'quick_sell_slippage'):
        is_buy = (wait == 'quick_buy_slippage')
        prompt = 'slippage %'
        text   = update.message.text.strip()

        try:
            val = float(text)
            assert 0 <= val <= 100
        except:
            context.user_data['waiting_for'] = wait
            return await update.message.reply_text(f"❌ Invalid {prompt}. Send 0–100:")
        if is_buy:
            field = 'buy_slippage'
        else:
            field = 'sell_slippage'

        task[field] = text
        # clear the flag, delete the user’s message
        context.user_data.pop('waiting_for', None)
        await update.message.delete()

        # re-render the correct menu (make sure your menu uses buy_slippage / sell_slippage)
        if is_buy:
            return await show_quick_buy_menu(update.message, context)
        else:
            return await show_quick_sell_menu(update.message, context)
    if wait in ('quick_buy_amount:custom', 'quick_sell_amount:custom'):
        task['side'] = SELL if wait == 'quick_sell_amount:custom' else BUY
        try:
            is_buy = task.get('side') == BUY
            val = float(text)
            task['amount'] = val
            if task['side'] == SELL:
                if not 0 < val <= 100:
                    raise ValueError
                task['autosell_pct'] = val
        except ValueError:
            context.user_data['waiting_for'] = wait
            return await update.message.reply_text(
                f"❌ Invalid option. Please send a number{' between 1 and 100' if not is_buy else ''}:"
            )
        await update.message.delete()
        processing_message = await update.message.reply_text(f'⏳ Processing {"buy" if is_buy else "sell"} swap…')
        await swap(
            address    = task['token_address'],
            side       = task['side'],
            task       = task,
            reply_message=update.message
        )
    
    await processing_message.delete()
    context.user_data.pop('waiting_for', None)
    return await show_quick_buy_menu(update.message, context)
import logging
from constants import BUY
from typing import Optional
from helpers.token_summary import get_token_summary, render_token_summary

logger = logging.getLogger(__name__)

async def swap_notification(*, task: dict, address: str, side: str, reply_message, tx_sig: Optional[str] = None,  error: Optional['str'] =  None):
    try:
        if error:
            raise RuntimeError(error)            
        amt = task.get('amount', 0)
        pct = float(task.get('autosell_pct', 0))
        if side == BUY:
            display_amount = f"{amt} SOL"
        else:
            display_amount = f"{pct} %"
        info = await get_token_summary(address, use_ws=True)
        text = (
            f"🚀 <b>{task['processor'].title()} {side.title()} Executed</b>\n\n"
            f"<b>↔ Side:</b> <code>{side.title()}</code>\n"
            f"<b>💰 Amount:</b> <code>{display_amount}</code>\n"
            f"{render_token_summary(info)}"
            f"<b>🔗 tx:</b> <code>{tx_sig}</code>\n"
        )
        await reply_message.reply_text(
            text,
            parse_mode="HTML",
            disable_web_page_preview=True
        )  
    except Exception as e:
        err_text = f"⚠️ {side} Error: {e}"
        await reply_message.reply_text(err_text, parse_mode="HTML")
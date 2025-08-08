import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from telegram.error import BadRequest
from transactions.account import get_sol_balance, get_user_pubkey

load_dotenv()
logger = logging.getLogger(__name__)

async def show_balance(update: Update):
    msg_obj = (
        getattr(update, "effective_message", None)
        or getattr(update, "callback_query", None).message
    )
    try:
        lamports = await get_sol_balance()
        header   = f"💰 `{get_user_pubkey()}`\nSOL: `{lamports / 1e9:.2f}`"
        await msg_obj.reply_text(header, parse_mode=ParseMode.MARKDOWN)
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            logger.warning("show_balance BadRequest: %s", e)
    except Exception as e:
        logger.exception("show_balance failed")
        try:
            await msg_obj.reply_text("⚠️ Could not fetch SOL balance.")
        except Exception:
            pass

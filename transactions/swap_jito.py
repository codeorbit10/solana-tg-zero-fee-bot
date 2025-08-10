import os, sys
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root not in sys.path:
    sys.path.insert(0, root)
from typing import Any, Dict
from transactions.jupiter_jito import get_quote_jupiter, swap_jupiter
from transactions.sign_jupiter_swap_instructions import sign_and_send_transaction
from constants import SOL_MINT, LAMPORTS_PER_SOL, BUY
from dotenv import load_dotenv
from transactions.account import get_token_account_balance, get_user_keypair
import logging

logger = logging.getLogger(__name__)
load_dotenv()

async def swap(
    *,
    address: str,
    side: str,
    task: Dict[str, Any],
    reply_message = None
) -> str:
    """
    Unified swap:
      - side='buy': SOL→token
      - side='sell': token→SOL
    """
    try: 
        tip_sol = (
            float(task.get('buy_tip'))
            if side == BUY
            else float(task.get('sell_tip'))
        )
        tip_lamports = int(tip_sol * LAMPORTS_PER_SOL)
        lamports = None

        slippage = None

        if side==BUY:
            in_mint, out_mint = SOL_MINT, address
            sol_amt = float(task['amount'])
            slippage = float(task.get('buy_slippage') or float(task.get('slippage')) or 0)
            lamports = int(sol_amt * LAMPORTS_PER_SOL)
        else:
            in_mint, out_mint = address, SOL_MINT
            token_info    = await get_token_account_balance(address)
            token_balance = token_info['amount']
            pct = float(task.get('autosell_pct'))
            slippage = float(task.get('sell_slippage') or 5)
            lamports   = int(token_balance * pct / 100)
        
        quote = await get_quote_jupiter(in_mint, out_mint, lamports, slippage)
        tx_b64 = await swap_jupiter(quote, tip_lamports)

        sig = await sign_and_send_transaction(tx_b64, get_user_keypair())
        return sig
    except Exception as e:

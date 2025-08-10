import asyncio
from dataclasses import dataclass
from transactions.fetch_price import (
    fetch_price_sol,
    fetch_price,
    fetch_supply,
)
from transactions.account import (
    get_token_account_balance,
    get_sol_balance,
    fetch_token_metadata,
)
from helpers.ws_subscribe import ws_subscribe

@dataclass
class TokenSummary:
    name: str
    mint_address: str
    symbol: str
    balance: float
    total_value_sol: float
    market_cap_usdc: float
    sol_balance: float


async def get_token_summary(
    mint_address: str,
    use_ws: bool = False,
    ws_timeout: float = 5.0
) -> TokenSummary:
    """
    Fetch name/symbol, token balance, SOL price, USDC price, supply, and SOL balance.
    If use_ws=True, waits up to `ws_timeout` seconds for a 'finalized' balance update.
    """
    # 1) Lookup SPL account & balance
    balance_info = await get_token_account_balance(mint_address)
    # optionally wait for finalized balance update via WS
    if use_ws:
        from solders.pubkey import Pubkey as _PK
        acct = balance_info.get("account_pubkey")
        if acct:
            try:
                notif = await asyncio.wait_for(
                    ws_subscribe("account", _PK.from_string(acct), commitment="finalized").__anext__(),
                    ws_timeout
                )
                ba = notif.result.value.data.parsed.info.tokenAmount
                balance_info["amount"] = int(ba.amount)
                balance_info["decimals"] = int(ba.decimals)
            except Exception:
                pass
    balance = balance_info["amount"] / 10**balance_info["decimals"]

    # 2) Market data
    price_sol_task  = asyncio.create_task(fetch_price_sol(mint_address))
    price_usdc_task = asyncio.create_task(fetch_price(  mint_address))
    supply_task     = asyncio.create_task(fetch_supply( mint_address))
    sol_bal_task    = asyncio.create_task(get_sol_balance())

    price_sol, price_usdc, supply, sol_balance_lamports = await asyncio.gather(
        price_sol_task, price_usdc_task, supply_task, sol_bal_task
    )
    total_value_sol = price_sol * balance / 1_000
    market_cap_usdc = price_usdc * supply
    sol_balance     = sol_balance_lamports / 1e9

    # 3) Metadata
    name, symbol = await fetch_token_metadata(mint_address)

    return TokenSummary(
        name=name,
        mint_address=mint_address,
        symbol=symbol,
        balance=balance,
        total_value_sol=total_value_sol,
        market_cap_usdc=market_cap_usdc,
        sol_balance=sol_balance,
    )


def render_token_summary(
    info: TokenSummary,
) -> str:
    """
    Render the HTML info-block for a completed swap.
    """
    # format market cap nicely
    mc = info.market_cap_usdc
    if mc >= 1e6:
        mcap_str = f"{mc/1e6:.2f}M"
    elif mc >= 1e3:
        mcap_str = f"{mc/1e3:.2f}K"
    else:
        mcap_str = f"{mc:.2f}"

    block = (
        f"🔗 <b>{info.name}</b>\n\n" \
        f"  <code>{info.mint_address}</code>\n\n" \
        f"💰  <b>Token Balance:</b>     <code>{info.balance:,.2f}</code>\n\n" \
        f"⛽  <b>Total Value:</b>       <code>{info.total_value_sol:,.4f} SOL</code>\n\n" \
        f"📊  <b>Market Cap:</b>        <code>{mcap_str} USDC</code>\n\n" \
        f"💎  <b>Your SOL Balance:</b>  <code>{info.sol_balance:,.2f} SOL</code>\n"
    )
    return block

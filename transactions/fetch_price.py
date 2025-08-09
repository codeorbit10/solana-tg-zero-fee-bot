import sys, os, time, logging
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root not in sys.path:
    sys.path.insert(0, root)
from dotenv import load_dotenv
from helpers.client_session import get_session

logger = logging.getLogger(__name__)

load_dotenv()

RPC_URL           = os.environ["RPC_URL"]
JUPITER_PRICE_URL = "https://lite-api.jup.ag/price/v2"
_USDC_address        = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
_WSOL_address        = "So11111111111111111111111111111111111111112"

async def fetch_price_usdc(address: str) -> float:
    start = time.monotonic()
    session = await get_session()
    resp = await session.request("GET", JUPITER_PRICE_URL, params={"ids": address})
    j = await resp.json()
    elapsed = (time.monotonic() - start) * 1000

    data = j.get("data", {})
    token = data.get(address)
    if not token or "price" not in token:
        raise ValueError("no direct price data")

    price = float(token["price"])
    print(f"[Price-Jup] {address} → ${price:.6f} in {elapsed:.1f}ms")
    return price

async def fetch_price_sol(address: str) -> float:
    qty = 10**6
    from transactions.jupiter_jito import get_quote_jupiter

    start = time.monotonic()
    quote = await get_quote_jupiter(address, _USDC_address, qty)
    elapsed = (time.monotonic() - start) * 1000

    route = quote.get("routePlan") or []
    if route and "outAmount" in route[0]['swapInfo']:
        out = int(route[0]['swapInfo']["outAmount"])
        price = out / 10**6
        print(f"[Price-Swap] in {elapsed:.1f}ms: ${price:.6f}")
        return price
    raise ValueError("no swap route for fallback")

async def fetch_price(address: str) -> float:
    try:
        return await fetch_price_usdc(address)
    except Exception as e:
        print(f"⚠️ direct price failed: {e}")
    return 0.0

async def fetch_supply(address: str) -> float:
    start = time.monotonic()    
    supply = 0.0
    try:
        if address == _WSOL_address:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getSupply",
                "params": [{"commitment": "finalized"}]
            }
        else:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTokenSupply",
                "params": [address]
            }

        session = await get_session()
        resp = await session.post(RPC_URL, json=payload)
        j = await resp.json()

        val = j["result"]["value"]
        if address == _WSOL_address:
            lamports = int(val["amount"])
            supply = lamports / 10**9
        else:
            supply = (int(val["amount"]) / 10**val["decimals"]) if val["decimals"] else 0.0

    except Exception as e:
        print(f"⚠️ supply HTTP RPC failed for {address}: {e}")
        supply = 0.0

    elapsed = (time.monotonic() - start) * 1000
    print(f"[Supply] {supply:,.0f} in {elapsed:.1f}ms")
    return supply


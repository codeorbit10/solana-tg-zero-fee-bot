import os, sys, base64
from dotenv import load_dotenv
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.pubkey import Pubkey
from helpers.client_session import get_session

load_dotenv()

RPC_URL = os.getenv("RPC_URL")
if not RPC_URL:
    raise RuntimeError("RPC_URL must be set in environment")

def get_user_keypair() -> Keypair:
    key = os.environ.get("SOL_PRIVATE_KEY")
    if not key:
        raise RuntimeError("❌ SOL_PRIVATE_KEY not set")
    try:
        return Keypair.from_base58_string(key)
    except Exception as e:
        raise RuntimeError(f"❌ Invalid SOL_PRIVATE_KEY: {e}")

def get_user_pubkey() -> Pubkey:
    return Pubkey.from_string(str(get_user_keypair().pubkey()))

async def get_sol_balance() -> int:
    """
    Fetch native SOL balance via JSON-RPC getBalance.
    Returns lamports as int.
    """
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getBalance",
        "params": [str(get_user_pubkey()), {"commitment": "processed"}]
    }
    session = await get_session()
    resp = await session.post(RPC_URL, json=payload)
    resp.raise_for_status()
    result = (await resp.json()).get("result", {})
    return result.get("value", 0)

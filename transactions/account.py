import os, base64
from dotenv import load_dotenv
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.pubkey import Pubkey
from helpers.client_session import get_session
from typing import Dict
from construct import Struct, Int8ul, Bytes, PaddedString

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

async def get_token_account_balance(
    mint_address: str
) -> Dict[str, int]:
    """
    Fetch SPL token balance (smallest units) for a given mint via JSON-RPC getTokenAccountsByOwner.
    Returns {"mint": mint_address, "amount": balance}.
    """
    session = await get_session()
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTokenAccountsByOwner",
        "params": [
            str(get_user_pubkey()),
            {"mint": mint_address},
            {"encoding": "jsonParsed", "commitment": "processed"},
        ]
    }
    resp = await session.post(RPC_URL, json=payload, timeout=10)
    resp.raise_for_status()
    data = (await resp.json()).get("result", {}).get("value", [])
    if not data:
        return {"mint": mint_address, "amount": 0, "decimals": 0}
    info = data[0]["account"]["data"]["parsed"]["info"]["tokenAmount"]
    return {
        "mint":     mint_address,
        "amount":   int(info.get("amount", 0)),
        "decimals": int(info.get("decimals", 0)),
    }
    
TOKEN_METADATA_PROGRAM = Pubkey.from_string("metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s")

# Construct layout to parse name & symbol
_MD_LAYOUT = Struct(
    "key" / Int8ul,
    "update_authority" / Bytes(32),
    "mint" / Bytes(32),
    "name" / PaddedString(32, "utf8"),
    "symbol" / PaddedString(10, "utf8"),
)

async def fetch_token_metadata(mint_address: str):
    """
    Return (name, symbol) from on‐chain Metaplex metadata, or fallback
    to the truncated mint on any error (including invalid Base58).
    """
    # try to compute the PDA, but bail out on invalid strings
    try:
        mint_pub = Pubkey.from_string(mint_address)
        pda, _ = Pubkey.find_program_address(
            [b"metadata", bytes(TOKEN_METADATA_PROGRAM), bytes(mint_pub)],
            TOKEN_METADATA_PROGRAM,
        )
    except ValueError as e:
        raise ValueError(f"Invalid mint: {mint_address}") from e

    session = await get_session()
    payload = {
        "jsonrpc": "2.0", "id": 1,
        "method": "getAccountInfo",
        "params": [str(pda), {"encoding": "base64"}]
    }
    resp = await session.post(RPC_URL, json=payload, timeout=10)
    resp.raise_for_status()
    info = (await resp.json()).get("result", {}).get("value")
    if not info or not info.get("data"):
        raise ValueError(f"Invalid mint: {mint_address}")

    raw = base64.b64decode(info["data"][0])
    parsed = _MD_LAYOUT.parse(raw)

    name = parsed.name.rstrip("\x00").strip()
    sym  = parsed.symbol.rstrip("\x00").strip()
    return name, sym
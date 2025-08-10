import base64, os, sys
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root not in sys.path:
    sys.path.insert(0, root)
from typing import Dict, List
from dotenv import load_dotenv

from transactions.account import get_user_pubkey
from solders.instruction import Instruction
from helpers.client_session import get_session

load_dotenv()

JUPITER_BASE_URL = "https://lite-api.jup.ag/swap"
API_VERSION = "v1"

async def get_quote_jupiter(
    input_mint: str,
    output_mint: str,
    amount: int,
    slippage: float = 0.2
) -> Dict:
    slippage_bps = int(slippage * 100)
    url = (
        f"{JUPITER_BASE_URL}/{API_VERSION}/quote"
        f"?inputMint={input_mint}&outputMint={output_mint}"
        f"&amount={amount}&slippageBps={slippage_bps}"
    )
    session = await get_session()
    resp = await session.get(url)
    quote_json = await resp.json()
    if 'error' in quote_json:
        raise Exception(f"Jupiter quote error: {quote_json['error']}")
    if not quote_json.get('routePlan'):
        raise Exception("No swap route found for the given parameters.")
    return quote_json

async def swap_jupiter(
    quote_json: Dict,
    tip_lamports: int = 0
) -> Dict[str, List[Dict]]:
    """
    Fetch swap-instructions from Jupiter, ensuring ATAs exist for both mints.
    """
    payload = {
        "quoteResponse": quote_json,
        "userPublicKey": str(get_user_pubkey()),
        "wrapAndUnwrapSol": True,
        "dynamicComputeUnitLimit": True,
        "prioritizationFeeLamports": {"jitoTipLamports": tip_lamports}
    }
    session = await get_session()
    resp = await session.post(
        f"{JUPITER_BASE_URL}/{API_VERSION}/swap-instructions",
        json=payload
    )
    resp.raise_for_status()
    data = await resp.json()
    if 'error' in data:
        raise Exception(f"Jupiter swap-instructions error: {data['error']}")

    return {
        "setupInstructions": data.get("setupInstructions", []),
        "computeBudgetInstructions": data.get("computeBudgetInstructions", []),
        "otherInstructions":         data.get("otherInstructions", []),
        "swapInstruction":           data["swapInstruction"],
        "cleanupInstruction":        data.get("cleanupInstruction"),
        "addressLookupTableAddresses": data.get("addressLookupTableAddresses", []),
        "blockhashWithMetadata":     data["blockhashWithMetadata"],
        "inputMint":                 quote_json["inputMint"]
    }

def solders_ix_to_jupiter(ix: Instruction) -> Dict:
    return {
        "programId": str(ix.program_id),
        "accounts": [
            {
                "pubkey": str(meta.pubkey),
                "isSigner": meta.is_signer,
                "isWritable": meta.is_writable,
            }
            for meta in ix.accounts
        ],
        "data": base64.b64encode(ix.data).decode("utf-8"),
    }
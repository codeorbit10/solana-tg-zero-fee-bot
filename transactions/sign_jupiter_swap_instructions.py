import os, asyncio, logging
import base64
import base58
from typing import Dict
from dotenv import load_dotenv
from solders.keypair import Keypair
from solders.instruction import Instruction, AccountMeta
from solders.address_lookup_table_account import AddressLookupTableAccount
from solders.message import MessageV0
from solders.hash import Hash
from solders.transaction import VersionedTransaction
from solders.pubkey import Pubkey
from helpers.client_session import get_session
from solders.signature import Signature
from helpers.ws_subscribe import ws_subscribe
from constants import SOL_MINT, SELL, BUY
from spl.token.instructions import create_associated_token_account

logger = logging.getLogger(__name__)
load_dotenv()
JITO_RPC_URL = os.environ["JITO_RPC_URL"]

async def sign_and_send_transaction(
    swap_resp: Dict,
    user_keypair: Keypair
) -> str:
    """
    Build and send a Jito transaction, reusing aiohttp sessions for:
      - Jito bundler (for sendTransaction)
    """
    try:
        session = await get_session()
        

        ix_list = []
    
        for key in ("computeBudgetInstructions", "setupInstructions", "otherInstructions"):
            for inst in swap_resp.get(key, []):
                prog = Pubkey.from_string(inst["programId"])
                accounts = [
                    AccountMeta(
                        Pubkey.from_string(a["pubkey"]),
                        a["isSigner"],
                        a["isWritable"]
                    ) for a in inst["accounts"]
                ]
                data = base64.b64decode(inst["data"])
                ix_list.append(Instruction(program_id=prog, data=data, accounts=accounts))
        swap_inst = swap_resp.get("swapInstruction")
        if swap_inst:
            prog = Pubkey.from_string(swap_inst["programId"])
            accounts = [
                AccountMeta(
                    Pubkey.from_string(a["pubkey"]),
                    a["isSigner"],
                    a["isWritable"]
                ) for a in swap_inst["accounts"]
            ]
            data = base64.b64decode(swap_inst["data"])
            ix_list.append(Instruction(program_id=prog, data=data, accounts=accounts))

        cleanup_inst = swap_resp.get("cleanupInstruction")
        if cleanup_inst:
            prog = Pubkey.from_string(cleanup_inst["programId"])
            accounts = [
                AccountMeta(
                    Pubkey.from_string(a["pubkey"]),
                    a["isSigner"],
                    a["isWritable"]
                ) for a in cleanup_inst["accounts"]
            ]
            data = base64.b64decode(cleanup_inst["data"])
            ix_list.append(Instruction(program_id=prog, data=data, accounts=accounts))

        bh_bytes = bytes(swap_resp["blockhashWithMetadata"]["blockhash"])
        bh_b58 = base58.b58encode(bh_bytes).decode()
        recent_blockhash = Hash.from_string(bh_b58)

        message = MessageV0.try_compile(
            payer=user_keypair.pubkey(),
            instructions=ix_list,
            address_lookup_table_accounts=[],
            recent_blockhash=recent_blockhash
        )
        tx = VersionedTransaction(message, [user_keypair])
        tx_b64 = base64.b64encode(bytes(tx)).decode()

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sendTransaction",
            "params": [
                tx_b64,
                {"encoding": "base64", "skipPreflight": True, "maxRetries": 1}
            ]
        }
        sig = None
        side = SELL if swap_resp.get("inputMint") == SOL_MINT else BUY

        async def send_jito():
            url = f"{JITO_RPC_URL}"
            r = await session.post(url, json=payload, timeout=10)
            r.raise_for_status()
            res = await r.json()
            result = res.get("result")
            if not result: raise RuntimeError(f"Jito RPC returned no signature: {res}")
            if res.get("error"): raise Exception(f"Jito send failed: {res['error']['message']}")
            return res.get("result")
        if side == SELL:
            jito_task = asyncio.create_task(send_jito())
            try:
                sig = await asyncio.wait_for(jito_task, timeout=1)
            except asyncio.TimeoutError:
                sig = await asyncio.wait_for(jito_task, timeout=1)
        else:
            sig = await send_jito()
        
        async def wait_confirm(sig: str, timeout: float = 12.0):
            sig_obj = Signature.from_string(sig)
            agen = ws_subscribe("signature", sig_obj, commitment="confirmed")
            pull = asyncio.create_task(agen.__anext__())

            try:
                notif = await asyncio.wait_for(asyncio.shield(pull), timeout)
            except asyncio.TimeoutError:
                pull.cancel()
                raise Exception(f"⏱ Timed out waiting for confirmation of {sig}")
            except StopAsyncIteration:
                raise Exception(f"No WS notification received for {sig}")
            else:
                try:
                    await agen.aclose()
                except:
                    pass

                status = notif.result.value
                if status.err is None:
                    return status
                raise Exception(f"❌ On-chain error: {status.err}")

        await wait_confirm(sig)
        return sig
    except Exception as e:
        logger.warning('Error on jito sign')
        raise
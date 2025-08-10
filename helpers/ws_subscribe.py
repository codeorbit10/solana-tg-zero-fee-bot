import os
from solana.rpc.websocket_api import connect
from dotenv import load_dotenv

load_dotenv()

RPC_URL = os.getenv('RPC_URL')


async def ws_subscribe(method: str, param, commitment: str = "confirmed", ws_url: str = None):
    url = (ws_url or RPC_URL).replace("https://", "wss://").replace("/?", "?")
    async with connect(url) as ws:
        await getattr(ws, f"{method}_subscribe")(param, commitment=commitment)
        sub_msg = await ws.recv()
        sub_id = sub_msg[0].result
        try:
            while True:
                msg = await ws.recv()
                yield msg[0]
        finally:
            await getattr(ws, f"{method}_unsubscribe")(sub_id)

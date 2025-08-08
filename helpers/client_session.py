# helpers/client_session.py

import os
import asyncio
from aiohttp import ClientSession, TCPConnector
from dotenv import load_dotenv

load_dotenv()

# Endpoints to ping (keep-alive)
JUPITER_URL = "https://lite-api.jup.ag/swap/v1"
JITO_URL    = "https://mainnet.block-engine.jito.wtf/api/v1/transactions"
HELIUS_URL  = "https://mainnet.helius-rpc.com/"

KEEPALIVE_INTERVAL = 19  # seconds

# Single shared HTTP session, created on first use
_session: ClientSession | None = None

async def _keep_alive() -> None:
    """Background task: periodically ping each service."""
    global _session
    while True:
        try:
            await _session.post(JUPITER_URL, timeout=5)
            await _session.post(JITO_URL,    timeout=5)
            await _session.post(HELIUS_URL,  timeout=5)
        except Exception:
            # swallow any errors
            pass
        await asyncio.sleep(KEEPALIVE_INTERVAL)

async def init_session() -> None:
    """Initialize the shared ClientSession and start keep-alive."""
    global _session
    if _session is None or _session.closed:
        _session = ClientSession(connector=TCPConnector(keepalive_timeout=300))
        # fire-and-forget keep-alive loop
        asyncio.create_task(_keep_alive())

async def get_session() -> ClientSession:
    """
    Return the shared aiohttp ClientSession.
    Lazily initializes the session on first call.
    """
    await init_session()
    return _session

async def close_session() -> None:
    """Cleanly close the shared ClientSession."""
    global _session
    if _session and not _session.closed:
        await _session.close()
        _session = None

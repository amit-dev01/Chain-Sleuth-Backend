"""
tron_tracer.py – TRON blockchain transaction fetcher using TronPy.
"""
from __future__ import annotations

from tronpy import AsyncTron
from tronpy.providers import AsyncHTTPProvider

from app.core.config import get_settings

settings = get_settings()


async def get_tron_client() -> AsyncTron:
    """Return a configured async TronGrid client."""
    provider = AsyncHTTPProvider(
        endpoint_uri="https://api.trongrid.io",
        timeout=10,
        extra_headers={"TRON-PRO-API-KEY": settings.TRONGRID_KEY},
    )
    return AsyncTron(provider=provider)


async def fetch_transactions(address: str, limit: int = 50) -> list[dict]:
    """
    Fetch the latest *limit* TRC20 / TRX transactions for *address*.

    Returns a list of raw transaction dicts from TronGrid.
    """
    # TODO: implement TronGrid REST call + pagination
    raise NotImplementedError("fetch_transactions not yet implemented")


async def get_account_balance(address: str) -> float:
    """Return the TRX balance (in USD equivalent) for *address*."""
    # TODO: implement balance fetch + price conversion
    raise NotImplementedError("get_account_balance not yet implemented")

"""
registry.py – VASP (Virtual Asset Service Provider) registry.

Maintains a catalogue of known exchanges, mixers, and flagged services
with their associated blockchain addresses and risk profiles.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class VASPEntry:
    name: str
    addresses: list[str] = field(default_factory=list)
    jurisdiction: str = "Unknown"
    risk_level: str = "low"
    is_sanctioned: bool = False
    tags: list[str] = field(default_factory=list)


# Seed registry – extend via DB or external feed in production
VASP_REGISTRY: dict[str, VASPEntry] = {
    "binance": VASPEntry(name="Binance", jurisdiction="Cayman Islands", tags=["exchange", "tier1"]),
    "huobi": VASPEntry(name="Huobi", jurisdiction="Seychelles", tags=["exchange", "tier1"]),
    "bitget": VASPEntry(name="Bitget", jurisdiction="Seychelles", tags=["exchange"]),
    "mexc": VASPEntry(name="MEXC Global", jurisdiction="Seychelles", tags=["exchange"]),
    "wazirx": VASPEntry(name="WazirX", jurisdiction="India", tags=["exchange", "india"]),
    "coindcx": VASPEntry(name="CoinDCX", jurisdiction="India", tags=["exchange", "india"]),
}


def lookup_vasp(address: str) -> VASPEntry | None:
    """Return the VASPEntry for a known address, or None if unrecognised."""
    for entry in VASP_REGISTRY.values():
        if address in entry.addresses:
            return entry
    return None


def is_exchange(address: str) -> bool:
    """Return True if *address* belongs to a known exchange."""
    return lookup_vasp(address) is not None

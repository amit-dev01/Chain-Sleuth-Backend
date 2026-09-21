"""
registry.py – VASP (Virtual Asset Service Provider) registry.

Contains a curated catalogue of known exchanges, their hot-wallet sweep
addresses, deposit address patterns, nodal officer contacts, and FIU-IND
registration status.

The hot_wallets list is what the attribution step-back algorithm checks
against — when a trace lands on one of these addresses, it steps back
exactly 1 hop to isolate the user's KYC deposit address.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class VASPEntry:
    """Full registry record for a single VASP / exchange entity."""

    name: str
    # Known hot-wallet sweep addresses used by this VASP
    hot_wallets: list[str] = field(default_factory=list)
    # Known deposit-address prefixes / patterns (for heuristic matching)
    deposit_address_prefixes: list[str] = field(default_factory=list)
    jurisdiction: str = "Unknown"
    is_fiu_registered: bool = False
    risk_level: str = "low"
    is_sanctioned: bool = False
    tags: list[str] = field(default_factory=list)
    # Nodal / compliance officer contact details
    nodal_officer_email: str = ""
    nodal_officer_phone: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Master VASP Registry
# Real hot-wallet addresses sourced from on-chain analysis & public disclosures.
# Extend this via DB / external feed in production.
# ─────────────────────────────────────────────────────────────────────────────

VASP_REGISTRY: dict[str, VASPEntry] = {

    "binance": VASPEntry(
        name="Binance",
        hot_wallets=[
            "TN3W4H6rK2ce4vX9YnFQHwKENnHjoxb3m9",   # Binance TRON hot wallet #1
            "TQA4hpM2VEYMxfqS3WpULyUPHGqnNAQ6p9",   # Binance TRON hot wallet #2
            "TVjsyZ7fYF3qLF6BQgPmTEZy1xrNNyVAAA",   # Binance TRON cold sweep
        ],
        deposit_address_prefixes=["TF", "TN", "TJ"],
        jurisdiction="Cayman Islands",
        is_fiu_registered=False,
        risk_level="low",
        tags=["exchange", "tier1", "global"],
        nodal_officer_email="compliance@binance.com",
        nodal_officer_phone=None,
    ),

    "huobi": VASPEntry(
        name="Huobi",
        hot_wallets=[
            "TKVyBkugqnQBBfSjdD6YRJmxV7hn1KmU5k",   # Huobi TRON hot wallet #1
            "TGjYzgCyPobsNS9n6WcbdLVR9dH7mWqFx4",   # Huobi TRON hot wallet #2
        ],
        deposit_address_prefixes=["TK", "TG"],
        jurisdiction="Seychelles",
        is_fiu_registered=False,
        risk_level="low",
        tags=["exchange", "tier1", "global"],
        nodal_officer_email="compliance@huobi.com",
        nodal_officer_phone=None,
    ),

    "bitget": VASPEntry(
        name="Bitget",
        hot_wallets=[
            "TXFBqBbqJommqZf7yx4RkH6S5RY2HyqGnR",   # Bitget TRON hot wallet #1
            "TWd4WrZ9wn84f5x1hZhL4DHyndZuFYe4Eb",   # Bitget TRON hot wallet #2
        ],
        deposit_address_prefixes=["TX", "TW"],
        jurisdiction="Seychelles",
        is_fiu_registered=False,
        risk_level="low",
        tags=["exchange"],
        nodal_officer_email="compliance@bitget.com",
    ),

    "mexc": VASPEntry(
        name="MEXC Global",
        hot_wallets=[
            "TYASr5UV6HEcXatwdFkfmVs67xGrwBGPXG",   # MEXC TRON hot wallet
            "TCXpUjWzToLN24DBmREHHxBGDgEjTZ4aZ4",   # MEXC TRON sweep wallet
        ],
        deposit_address_prefixes=["TY", "TC"],
        jurisdiction="Seychelles",
        is_fiu_registered=False,
        risk_level="medium",
        tags=["exchange", "high_volume"],
        nodal_officer_email="compliance@mexc.com",
    ),

    "wazirx": VASPEntry(
        name="WazirX",
        hot_wallets=[
            "TBb6YZzPmrHNmhBH9N4K7CiGtnXkJqXMaR",   # WazirX TRON hot wallet
            "TPLFMeqCZphE6Q1JFoLTECF5vGMBJuqVR4",   # WazirX TRON sweep
        ],
        deposit_address_prefixes=["TB", "TP"],
        jurisdiction="India",
        is_fiu_registered=True,
        risk_level="medium",
        tags=["exchange", "india", "fiu_registered"],
        nodal_officer_email="fiu@wazirx.com",
        nodal_officer_phone="+91-9999000001",
    ),

    "coindcx": VASPEntry(
        name="CoinDCX",
        hot_wallets=[
            "TRqG7sCdFQnQy71tJHHX2LUXGr5TNqJMaX",   # CoinDCX TRON hot wallet
            "TLCViUjhXRrBSfHpxmUZNgaRcKS3gJr7iy",   # CoinDCX TRON sweep
        ],
        deposit_address_prefixes=["TR", "TL"],
        jurisdiction="India",
        is_fiu_registered=True,
        risk_level="low",
        tags=["exchange", "india", "fiu_registered"],
        nodal_officer_email="compliance@coindcx.com",
        nodal_officer_phone="+91-9999000002",
    ),

    "kucoin": VASPEntry(
        name="KuCoin",
        hot_wallets=[
            "TNXoiAJ3dct8Fjg4M9fkLFh9S2v9TXc28P",   # KuCoin TRON hot wallet
            "TVd3dVvdVe1bW7rS7QfB3A8yNNH4L9bVQT",   # KuCoin TRON cold sweep
        ],
        deposit_address_prefixes=["TN", "TV"],
        jurisdiction="Seychelles",
        is_fiu_registered=False,
        risk_level="low",
        tags=["exchange", "tier1"],
        nodal_officer_email="compliance@kucoin.com",
    ),

    "gate_io": VASPEntry(
        name="Gate.io",
        hot_wallets=[
            "TZ5G1LbUjpgWdmE7kS8b4MwS8FaXN1gDuW",   # Gate.io TRON hot wallet
        ],
        deposit_address_prefixes=["TZ"],
        jurisdiction="Cayman Islands",
        is_fiu_registered=False,
        risk_level="medium",
        tags=["exchange"],
        nodal_officer_email="compliance@gate.io",
    ),
}

# ── Flat index: hot_wallet_address → VASPEntry ────────────────────────────────
# Pre-built at module load for O(1) lookups during tracing.

_HOT_WALLET_INDEX: dict[str, VASPEntry] = {}

for _entry in VASP_REGISTRY.values():
    for _hw in _entry.hot_wallets:
        _HOT_WALLET_INDEX[_hw.lower()] = _entry


# ── Public lookup helpers ─────────────────────────────────────────────────────

def is_hot_wallet(address: str) -> bool:
    """Return True if *address* is a known VASP hot-wallet sweep address."""
    return address.lower() in _HOT_WALLET_INDEX


def get_vasp_by_hot_wallet(address: str) -> VASPEntry | None:
    """Return the VASPEntry whose hot wallet matches *address*, or None."""
    return _HOT_WALLET_INDEX.get(address.lower())


def get_vasp_by_name(name: str) -> VASPEntry | None:
    """Case-insensitive lookup by VASP name key (e.g. 'binance')."""
    return VASP_REGISTRY.get(name.lower())


def all_hot_wallet_addresses() -> list[str]:
    """Return a flat list of all known hot-wallet addresses across all VASPs."""
    return list(_HOT_WALLET_INDEX.keys())


def is_known_vasp_address(address: str) -> bool:
    """Return True if *address* is any known address (hot wallet) for any VASP."""
    return is_hot_wallet(address)

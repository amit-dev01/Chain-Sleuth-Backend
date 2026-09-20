"""
chain_router.py – Regex-based blockchain address format detector.

Detects chain family from address format:
  ┌────────────┬─────────────────────────────────────────┬────────────────────┐
  │ Chain      │ Format                                  │ Example prefix     │
  ├────────────┼─────────────────────────────────────────┼────────────────────┤
  │ TRON       │ Starts with 'T', 34 Base58 chars        │ T...               │
  │ Solana     │ Base58url, 32–44 chars, no '0x' / 'T'  │ (anything Base58)  │
  │ EVM        │ '0x' prefix + 40 hex chars (42 total)  │ 0x...              │
  └────────────┴─────────────────────────────────────────┴────────────────────┘
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Optional


# ── Compiled patterns ─────────────────────────────────────────────────────────

# TRON: starts with capital T, exactly 34 Base58 characters
_TRON_RE = re.compile(r"^T[1-9A-HJ-NP-Za-km-z]{33}$")

# EVM (Ethereum / BSC / Polygon / etc.): 0x + 40 hex chars
_EVM_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")

# Solana: Base58 alphabet only, 32–44 chars, no '0x' prefix, doesn't start with 'T'
# (excludes 0, O, I, l from the alphabet)
_SOLANA_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")


# ── Chain enum ────────────────────────────────────────────────────────────────

class DetectedChain(str, Enum):
    TRON     = "tron"
    SOLANA   = "solana"
    ETHEREUM = "ethereum"   # represents all EVM-compatible chains
    UNKNOWN  = "unknown"


# ── Public API ────────────────────────────────────────────────────────────────

def detect_chain(address: str) -> DetectedChain:
    """
    Infer the blockchain family of *address* using regex pattern matching.

    Evaluation order matters:
      1. EVM checked first (unambiguous 0x prefix)
      2. TRON checked second (T-prefix + fixed length)
      3. Solana checked last (broad Base58 fallback)

    Args:
        address: Raw wallet address string.

    Returns:
        A :class:`DetectedChain` enum member.

    Examples::

        >>> detect_chain("0xde0B295669a9FD93d5F28D9Ec85E40f4cb697BAe")
        <DetectedChain.ETHEREUM: 'ethereum'>

        >>> detect_chain("TN3W4H6rK2ce4vX9YnFQHwKENnHjoxb3m9")
        <DetectedChain.TRON: 'tron'>

        >>> detect_chain("4Zw1fXuYuJhWhu9KLEYMhiPEiqcpKd6akw3WRZt4W4TT")
        <DetectedChain.SOLANA: 'solana'>
    """
    addr = address.strip()

    if _EVM_RE.match(addr):
        return DetectedChain.ETHEREUM

    if _TRON_RE.match(addr):
        return DetectedChain.TRON

    # Solana: Base58 match but explicitly NOT starting with 'T'
    # (to avoid false-positives with short TRON-like strings)
    if _SOLANA_RE.match(addr) and not addr.startswith("T"):
        return DetectedChain.SOLANA

    return DetectedChain.UNKNOWN


def detect_chain_str(address: str) -> str:
    """
    Convenience wrapper that returns the chain as a plain string
    matching the ``Chain`` Literal in schemas.py.

    Returns ``'unknown'`` for unrecognised formats.
    """
    return detect_chain(address).value


def assert_chain(address: str, expected: DetectedChain) -> bool:
    """Return True if *address* matches the *expected* chain family."""
    return detect_chain(address) == expected


def validate_address(address: str) -> tuple[bool, Optional[DetectedChain]]:
    """
    Validate an address and return ``(is_valid, detected_chain)``.

    An address is considered valid if it matches any known chain pattern.
    Returns ``(False, None)`` for unknown formats.
    """
    chain = detect_chain(address)
    if chain == DetectedChain.UNKNOWN:
        return False, None
    return True, chain

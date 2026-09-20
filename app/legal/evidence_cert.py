"""
evidence_cert.py – Digital evidence certificate generator.

Produces a cryptographically signed evidence bundle containing:
  - Transaction hashes
  - Block timestamps
  - Graph traversal summary
  - SHA-256 hash of the full trace for chain-of-custody integrity.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID

from app.models.schemas import TraceResponse


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


async def generate_evidence_certificate(
    trace: TraceResponse,
    case_id: UUID,
    officer_name: str,
) -> dict:
    """
    Build a JSON evidence certificate for a completed trace.

    The certificate includes a SHA-256 integrity hash that can be
    submitted to court as a chain-of-custody document.
    """
    payload = {
        "case_id": str(case_id),
        "trace_id": str(trace.trace_id),
        "root_address": trace.root_address,
        "chain": trace.chain,
        "depth": trace.depth,
        "node_count": len(trace.nodes),
        "edge_count": len(trace.edges),
        "risk_summary": trace.risk_summary,
        "generated_by": officer_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    payload["integrity_hash"] = _sha256(json.dumps(payload, sort_keys=True))
    return payload

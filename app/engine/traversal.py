"""
traversal.py – Async BFS / DFS graph traversal over Neo4j for address tracing.
"""
from __future__ import annotations

from app.core.database import neo4j_session
from app.models.schemas import TraceEdge, TraceNode


async def bfs_traverse(root_address: str, depth: int = 3) -> tuple[list[TraceNode], list[TraceEdge]]:
    """
    Perform a Breadth-First traversal starting at *root_address* up to *depth* hops.

    Returns:
        nodes: Unique wallet nodes discovered.
        edges: Transaction edges connecting them.
    """
    # TODO: implement Cypher BFS query via neo4j_session
    raise NotImplementedError("BFS traversal not yet implemented")


async def dfs_traverse(root_address: str, depth: int = 3) -> tuple[list[TraceNode], list[TraceEdge]]:
    """
    Perform a Depth-First traversal starting at *root_address* up to *depth* hops.
    """
    # TODO: implement Cypher DFS query via neo4j_session
    raise NotImplementedError("DFS traversal not yet implemented")


async def store_graph(nodes: list[TraceNode], edges: list[TraceEdge]) -> None:
    """Upsert discovered nodes and edges into Neo4j."""
    # TODO: MERGE nodes and edges in batch
    raise NotImplementedError("store_graph not yet implemented")

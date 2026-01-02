"""Network Traversal API router for retrieving subgraphs."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db.neo4j import get_session
from app.models import (
    GraphLink,
    GraphNode,
    NodeLabel,
    SubgraphResponse,
)
from app.models.user import User
from app.auth.dependencies import get_current_active_user
from app.config import get_settings

router = APIRouter(prefix="/network", tags=["network"])


def _process_path_results(records: list[dict]) -> SubgraphResponse:
    """Process path results and extract unique nodes and relationships.

    Args:
        records: List of records containing paths.

    Returns:
        SubgraphResponse with unique nodes and links.
    """
    nodes_dict: dict[str, GraphNode] = {}
    links_dict: dict[str, GraphLink] = {}

    for record in records:
        path = record.get("path")
        if not path:
            continue

        # Process nodes in the path
        for node in path.nodes:
            if node.element_id not in nodes_dict:
                properties = dict(node)
                node_id = properties.pop("node_id", 0)
                labels = list(node.labels)
                label = labels[0] if labels else "Unknown"

                nodes_dict[node.element_id] = GraphNode(
                    id=node.element_id,
                    node_id=node_id,
                    label=label,
                    properties=properties,
                )

        # Process relationships in the path
        for rel in path.relationships:
            if rel.element_id not in links_dict:
                links_dict[rel.element_id] = GraphLink(
                    id=rel.element_id,
                    source=rel.start_node.element_id,
                    target=rel.end_node.element_id,
                    type=rel.type,
                    properties=dict(rel),
                )

    return SubgraphResponse(
        nodes=list(nodes_dict.values()),
        links=list(links_dict.values()),
    )


@router.get(
    "/traverse/{node_id}",
    response_model=SubgraphResponse,
    summary="Traverse network from a starting node",
    description="Retrieve a subgraph starting from a specific node with configurable hop depth.",
)
async def traverse_network(
    node_id: int,
    label: NodeLabel | None = Query(None, description="Label of the starting node"),
    hops: int = Query(1, ge=1, le=5, description="Number of hops to traverse"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum total entities to return"),
) -> SubgraphResponse:
    """Traverse the network starting from a specific node.

    Args:
        node_id: The starting node's node_id property.
        label: Optional label of the starting node.
        hops: Number of relationship hops to traverse (default: 1, max: 5).
        limit: Maximum number of paths to return.

    Returns:
        SubgraphResponse with nodes and links in the traversed subgraph.
    """
    settings = get_settings()

    # Enforce limits
    hops = min(hops, settings.MAX_HOPS)
    limit = min(limit, settings.MAX_LIMIT)

    if label:
        query = f"""
        MATCH path = (start:`{label.value}` {{node_id: $node_id}})-[*1..{hops}]-(connected)
        RETURN path
        LIMIT $limit
        """
    else:
        query = f"""
        MATCH path = (start {{node_id: $node_id}})-[*1..{hops}]-(connected)
        RETURN path
        LIMIT $limit
        """

    async with get_session() as session:
        result = await session.run(query, {"node_id": node_id, "limit": limit})
        records = await result.data()

    if not records:
        # Check if the starting node exists
        check_query = "MATCH (n {node_id: $node_id}) RETURN n LIMIT 1"
        async with get_session() as session:
            check_result = await session.run(check_query, {"node_id": node_id})
            check_records = await check_result.data()

        if not check_records:
            raise HTTPException(status_code=404, detail=f"Node with node_id {node_id} not found")

        # Node exists but has no connections
        node = check_records[0]["n"]
        properties = dict(node)
        node_id_prop = properties.pop("node_id", 0)
        labels = list(node.labels)
        node_label = labels[0] if labels else "Unknown"

        return SubgraphResponse(
            nodes=[
                GraphNode(
                    id=node.element_id,
                    node_id=node_id_prop,
                    label=node_label,
                    properties=properties,
                )
            ],
            links=[],
        )

    return _process_path_results(records)


@router.get(
    "/neighbors/{node_id}",
    response_model=SubgraphResponse,
    summary="Get immediate neighbors of a node",
    description="Retrieve all directly connected nodes (1-hop) for a specific node.",
)
async def get_neighbors(
    node_id: int,
    label: NodeLabel | None = Query(None, description="Label of the starting node"),
    relationship_type: str | None = Query(None, description="Filter by relationship type"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum neighbors to return"),
) -> SubgraphResponse:
    """Get immediate neighbors of a node.

    Args:
        node_id: The node's node_id property.
        label: Optional label of the starting node.
        relationship_type: Optional relationship type filter.
        limit: Maximum number of neighbors to return.

    Returns:
        SubgraphResponse with the starting node and its neighbors.
    """
    if relationship_type:
        if label:
            query = f"""
            MATCH path = (start:`{label.value}` {{node_id: $node_id}})-[r:`{relationship_type}`]-(neighbor)
            RETURN path
            LIMIT $limit
            """
        else:
            query = f"""
            MATCH path = (start {{node_id: $node_id}})-[r:`{relationship_type}`]-(neighbor)
            RETURN path
            LIMIT $limit
            """
    else:
        if label:
            query = f"""
            MATCH path = (start:`{label.value}` {{node_id: $node_id}})-[r]-(neighbor)
            RETURN path
            LIMIT $limit
            """
        else:
            query = """
            MATCH path = (start {node_id: $node_id})-[r]-(neighbor)
            RETURN path
            LIMIT $limit
            """

    async with get_session() as session:
        result = await session.run(query, {"node_id": node_id, "limit": limit})
        records = await result.data()

    if not records:
        raise HTTPException(status_code=404, detail=f"Node with node_id {node_id} not found or has no neighbors")

    return _process_path_results(records)


@router.get(
    "/shortest-path",
    response_model=SubgraphResponse,
    summary="Find shortest path between two nodes",
    description="Find the shortest path between two nodes by their node_ids.",
)
async def find_shortest_path(
    start_node_id: int = Query(..., description="Starting node's node_id"),
    end_node_id: int = Query(..., description="Ending node's node_id"),
    max_hops: int = Query(5, ge=1, le=10, description="Maximum path length"),
) -> SubgraphResponse:
    """Find the shortest path between two nodes.

    Args:
        start_node_id: The starting node's node_id property.
        end_node_id: The ending node's node_id property.
        max_hops: Maximum number of hops to search.

    Returns:
        SubgraphResponse with nodes and links in the shortest path.
    """
    query = f"""
    MATCH path = shortestPath(
        (start {{node_id: $start_node_id}})-[*1..{max_hops}]-(end {{node_id: $end_node_id}})
    )
    RETURN path
    """

    async with get_session() as session:
        result = await session.run(
            query,
            {"start_node_id": start_node_id, "end_node_id": end_node_id}
        )
        records = await result.data()

    if not records:
        raise HTTPException(
            status_code=404,
            detail=f"No path found between nodes {start_node_id} and {end_node_id} within {max_hops} hops"
        )

    return _process_path_results(records)


@router.get(
    "/relationship-types",
    summary="Get available relationship types",
    description="Return all available relationship types in the schema.",
)
async def get_relationship_types() -> dict:
    """Get all available relationship types.

    Returns:
        Dictionary with available relationship types and their descriptions.
    """
    return {
        "relationship_types": [
            {"value": "役員", "description": "Officer relationship"},
            {"value": "仲介", "description": "Intermediary relationship"},
            {"value": "所在地", "description": "Location relationship"},
            {"value": "登録住所", "description": "Registered address relationship"},
            {"value": "同名人物", "description": "Same name person"},
            {"value": "同一人物?", "description": "Possibly same person"},
        ]
    }

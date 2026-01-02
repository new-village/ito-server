"""Network Traversal API router for retrieving subgraphs."""

from fastapi import APIRouter, HTTPException, Query

from app.db.neo4j import get_session
from app.models import (
    GraphLink,
    GraphNode,
    NodeLabel,
    SubgraphResponse,
)
from app.config import get_settings

router = APIRouter(prefix="/network", tags=["network"])


def _process_node(node) -> GraphNode:
    """Process a Neo4j node into a GraphNode.

    Args:
        node: Neo4j node object.

    Returns:
        GraphNode instance.
    """
    properties = dict(node.items())
    node_id = properties.pop("node_id", 0)
    labels = list(node.labels)
    label = labels[0] if labels else "Unknown"

    return GraphNode(
        id=node.element_id,
        node_id=node_id,
        label=label,
        properties=properties,
    )


def _process_relationship(rel) -> GraphLink:
    """Process a Neo4j relationship into a GraphLink.

    Args:
        rel: Neo4j relationship object.

    Returns:
        GraphLink instance.
    """
    return GraphLink(
        id=rel.element_id,
        source=rel.start_node.element_id,
        target=rel.end_node.element_id,
        type=rel.type,
        properties=dict(rel.items()) if hasattr(rel, "items") else {},
    )


async def _process_path_results(session, result) -> SubgraphResponse:
    """Process path results and extract unique nodes and relationships.

    Args:
        session: Neo4j session.
        result: Neo4j result object.

    Returns:
        SubgraphResponse with unique nodes and links.
    """
    nodes_dict: dict[str, GraphNode] = {}
    links_dict: dict[str, GraphLink] = {}

    async for record in result:
        path = record.get("path")
        if not path:
            continue

        # Process nodes in the path
        for node in path.nodes:
            if node.element_id not in nodes_dict:
                nodes_dict[node.element_id] = _process_node(node)

        # Process relationships in the path
        for rel in path.relationships:
            if rel.element_id not in links_dict:
                links_dict[rel.element_id] = _process_relationship(rel)

    return SubgraphResponse(
        nodes=list(nodes_dict.values()),
        links=list(links_dict.values()),
    )


async def _process_neighbor_results(result) -> SubgraphResponse:
    """Process neighbor query results using async iteration.

    Args:
        result: Neo4j result object.

    Returns:
        SubgraphResponse with unique nodes and links.
    """
    nodes_dict: dict[str, GraphNode] = {}
    links_dict: dict[str, GraphLink] = {}

    async for record in result:
        start_node = record.get("start")
        neighbor_node = record.get("neighbor")
        rel = record.get("r")

        if start_node and start_node.element_id not in nodes_dict:
            nodes_dict[start_node.element_id] = _process_node(start_node)

        if neighbor_node and neighbor_node.element_id not in nodes_dict:
            nodes_dict[neighbor_node.element_id] = _process_node(neighbor_node)

        if rel and rel.element_id not in links_dict:
            links_dict[rel.element_id] = _process_relationship(rel)

    return SubgraphResponse(
        nodes=list(nodes_dict.values()),
        links=list(links_dict.values()),
    )


@router.get(
    "/neighbors/{node_id}",
    response_model=SubgraphResponse,
    summary="Get immediate neighbors of a node",
    description="Retrieve all directly connected nodes (1-hop) for a specific node. "
    "Optionally filter neighbors by their label.",
)
async def get_neighbors(
    node_id: int,
    label: NodeLabel | None = Query(None, description="Filter neighbors by this label"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum neighbors to return"),
) -> SubgraphResponse:
    """Get immediate neighbors of a node.

    Args:
        node_id: The node's node_id property.
        label: Optional label to filter neighbors (not the starting node).
        limit: Maximum number of neighbors to return.

    Returns:
        SubgraphResponse with the starting node and its neighbors.
    """
    settings = get_settings()
    limit = min(limit, settings.MAX_LIMIT)

    if label:
        # Filter neighbors by label
        query = f"""
        MATCH (start {{node_id: $node_id}})-[r]-(neighbor:`{label.value}`)
        RETURN start, r, neighbor
        LIMIT $limit
        """
    else:
        # Get all neighbors regardless of label
        query = """
        MATCH (start {node_id: $node_id})-[r]-(neighbor)
        RETURN start, r, neighbor
        LIMIT $limit
        """

    async with get_session() as session:
        result = await session.run(query, {"node_id": node_id, "limit": limit})
        response = await _process_neighbor_results(result)

    if not response.nodes:
        # Check if the starting node exists
        check_query = "MATCH (n {node_id: $node_id}) RETURN n LIMIT 1"
        async with get_session() as session:
            check_result = await session.run(check_query, {"node_id": node_id})
            check_node = None
            async for record in check_result:
                check_node = record.get("n")
                break

        if not check_node:
            raise HTTPException(
                status_code=404,
                detail=f"Node with node_id {node_id} not found"
            )

        # Node exists but has no neighbors (or no neighbors with the specified label)
        if label:
            raise HTTPException(
                status_code=404,
                detail=f"Node {node_id} has no neighbors with label '{label.value}'"
            )

        # Return just the starting node with no links
        return SubgraphResponse(
            nodes=[_process_node(check_node)],
            links=[],
        )

    return response


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
        response = await _process_path_results(session, result)

    if not response.nodes:
        raise HTTPException(
            status_code=404,
            detail=f"No path found between nodes {start_node_id} and {end_node_id} within {max_hops} hops"
        )

    return response


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

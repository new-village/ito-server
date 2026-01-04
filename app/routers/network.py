"""Network Traversal API router for retrieving subgraphs."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db.neo4j import get_session
from app.models import (
    GraphLink,
    GraphNode,
    NodeLabel,
    RelationshipsResponse,
    SubgraphResponse,
)
from app.models.user import User
from app.auth.dependencies import get_current_active_user
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

        if start_node is not None and start_node.element_id not in nodes_dict:
            nodes_dict[start_node.element_id] = _process_node(start_node)

        if neighbor_node is not None and neighbor_node.element_id not in nodes_dict:
            nodes_dict[neighbor_node.element_id] = _process_node(neighbor_node)

        # Neo4j Node/Relationship objects can be "falsy" when they have no properties.
        # Avoid truthiness checks; explicitly test for None.
        if rel is not None and rel.element_id not in links_dict:
            links_dict[rel.element_id] = _process_relationship(rel)

    return SubgraphResponse(
        nodes=list(nodes_dict.values()),
        links=list(links_dict.values()),
    )


async def _process_relationships_results(result) -> RelationshipsResponse:
    """Process relationships query results using async iteration.

    Args:
        result: Neo4j result object.

    Returns:
        RelationshipsResponse with unique relationships.
    """
    links_dict: dict[str, GraphLink] = {}

    async for record in result:
        rel = record.get("r")

        # Neo4j Relationship objects can be "falsy" when they have no properties.
        # Avoid truthiness checks; explicitly test for None.
        if rel is not None and rel.element_id not in links_dict:
            links_dict[rel.element_id] = _process_relationship(rel)

    return RelationshipsResponse(
        relationships=list(links_dict.values()),
    )


@router.get(
    "/neighbors/{node_id}",
    response_model=SubgraphResponse,
    summary="Get immediate neighbors of a node",
    description="Retrieve all directly connected nodes (1-hop) for a specific node. "
    "Optionally filter neighbors by their label. Requires authentication.",
)
async def get_neighbors(
    node_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
    label: NodeLabel | None = Query(None, description="Filter neighbors by this label"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum neighbors to return"),
) -> SubgraphResponse:
    """Get immediate neighbors of a node.

    Args:
        node_id: The node's node_id property.
        current_user: The authenticated user (injected by dependency).
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
            # Node not found - return empty result with 200
            return SubgraphResponse(nodes=[], links=[])

        # Node exists but has no neighbors (or no neighbors with the specified label)
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
    description="Find the shortest path between two nodes by their node_ids. Requires authentication.",
)
async def find_shortest_path(
    current_user: Annotated[User, Depends(get_current_active_user)],
    start_node_id: int = Query(..., description="Starting node's node_id"),
    end_node_id: int = Query(..., description="Ending node's node_id"),
    max_hops: int = Query(4, ge=1, le=10, description="Maximum path length (default: 4)"),
) -> SubgraphResponse:
    """Find the shortest path between two nodes.

    Args:
        current_user: The authenticated user (injected by dependency).
        start_node_id: The starting node's node_id property.
        end_node_id: The ending node's node_id property.
        max_hops: Maximum number of hops to search (default: 4).

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

    # Return empty result with 200 if no path found
    return response


@router.get(
    "/relationships/{node_id}",
    response_model=RelationshipsResponse,
    summary="Get relationships of a node",
    description="Retrieve all relationships connected to a specific node. "
    "Optionally filter by relationship type. Requires authentication.",
)
async def get_relationships(
    node_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
    rel_type: str | None = Query(None, description="Filter relationships by type"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum relationships to return"),
) -> RelationshipsResponse:
    """Get relationships of a node.

    Args:
        node_id: The node's node_id property.
        current_user: The authenticated user (injected by dependency).
        rel_type: Optional relationship type to filter.
        limit: Maximum number of relationships to return.

    Returns:
        RelationshipsResponse with the relationships connected to the node.
    """
    settings = get_settings()
    limit = min(limit, settings.MAX_LIMIT)

    if rel_type:
        # Filter relationships by type
        query = f"""
        MATCH (n {{node_id: $node_id}})-[r:`{rel_type}`]-()
        RETURN r
        LIMIT $limit
        """
    else:
        # Get all relationships regardless of type
        query = """
        MATCH (n {node_id: $node_id})-[r]-()
        RETURN r
        LIMIT $limit
        """

    async with get_session() as session:
        result = await session.run(query, {"node_id": node_id, "limit": limit})
        response = await _process_relationships_results(result)

    return response


@router.get(
    "/relationship-types",
    summary="Get available relationship types",
    description="Return all available relationship types in the schema. Requires authentication.",
)
async def get_relationship_types(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> dict:
    """Get all available relationship types.

    Args:
        current_user: The authenticated user (injected by dependency).

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

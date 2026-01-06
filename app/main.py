"""Main FastAPI application for ITO Server.

Network Investigation Backend API connecting to Neo4j Aura.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from app.config import get_settings
from app.db.neo4j import Neo4jConnection
from app.db.session import init_db, init_flag_db, get_engine, FLAG_DATABASE_PATH
from app.models import HealthResponse
from app.models.user import User
from app.auth.security import get_password_hash
from app.routers import search, network, cypher, flag
from app.api.auth import router as auth_router


def bootstrap_admin_user() -> None:
    """Create the first admin user if no users exist.

    Uses FIRST_ADMIN_USER and FIRST_ADMIN_PASSWORD from environment variables.
    """
    settings = get_settings()
    engine = get_engine()

    with Session(engine) as session:
        # Check if any users exist
        statement = select(User)
        existing_user = session.exec(statement).first()

        if existing_user is None:
            # Create the first admin user
            admin_user = User(
                username=settings.FIRST_ADMIN_USER,
                hashed_password=get_password_hash(
                    settings.FIRST_ADMIN_PASSWORD.get_secret_value()
                ),
                is_active=True,
                is_admin=True,
            )
            session.add(admin_user)
            session.commit()
            print(f"✅ Created initial admin user: {settings.FIRST_ADMIN_USER}")
        else:
            print(f"ℹ️ Users already exist, skipping admin bootstrap")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Manage application lifespan events.

    Handles database initialization, admin user bootstrap,
    Neo4j driver initialization and cleanup.
    """
    settings = get_settings()
    print(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    # Initialize SQLite database and create tables
    print("Initializing SQLite database...")
    init_db()
    print(f"✅ SQLite database ready at {settings.DATABASE_PATH}")

    # Initialize Flag database
    print("Initializing Flag database...")
    init_flag_db()
    print(f"✅ Flag database ready at {FLAG_DATABASE_PATH}")

    # Bootstrap admin user if needed
    bootstrap_admin_user()

    # Initialize Neo4j connection
    print(f"Connecting to Neo4j at {settings.NEO4J_URL}")
    try:
        connected = await Neo4jConnection.verify_connectivity()
        if connected:
            print("✅ Successfully connected to Neo4j")
        else:
            print("⚠️ Could not verify Neo4j connection")
    except Exception as e:
        print(f"❌ Neo4j connection error: {e}")

    yield

    # Shutdown: Close Neo4j connection
    print("Shutting down, closing Neo4j connection...")
    await Neo4jConnection.close()
    print("✅ Neo4j connection closed")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        description="""
# ITO Server - Network Investigation Backend API

A FastAPI-based REST API that connects to Neo4j Aura and serves as a backend
for a network investigation web application.

## Features

- **Authentication**: OAuth2 password flow with JWT tokens
- **Search API**: Find specific nodes by properties (node_id, name, etc.)
- **Network Traversal API**: Retrieve subgraphs with configurable hop depth
- **Cypher API**: Execute arbitrary Cypher queries

## Node Labels

- `officer`: Officers and shareholders
- `entity`: Corporate entities
- `intermediary`: Intermediaries
- `address`: Addresses

## Authentication

Most endpoints require authentication. Use the `/api/v1/auth/login` endpoint
to obtain a JWT token, then include it in the `Authorization` header:

```
Authorization: Bearer <your_token>
```
        """,
        version=settings.APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.CORS_ALLOW_METHODS,
        allow_headers=settings.CORS_ALLOW_HEADERS,
    )

    # Include routers
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(search.router, prefix="/api/v1")
    app.include_router(network.router, prefix="/api/v1")
    app.include_router(cypher.router, prefix="/api/v1")
    app.include_router(flag.router, prefix="/api/v1")

    return app


# Create the application instance
app = create_app()


@app.get("/", tags=["root"])
async def root() -> dict:
    """Root endpoint returning API information."""
    settings = get_settings()
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "redoc": "/redoc",
        "openapi": "/openapi.json",
    }


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check() -> HealthResponse:
    """Health check endpoint for monitoring and load balancers."""
    settings = get_settings()

    try:
        db_connected = await Neo4jConnection.verify_connectivity()
        db_status = "connected" if db_connected else "disconnected"
    except Exception:
        db_status = "error"

    return HealthResponse(
        status="healthy" if db_status == "connected" else "degraded",
        database=db_status,
        version=settings.APP_VERSION,
    )


@app.get("/ready", tags=["health"])
async def readiness_check() -> dict:
    """Readiness check for Kubernetes/Cloud Run."""
    try:
        connected = await Neo4jConnection.verify_connectivity()
        if connected:
            return {"status": "ready"}
        else:
            return {"status": "not ready", "reason": "database disconnected"}
    except Exception as e:
        return {"status": "not ready", "reason": str(e)}


@app.get("/live", tags=["health"])
async def liveness_check() -> dict:
    """Liveness check for Kubernetes/Cloud Run."""
    return {"status": "alive"}

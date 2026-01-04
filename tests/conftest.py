"""Pytest configuration and fixtures for ITO Server tests."""

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import Session, SQLModel, create_engine

# Set test environment variables before importing app
os.environ["NEO4J_URL"] = "neo4j://localhost:7687"
os.environ["NEO4J_USERNAME"] = "neo4j"
os.environ["NEO4J_PASSWORD"] = "testpassword"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only-minimum-32-chars"
os.environ["DATABASE_PATH"] = "./test_auth.db"
os.environ["FIRST_ADMIN_USER"] = "testadmin"
os.environ["FIRST_ADMIN_PASSWORD"] = "testadminpassword"


@pytest.fixture(scope="function")
def test_db_session():
    """Create a test database session with fresh tables for each test."""
    from app.models.user import User, RefreshToken
    from app.auth.security import get_password_hash

    # Use in-memory SQLite for tests
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        yield session

    # Cleanup
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def test_user(test_db_session):
    """Create a test user in the database."""
    from app.models.user import User
    from app.auth.security import get_password_hash

    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=get_password_hash("testpassword123"),
        is_active=True,
        is_admin=False,
    )
    test_db_session.add(user)
    test_db_session.commit()
    test_db_session.refresh(user)
    return user


@pytest.fixture
async def test_client_with_db(mock_neo4j_driver, test_db_session) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with real SQLite database (in-memory)."""
    from app.db.session import get_db_session

    def override_get_db_session():
        yield test_db_session

    with patch("app.db.neo4j.AsyncGraphDatabase.driver", return_value=mock_neo4j_driver):
        with patch("app.db.neo4j.Neo4jConnection._driver", mock_neo4j_driver):
            with patch("app.main.init_db"):
                with patch("app.main.bootstrap_admin_user"):
                    from app.main import app

                    app.dependency_overrides[get_db_session] = override_get_db_session

                    async with AsyncClient(
                        transport=ASGITransport(app=app),
                        base_url="http://test"
                    ) as client:
                        yield client

                    app.dependency_overrides.clear()


@pytest.fixture
def mock_neo4j_driver():
    """Create a mock Neo4j driver."""
    mock_driver = MagicMock()
    mock_driver.verify_connectivity = AsyncMock(return_value=True)
    mock_driver.close = AsyncMock()
    return mock_driver


@pytest.fixture
def mock_neo4j_session():
    """Create a mock Neo4j session."""
    mock_session = MagicMock()
    mock_session.close = AsyncMock()
    return mock_session


@pytest.fixture
def mock_neo4j_node():
    """Create a mock Neo4j node."""
    mock_node = MagicMock()
    mock_node.element_id = "4:test:123"
    mock_node.labels = frozenset(["entity"])
    mock_node.__iter__ = lambda self: iter({"node_id": 12345, "name": "Test Company"}.items())

    def mock_items():
        return {"node_id": 12345, "name": "Test Company"}.items()

    mock_node.items = mock_items
    return mock_node


@pytest.fixture
def mock_authenticated_user():
    """Create a mock authenticated user for testing."""
    from datetime import UTC

    from app.models.user import User

    mock_user = MagicMock(spec=User)
    mock_user.id = 1
    mock_user.username = "testuser"
    mock_user.email = "test@example.com"
    mock_user.is_active = True
    mock_user.is_admin = False
    mock_user.created_at = datetime.now(UTC)
    mock_user.updated_at = datetime.now(UTC)
    return mock_user


@pytest.fixture
async def test_client(mock_neo4j_driver, test_db_session) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with mocked Neo4j connection and real SQLite."""
    from app.db.session import get_db_session

    def override_get_db_session():
        yield test_db_session

    with patch("app.db.neo4j.AsyncGraphDatabase.driver", return_value=mock_neo4j_driver):
        with patch("app.db.neo4j.Neo4jConnection._driver", mock_neo4j_driver):
            # Mock SQLite init to avoid creating test database
            with patch("app.main.init_db"):
                with patch("app.main.bootstrap_admin_user"):
                    from app.main import app

                    app.dependency_overrides[get_db_session] = override_get_db_session

                    async with AsyncClient(
                        transport=ASGITransport(app=app),
                        base_url="http://test"
                    ) as client:
                        yield client

                    app.dependency_overrides.clear()


@pytest.fixture
async def authenticated_test_client(mock_neo4j_driver, mock_authenticated_user, test_db_session) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with authentication mocked."""
    from app.db.session import get_db_session

    def override_get_db_session():
        yield test_db_session

    with patch("app.db.neo4j.AsyncGraphDatabase.driver", return_value=mock_neo4j_driver):
        with patch("app.db.neo4j.Neo4jConnection._driver", mock_neo4j_driver):
            with patch("app.main.init_db"):
                with patch("app.main.bootstrap_admin_user"):
                    from app.main import app
                    from app.auth.dependencies import get_current_active_user

                    # Override authentication dependency
                    async def mock_get_current_active_user():
                        return mock_authenticated_user

                    app.dependency_overrides[get_current_active_user] = mock_get_current_active_user
                    app.dependency_overrides[get_db_session] = override_get_db_session

                    async with AsyncClient(
                        transport=ASGITransport(app=app),
                        base_url="http://test"
                    ) as client:
                        yield client

                    # Clean up override
                    app.dependency_overrides.clear()


@pytest.fixture
def sample_officer_node():
    """Sample officer node data."""
    return {
        "node_id": 10000001,
        "name": "John Doe",
        "countries": "United States",
        "country_codes": "USA",
        "sourceID": "Panama Papers",
        "valid_until": "2020-12-31",
        "note": "",
    }


@pytest.fixture
def sample_entity_node():
    """Sample entity node data."""
    return {
        "node_id": 20000001,
        "name": "Test Corporation Ltd",
        "original_name": "Test Corporation Limited",
        "former_name": "",
        "jurisdiction": "BVI",
        "jurisdiction_description": "British Virgin Islands",
        "company_type": "Standard International Company",
        "address": "123 Main Street, Road Town",
        "internal_id": 12345,
        "incorporation_date": "2010-01-15",
        "inactivation_date": "",
        "struck_off_date": "",
        "dorm_date": "",
        "status": "Active",
        "service_provider": "Mossack Fonseca",
        "ibcRUC": "",
        "country_codes": "VGB",
        "countries": "British Virgin Islands",
        "sourceID": "Panama Papers",
        "valid_until": "The Panama Papers data is current through 2015",
        "note": "",
    }


@pytest.fixture
def sample_subgraph_response():
    """Sample subgraph response data."""
    return {
        "nodes": [
            {
                "id": "4:test:1",
                "node_id": 10000001,
                "label": "役員/株主",
                "properties": {"name": "John Doe", "countries": "USA"},
            },
            {
                "id": "4:test:2",
                "node_id": 20000001,
                "label": "法人",
                "properties": {"name": "Test Corp", "status": "Active"},
            },
        ],
        "links": [
            {
                "id": "5:test:1",
                "source": "4:test:1",
                "target": "4:test:2",
                "type": "役員",
                "properties": {"rel_type": "director"},
            },
        ],
    }

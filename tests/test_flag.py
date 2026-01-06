"""Tests for Flag API endpoints."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import Session, SQLModel, create_engine

from app.models.flag import Flag


@pytest.fixture
def flag_db_session():
    """Create a test database session with fresh flag tables for each test."""
    # Use in-memory SQLite for tests
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    # Create only the Flag table
    Flag.metadata.create_all(engine)

    with Session(engine) as session:
        yield session

    # Cleanup
    Flag.metadata.drop_all(engine)


@pytest.fixture
def sample_flag(flag_db_session):
    """Create a sample flag in the test database."""
    flag = Flag(
        flag_id="202601060001",
        subject_id="12129942",
        rule_id="RULE-001",
        score=10,
        parameter="JPN",
        create_date=datetime(2026, 1, 1, 12, 13, 52, tzinfo=timezone.utc),
        create_by="SYSTEM",
    )
    flag_db_session.add(flag)
    flag_db_session.commit()
    flag_db_session.refresh(flag)
    return flag


@pytest.fixture
def sample_flags_same_flag_id(flag_db_session):
    """Create sample flags with the same flag_id."""
    flags = [
        Flag(
            flag_id="202601060002",
            subject_id="12129942",
            rule_id="RULE-002",
            score=10,
            parameter="10000",
            create_date=datetime(2026, 1, 1, 12, 13, 52, tzinfo=timezone.utc),
            create_by="ADMIN",
        ),
        Flag(
            flag_id="202601060002",
            subject_id="240070570",
            rule_id="RULE-002",
            score=10,
            parameter="10000",
            create_date=datetime(2026, 1, 1, 12, 13, 52, tzinfo=timezone.utc),
            create_by="ADMIN",
        ),
    ]
    for flag in flags:
        flag_db_session.add(flag)
    flag_db_session.commit()
    for flag in flags:
        flag_db_session.refresh(flag)
    return flags


class TestGetFlagsBySubject:
    """Tests for GET /api/v1/flag/{subject_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_flags_by_subject_returns_related_flags(
        self, mock_neo4j_driver, mock_authenticated_user, flag_db_session, sample_flags_same_flag_id
    ):
        """Test that getting flags returns all related flags with same flag_id."""
        from app.routers.flag import _get_flag_db

        def override_get_flag_db():
            yield flag_db_session

        with patch("app.db.neo4j.AsyncGraphDatabase.driver", return_value=mock_neo4j_driver):
            with patch("app.db.neo4j.Neo4jConnection._driver", mock_neo4j_driver):
                with patch("app.main.init_db"):
                    with patch("app.main.init_flag_db"):
                        with patch("app.main.bootstrap_admin_user"):
                            from app.main import app
                            from app.auth.dependencies import get_current_active_user

                            async def mock_get_current_active_user():
                                return mock_authenticated_user

                            app.dependency_overrides[get_current_active_user] = mock_get_current_active_user
                            app.dependency_overrides[_get_flag_db] = override_get_flag_db

                            async with AsyncClient(
                                transport=ASGITransport(app=app),
                                base_url="http://test"
                            ) as client:
                                response = await client.get("/api/v1/flag/12129942")

                            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["flags"]) == 1
        flag = data["flags"][0]
        assert flag["flag_id"] == "202601060002"
        assert flag["rule_id"] == "RULE-002"
        assert flag["score"] == 10
        assert set(flag["subject_ids"]) == {"12129942", "240070570"}

    @pytest.mark.asyncio
    async def test_get_flags_by_subject_returns_empty_when_not_found(
        self, mock_neo4j_driver, mock_authenticated_user, flag_db_session
    ):
        """Test that getting flags returns empty list when subject not found."""
        from app.routers.flag import _get_flag_db

        def override_get_flag_db():
            yield flag_db_session

        with patch("app.db.neo4j.AsyncGraphDatabase.driver", return_value=mock_neo4j_driver):
            with patch("app.db.neo4j.Neo4jConnection._driver", mock_neo4j_driver):
                with patch("app.main.init_db"):
                    with patch("app.main.init_flag_db"):
                        with patch("app.main.bootstrap_admin_user"):
                            from app.main import app
                            from app.auth.dependencies import get_current_active_user

                            async def mock_get_current_active_user():
                                return mock_authenticated_user

                            app.dependency_overrides[get_current_active_user] = mock_get_current_active_user
                            app.dependency_overrides[_get_flag_db] = override_get_flag_db

                            async with AsyncClient(
                                transport=ASGITransport(app=app),
                                base_url="http://test"
                            ) as client:
                                response = await client.get("/api/v1/flag/nonexistent")

                            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["flags"] == []

    @pytest.mark.asyncio
    async def test_get_flags_requires_authentication(
        self, mock_neo4j_driver, flag_db_session
    ):
        """Test that getting flags requires authentication."""
        from app.routers.flag import _get_flag_db

        def override_get_flag_db():
            yield flag_db_session

        with patch("app.db.neo4j.AsyncGraphDatabase.driver", return_value=mock_neo4j_driver):
            with patch("app.db.neo4j.Neo4jConnection._driver", mock_neo4j_driver):
                with patch("app.main.init_db"):
                    with patch("app.main.init_flag_db"):
                        with patch("app.main.bootstrap_admin_user"):
                            from app.main import app

                            app.dependency_overrides[_get_flag_db] = override_get_flag_db

                            async with AsyncClient(
                                transport=ASGITransport(app=app),
                                base_url="http://test"
                            ) as client:
                                response = await client.get("/api/v1/flag/12129942")

                            app.dependency_overrides.clear()

        assert response.status_code == 401


class TestCreateFlag:
    """Tests for POST /api/v1/flag endpoint."""

    @pytest.mark.asyncio
    async def test_create_flag_success(
        self, mock_neo4j_driver, mock_authenticated_user, flag_db_session
    ):
        """Test successful flag creation with multiple subject_ids."""
        from app.routers.flag import _get_flag_db

        def override_get_flag_db():
            yield flag_db_session

        flag_data = {
            "flag_id": "202601060003",
            "subject_ids": ["11111111", "22222222"],
            "rule_id": "RULE-003",
            "score": 15,
            "parameter": "USD",
            "create_date": "2026-01-06T10:00:00Z",
            "create_by": "TEST",
        }

        with patch("app.db.neo4j.AsyncGraphDatabase.driver", return_value=mock_neo4j_driver):
            with patch("app.db.neo4j.Neo4jConnection._driver", mock_neo4j_driver):
                with patch("app.main.init_db"):
                    with patch("app.main.init_flag_db"):
                        with patch("app.main.bootstrap_admin_user"):
                            from app.main import app
                            from app.auth.dependencies import get_current_active_user

                            async def mock_get_current_active_user():
                                return mock_authenticated_user

                            app.dependency_overrides[get_current_active_user] = mock_get_current_active_user
                            app.dependency_overrides[_get_flag_db] = override_get_flag_db

                            async with AsyncClient(
                                transport=ASGITransport(app=app),
                                base_url="http://test"
                            ) as client:
                                response = await client.post("/api/v1/flag", json=flag_data)

                            app.dependency_overrides.clear()

        assert response.status_code == 201
        data = response.json()
        assert data["flag_id"] == "202601060003"
        assert data["rule_id"] == "RULE-003"
        assert data["score"] == 15
        assert set(data["subject_ids"]) == {"11111111", "22222222"}

    @pytest.mark.asyncio
    async def test_create_flag_duplicate_flag_id(
        self, mock_neo4j_driver, mock_authenticated_user, flag_db_session, sample_flag
    ):
        """Test that creating a flag with existing flag_id returns 409."""
        from app.routers.flag import _get_flag_db

        def override_get_flag_db():
            yield flag_db_session

        flag_data = {
            "flag_id": "202601060001",  # Same as sample_flag
            "subject_ids": ["99999999"],
            "rule_id": "RULE-001",
            "score": 10,
            "parameter": "JPN",
            "create_date": "2026-01-06T10:00:00Z",
            "create_by": "TEST",
        }

        with patch("app.db.neo4j.AsyncGraphDatabase.driver", return_value=mock_neo4j_driver):
            with patch("app.db.neo4j.Neo4jConnection._driver", mock_neo4j_driver):
                with patch("app.main.init_db"):
                    with patch("app.main.init_flag_db"):
                        with patch("app.main.bootstrap_admin_user"):
                            from app.main import app
                            from app.auth.dependencies import get_current_active_user

                            async def mock_get_current_active_user():
                                return mock_authenticated_user

                            app.dependency_overrides[get_current_active_user] = mock_get_current_active_user
                            app.dependency_overrides[_get_flag_db] = override_get_flag_db

                            async with AsyncClient(
                                transport=ASGITransport(app=app),
                                base_url="http://test"
                            ) as client:
                                response = await client.post("/api/v1/flag", json=flag_data)

                            app.dependency_overrides.clear()

        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_create_flag_requires_authentication(
        self, mock_neo4j_driver, flag_db_session
    ):
        """Test that creating a flag requires authentication."""
        from app.routers.flag import _get_flag_db

        def override_get_flag_db():
            yield flag_db_session

        flag_data = {
            "flag_id": "202601060003",
            "subject_ids": ["11111111"],
            "rule_id": "RULE-003",
            "score": 15,
            "parameter": "USD",
            "create_date": "2026-01-06T10:00:00Z",
            "create_by": "TEST",
        }

        with patch("app.db.neo4j.AsyncGraphDatabase.driver", return_value=mock_neo4j_driver):
            with patch("app.db.neo4j.Neo4jConnection._driver", mock_neo4j_driver):
                with patch("app.main.init_db"):
                    with patch("app.main.init_flag_db"):
                        with patch("app.main.bootstrap_admin_user"):
                            from app.main import app

                            app.dependency_overrides[_get_flag_db] = override_get_flag_db

                            async with AsyncClient(
                                transport=ASGITransport(app=app),
                                base_url="http://test"
                            ) as client:
                                response = await client.post("/api/v1/flag", json=flag_data)

                            app.dependency_overrides.clear()

        assert response.status_code == 401


class TestDeleteFlag:
    """Tests for DELETE /api/v1/flag/{flag_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_flag_success(
        self, mock_neo4j_driver, mock_authenticated_user, flag_db_session, sample_flags_same_flag_id
    ):
        """Test successful flag deletion."""
        from app.routers.flag import _get_flag_db

        def override_get_flag_db():
            yield flag_db_session

        with patch("app.db.neo4j.AsyncGraphDatabase.driver", return_value=mock_neo4j_driver):
            with patch("app.db.neo4j.Neo4jConnection._driver", mock_neo4j_driver):
                with patch("app.main.init_db"):
                    with patch("app.main.init_flag_db"):
                        with patch("app.main.bootstrap_admin_user"):
                            from app.main import app
                            from app.auth.dependencies import get_current_active_user

                            async def mock_get_current_active_user():
                                return mock_authenticated_user

                            app.dependency_overrides[get_current_active_user] = mock_get_current_active_user
                            app.dependency_overrides[_get_flag_db] = override_get_flag_db

                            async with AsyncClient(
                                transport=ASGITransport(app=app),
                                base_url="http://test"
                            ) as client:
                                response = await client.delete("/api/v1/flag/202601060002")

                            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["flag_id"] == "202601060002"
        assert data["deleted_count"] == 2

    @pytest.mark.asyncio
    async def test_delete_flag_not_found(
        self, mock_neo4j_driver, mock_authenticated_user, flag_db_session
    ):
        """Test that deleting a non-existent flag returns 404."""
        from app.routers.flag import _get_flag_db

        def override_get_flag_db():
            yield flag_db_session

        with patch("app.db.neo4j.AsyncGraphDatabase.driver", return_value=mock_neo4j_driver):
            with patch("app.db.neo4j.Neo4jConnection._driver", mock_neo4j_driver):
                with patch("app.main.init_db"):
                    with patch("app.main.init_flag_db"):
                        with patch("app.main.bootstrap_admin_user"):
                            from app.main import app
                            from app.auth.dependencies import get_current_active_user

                            async def mock_get_current_active_user():
                                return mock_authenticated_user

                            app.dependency_overrides[get_current_active_user] = mock_get_current_active_user
                            app.dependency_overrides[_get_flag_db] = override_get_flag_db

                            async with AsyncClient(
                                transport=ASGITransport(app=app),
                                base_url="http://test"
                            ) as client:
                                response = await client.delete("/api/v1/flag/nonexistent")

                            app.dependency_overrides.clear()

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_flag_requires_authentication(
        self, mock_neo4j_driver, flag_db_session
    ):
        """Test that deleting a flag requires authentication."""
        from app.routers.flag import _get_flag_db

        def override_get_flag_db():
            yield flag_db_session

        with patch("app.db.neo4j.AsyncGraphDatabase.driver", return_value=mock_neo4j_driver):
            with patch("app.db.neo4j.Neo4jConnection._driver", mock_neo4j_driver):
                with patch("app.main.init_db"):
                    with patch("app.main.init_flag_db"):
                        with patch("app.main.bootstrap_admin_user"):
                            from app.main import app

                            app.dependency_overrides[_get_flag_db] = override_get_flag_db

                            async with AsyncClient(
                                transport=ASGITransport(app=app),
                                base_url="http://test"
                            ) as client:
                                response = await client.delete("/api/v1/flag/202601060001")

                            app.dependency_overrides.clear()

        assert response.status_code == 401

# AMI Server

A FastAPI-based REST API backend for network investigation, connecting to Neo4j Aura database. Designed for deployment on Google Cloud Run.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Cloud Run                                │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                      AMI Server                            │  │
│  │  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐  │  │
│  │  │ Search  │  │ Network  │  │ Cypher🔒 │  │  Health   │  │  │
│  │  │   API   │  │   API    │  │   API    │  │   Check   │  │  │
│  │  └────┬────┘  └────┬─────┘  └────┬─────┘  └───────────┘  │  │
│  │       │            │             │                        │  │
│  │       └────────────┼─────────────┘                        │  │
│  │                    │                                      │  │
│  │  ┌────────────┐   │   ┌──────────────┐                   │  │
│  │  │ Auth API   │   │   │   SQLite     │                   │  │
│  │  │ (JWT/OAuth)│───┼───│  (Users DB)  │                   │  │
│  │  └────────────┘   │   └──────────────┘                   │  │
│  │                    │        │ Cloud Storage Mount         │  │
│  │             ┌──────┴──────┐ │                             │  │
│  │             │  Neo4j      │ │                             │  │
│  │             │  Driver     │ │                             │  │
│  │             │  (Async)    │ │                             │  │
│  │             └──────┬──────┘ │                             │  │
│  └────────────────────┼────────┼─────────────────────────────┘  │
└───────────────────────┼────────┼────────────────────────────────┘
                        │        │
                        ▼        ▼
              ┌─────────────────┐  ┌─────────────────┐
              │   Neo4j Aura    │  │ Cloud Storage   │
              │    Database     │  │  /data/ami.db   │
              └─────────────────┘  └─────────────────┘
```

🔒 = Requires authentication

## ✨ Features

### Core APIs

1. **Search Node API** (`/api/v1/search/`) 🔒
   - Find nodes by `node_id`
   - Search by name (partial match)
   - Pagination with `limit` and `offset`
   - Filter by node label

2. **Network API** (`/api/v1/network/`) 🔒
   - Get immediate neighbors of a node
   - Filter neighbors by label
   - Find shortest path between nodes

3. **Async Cypher API** (`/api/v1/cypher/`) 🔒
   - Execute arbitrary Cypher queries (requires authentication)
   - Get database schema
   - Get database statistics

4. **Authentication API** (`/api/v1/auth/`)
   - OAuth2 Password Flow with JWT tokens
   - User login and token generation
   - User logout (token invalidation)
   - User profile retrieval
   - SQLite-based user storage

### Graph Schema

**Node Labels:**
- `officer`: Officers and shareholders
- `entity`: Corporate entities
- `intermediary`: Intermediaries
- `address`: Addresses

**Relationship Types:**
- `役員`: Officer relationship
- `仲介`: Intermediary relationship
- `所在地`: Location relationship
- `登録住所`: Registered address relationship
- `同名人物`: Same name person
- `同一人物?`: Possibly same person

### Response Format

Subgraph results follow a structured JSON schema for easy integration with visualization libraries:

```json
{
  "nodes": [
    {
      "id": "4:abc:123",
      "node_id": 12345,
      "label": "法人",
      "properties": {
        "name": "Company Name",
        "status": "Active"
      }
    }
  ],
  "links": [
    {
      "id": "5:abc:456",
      "source": "4:abc:123",
      "target": "4:abc:789",
      "type": "役員",
      "properties": {}
    }
  ]
}
```

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- Neo4j Aura database instance

### Local Development

1. **Clone the repository**
   ```bash
   git clone https://github.com/new-village/ami-server.git
   cd ami-server
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/macOS
   # or
   .venv\Scripts\activate  # Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements-dev.txt
   ```

4. **Configure environment variables**
   
   Create a `.env` file:
   ```env
   # Neo4j Connection
   NEO4J_URL=neo4j+s://your-instance.databases.neo4j.io
   NEO4J_USERNAME=neo4j
   NEO4J_PASSWORD=your-password
   
   # Authentication
   SECRET_KEY=your-secret-key-change-in-production
   DATABASE_PATH=./ami.db
   FIRST_ADMIN_USER=admin
   FIRST_ADMIN_PASSWORD=your-admin-password
   ```

5. **Run the server**
   ```bash
   uvicorn app.main:app --reload --port 8080
   ```

6. **Access the API**
   - Swagger UI: http://localhost:8080/docs
   - ReDoc: http://localhost:8080/redoc
   - OpenAPI JSON: http://localhost:8080/openapi.json

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_search.py -v
```

## 🐳 Docker

### Build Image

```bash
docker build -t ami-server .
```

### Run Container

```bash
docker run -p 8080:8080 \
  -e NEO4J_URL=neo4j+s://your-instance.databases.neo4j.io \
  -e NEO4J_USERNAME=neo4j \
  -e NEO4J_PASSWORD=your-password \
  ami-server
```

## ☁️ Google Cloud Run Deployment

### Using gcloud CLI

1. **Build and push to Container Registry**
   ```bash
   gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/ami-server
   ```

2. **Deploy to Cloud Run**
   ```bash
   gcloud run deploy ami-server \
     --image gcr.io/YOUR_PROJECT_ID/ami-server \
     --platform managed \
     --region asia-northeast1 \
     --allow-unauthenticated \
     --set-secrets=NEO4J_URL=neo4j-url:latest,NEO4J_USERNAME=neo4j-username:latest,NEO4J_PASSWORD=neo4j-password:latest
   ```

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `NEO4J_URL` | Neo4j connection URL | Yes |
| `NEO4J_USERNAME` | Neo4j username | Yes |
| `NEO4J_PASSWORD` | Neo4j password | Yes |
| `SECRET_KEY` | JWT signing secret key | Yes |
| `DATABASE_PATH` | SQLite database path | Yes |
| `FIRST_ADMIN_USER` | Initial admin username | Yes |
| `FIRST_ADMIN_PASSWORD` | Initial admin password | Yes |
| `ALGORITHM` | JWT algorithm | No (default: HS256) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token expiry in minutes | No (default: 15) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token expiry in days | No (default: 7) |
| `DEBUG` | Enable debug mode | No (default: false) |

## 📖 API Documentation

### Search API (🔒 Requires Authentication)

#### Search All Labels
```http
GET /api/v1/search?node_id={node_id}&limit={limit}&offset={offset}
GET /api/v1/search?name={name}&limit={limit}&offset={offset}
Authorization: Bearer <token>
```

Parameters:
- `node_id` (optional): Search by node_id (exact match)
- `name` (optional): Search by name (partial match, case-insensitive)
- `limit` (optional): Maximum results to return (default: 100, max: 1000)
- `offset` (optional): Number of results to skip for pagination (default: 0)

#### Search by Specific Label
```http
GET /api/v1/search/{label}?node_id={node_id}&limit={limit}&offset={offset}
GET /api/v1/search/{label}?name={name}&limit={limit}&offset={offset}
Authorization: Bearer <token>
```

Available labels: `officer`, `entity`, `intermediary`, `address`

### Network API (🔒 Requires Authentication)

#### Get Neighbors
```http
GET /api/v1/network/neighbors/{node_id}
GET /api/v1/network/neighbors/{node_id}?label={label}&limit={limit}
Authorization: Bearer <token>
```

Parameters:
- `label` (optional): Filter neighbors by label (`officer`, `entity`, `intermediary`, `address`)
- `limit` (optional): Maximum neighbors to return (default: 100)

#### Find Shortest Path
```http
GET /api/v1/network/shortest-path?start_node_id={id1}&end_node_id={id2}
GET /api/v1/network/shortest-path?start_node_id={id1}&end_node_id={id2}&max_hops={hops}
Authorization: Bearer <token>
```

Parameters:
- `max_hops` (optional): Maximum path length to search (default: 4, range: 1-10)

#### Get Relationships
```http
GET /api/v1/network/relationships/{node_id}
GET /api/v1/network/relationships/{node_id}?rel_type={type}&limit={limit}
Authorization: Bearer <token>
```

Parameters:
- `rel_type` (optional): Filter relationships by type
- `limit` (optional): Maximum relationships to return (default: 100)

Response:
```json
{
  "relationships": [
    {
      "id": "5:abc:456",
      "source": "4:abc:123",
      "target": "4:abc:789",
      "type": "役員",
      "properties": {}
    }
  ]
}
```


### Cypher API (🔒 Requires Authentication)

#### Execute Query
```http
POST /api/v1/cypher/execute
Authorization: Bearer <token>
Content-Type: application/json

{
  "query": "MATCH (n) RETURN n LIMIT 10",
  "parameters": {}
}
```

#### Get Schema
```http
GET /api/v1/cypher/schema
```

#### Get Statistics
```http
GET /api/v1/cypher/stats
```

### Authentication API

The authentication system uses short-lived access tokens (15 minutes) and long-lived refresh tokens (7 days) stored in the database. This provides secure session management with the ability to logout and invalidate sessions.

#### Login
```http
POST /api/v1/auth/login
Content-Type: application/x-www-form-urlencoded

username=admin&password=admin
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "abc123...",
  "token_type": "bearer"
}
```

#### Refresh Token
Get a new access token using a valid refresh token. The refresh token is rotated (a new one is issued).
```http
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "abc123..."
}
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "xyz789...",
  "token_type": "bearer"
}
```

#### Logout
Invalidate a specific refresh token to end that session.
```http
POST /api/v1/auth/logout
Content-Type: application/json

{
  "refresh_token": "abc123..."
}
```

Response:
```json
{
  "message": "Successfully logged out"
}
```

#### Logout All Sessions (🔒 Requires Authentication)
Invalidate all refresh tokens for the current user.
```http
POST /api/v1/auth/logout-all
Authorization: Bearer <access_token>
```

Response:
```json
{
  "message": "Successfully logged out from 3 session(s)"
}
```

#### Get Current User (🔒 Requires Authentication)
```http
GET /api/v1/auth/me
Authorization: Bearer <access_token>
```

### Health Endpoints

```http
GET /health    # Health check with database status
GET /ready     # Readiness check
GET /live      # Liveness check
```

## 🔧 Configuration

Configuration is managed via `pydantic-settings`. All settings can be overridden via environment variables.

| Setting | Default | Description |
|---------|---------|-------------|
| `APP_NAME` | "AMI Server" | Application name |
| `APP_VERSION` | "1.0.0" | Application version |
| `DEBUG` | false | Debug mode |
| `DEFAULT_HOPS` | 1 | Default traversal hops |
| `MAX_HOPS` | 5 | Maximum traversal hops |
| `DEFAULT_LIMIT` | 100 | Default result limit |
| `MAX_LIMIT` | 1000 | Maximum result limit |

## 📁 Project Structure

```
ami-server/
├── app/
│   ├── __init__.py
│   ├── config.py              # Configuration with pydantic-settings
│   ├── main.py                # FastAPI application
│   ├── api/
│   │   ├── __init__.py
│   │   └── auth.py            # Authentication endpoints
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── dependencies.py    # Auth dependency injection
│   │   └── security.py        # JWT and password utilities
│   ├── db/
│   │   ├── __init__.py
│   │   ├── neo4j.py           # Neo4j connection management
│   │   └── session.py         # SQLite session management
│   ├── models/
│   │   ├── __init__.py
│   │   ├── graph.py           # Graph response models
│   │   └── user.py            # User SQLModel
│   └── routers/
│       ├── __init__.py
│       ├── search.py          # Search API endpoints
│       ├── network.py         # Network traversal endpoints
│       └── cypher.py          # Cypher query endpoints (protected)
├── tests/
│   ├── __init__.py
│   ├── conftest.py            # Test fixtures
│   ├── test_auth.py           # Authentication tests
│   ├── test_main.py
│   ├── test_search.py
│   ├── test_network.py
│   └── test_cypher.py
├── schema/
│   └── neo4j_importer_model.json
├── Dockerfile
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
└── README.md
```

## 📜 License

This project is licensed under the MIT License.

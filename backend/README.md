# Backend README

## Setup

### 1. Create virtual environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment
```bash
cp .env.example .env
# Edit .env with your configuration
```

### 4. Run the server
```bash
# Development
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or using Python
python -m app.main
```

### 5. Access API documentation
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health check: http://localhost:8000/health

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app entry point
│   ├── core/                # Core configuration & security
│   ├── api/                 # API endpoints
│   ├── models/              # Pydantic models
│   ├── services/            # Business logic
│   ├── repositories/        # Data access layer
│   └── database/            # Database models
├── tests/                   # Test files
├── alembic/                 # Database migrations
├── requirements.txt
└── Dockerfile
```

## Development

### Run tests
```bash
pytest
```

### Code formatting
```bash
black app/
ruff check app/
```

### Type checking
```bash
mypy app/
```

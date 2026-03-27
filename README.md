# Agentic-RE: Multi-agent Real Estate Analysis Framework

[![Paper](https://img.shields.io/badge/Paper-ECML--PKDD--2026-blue)](docs/AGENT_ARCHITECTURE.md)
[![Reproducibility](https://img.shields.io/badge/Reproducibility-Guide-green)](REPRODUCIBILITY.md)

An agentic framework for intelligent real estate analysis, combining geospatial data, energy performance certifications (EPC), and point-of-interest (POI) evaluation.

> **Note for Reviewers:** This repository has been anonymized for the double-blind review process. Please refer to [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md) for instructions on how to replicate the experimental results presented in the paper.

## Default User Account:
Username: `admin`  
Password: `admin123`

## 🏗️ Architecture

```
agentic-re/
├── backend/                # Python FastAPI backend
├── frontend/               # React TypeScript frontend
├── docker-compose.yml      # Development environment
└── TECH_STACK.md          # Complete tech stack documentation
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose (optional but recommended)

### Option 1: Automatic Setup (Recommended)

```powershell
# Run the setup script from the root of the repository
pwsh -File scripts/setup.ps1
```

This script:
- Creates the Python virtual environment
- Installs backend and frontend dependencies
- Runs backend tests
- Creates the default admin user (admin / admin123)

Optional flags:
- `-SkipTests`: Skip test execution
- `-SkipUser`: Skip admin user creation

### Option 2: Docker

```bash
# Start all services
docker-compose up -d

# Backend: http://localhost:8000
# Frontend: http://localhost:3000
# API Docs: http://localhost:8000/docs
```

### Option 3: Local Development

**Backend:**
```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your configurations
# Ensure LLM API keys are set

# Start server
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.example .env.local

# Start development server
npm run dev
```

## 📚 Documentation

- [`TECH_STACK.md`](TECH_STACK.md) - Complete technology stack
- [`backend/README.md`](backend/README.md) - Backend documentation
- [`frontend/README.md`](frontend/README.md) - Frontend documentation
- [`docs/AGENT_ARCHITECTURE.md`](docs/AGENT_ARCHITECTURE.md) - LLM agent architecture
- [`backend/API_GUIDE.md`](backend/API_GUIDE.md) - API guide

## 🛠️ Technology Stack

### Backend
- **FastAPI** - Modern web framework
- **DuckDB** - In-process analytical database
- **Redis** - Caching and state management
- **LangGraph** - LLM orchestration (Multi-agent workflow)

### Frontend
- **React 18** + **TypeScript**
- **Tailwind CSS** - Styling
- **Vite** - Build tool
- **React Leaflet** - Interactive maps

## 📊 Features

- ✅ AI-powered real estate analysis (Multi-agent LLM)
- ✅ Interactive map with clustering
- ✅ Energy performance certificate (EPC) management
- ✅ Points of Interest (POI) evaluation
- ✅ User feedback system
- ✅ JWT Authentication
- ✅ Real-time updates via WebSockets

## 🔄 Project Status

**Completed:**
- [x] Tech stack definition
- [x] Backend structure
- [x] Frontend structure
- [x] Docker configuration
- [x] Core agentic orchestration
- [x] Multi-attribute ranking engine

**In Progress:**
- [ ] Extended comparative evaluation
- [ ] Additional geographic data integration

## 📝 License

See [LICENSE](LICENSE) file.

## 👥 User Management

The system provides CLI scripts for user management.

### Create a User

```bash
cd backend
python create_user.py
```

### Delete a User

```bash
cd backend
python delete_user.py
```

Follow the on-screen instructions.

## 🧪 Testing

The project includes a comprehensive test suite for the backend.

### Test Setup

Ensure you are in the `backend` directory with the virtual environment active.

### Run Tests

```bash
# Run all tests
pytest

# Run specific repository tests
python -m tests.test_repositories

# Run integration tests
python -m tests.test_integration
```

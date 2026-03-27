# Agentic-RE: Complete Technology Stack

## Overview

This document defines the complete technology stack for the separated backend and frontend architecture.

---

## 🐍 Backend Stack (Python)

### Core Framework
- **FastAPI** `^0.109.0` - Modern async web framework
  - Auto-generated OpenAPI (Swagger) documentation
  - Pydantic v2 integration for schema validation
  - Native async/await and WebSocket support

### Web Server & ASGI
- **Uvicorn** `^0.27.0` - High-performance ASGI server
- **Gunicorn** (production) - Process manager with Uvicorn workers

### Database & Persistence
- **DuckDB** `^1.0.0` - In-process analytical database for fast real estate queries
- **SQLAlchemy** `^2.0.25` - SQL toolkit for SQLite user management
- **Redis** `^5.0.1` - Caching and analytical state management

### Data Processing
- **pandas** `^2.2.0` - Advanced data manipulation
- **pyarrow** `^15.0.0` - High-performance Parquet format support
- **NumPy** - Numerical computing

### LLM & Agentic Orchestration
- **LangGraph** `^0.0.10` - State-of-the-art agent workflow orchestration
- **LangChain** - Multi-provider LLM integration
- **Google Generative AI** (Gemini 1.5 Pro/Flash)
- **OpenAI** (GPT-4o)

### Utilities & Security
- **JWT (python-jose)** `^3.3.0` - Secure token-based authentication
- **Passlib (bcrypt)** `^1.7.4` - Industry-standard password hashing
- **Loguru** - Advanced structured logging

---

## ⚛️ Frontend Stack (React + TypeScript)

### Core Framework
- **React 18** - UI components and library
- **TypeScript** - Full-stack type safety
- **Vite** - Modern frontend build tool for rapid development

### State Management
- **TanStack Query (React Query)** - Efficient server state caching
- **Zustand** - Lightweight global client state

### UI & Styling
- **Tailwind CSS** - Utility-first styling framework
- **Lucide React** - Modern icons
- **React Leaflet** + **Leaflet** - Interactive geospatial mapping

---

## 🏗️ DevOps & Deployment

### Containerization
- **Docker** & **Docker Compose** - Standardized environment orchestration

### Web Server (Production)
- **Nginx** - Reverse proxy, SSL termination, and static asset serving

---

## 🌐 Environment Configuration

### Key Variables
- `DATABASE_PATH`: Local path to SQLite/DuckDB files
- `REDIS_URL`: Connection string for caching layer
- `GEMINI_API_KEY` / `OPENAI_API_KEY`: Credentials for LLM providers
- `SECRET_KEY`: High-entropy key for JWT generation

---

## 🚀 Performance Targets

- **API Latency**: <120ms (P95) for standard requests
- **Orchestration**: <15s for full multi-agent analysis (including 8+ LLM calls)
- **Map Rendering**: <1s for 500+ interactive markers with clustering

---

## 🧪 Testing Strategy

- **Unit Tests**: `pytest` for core business logic and individual agents
- **Integration Tests**: End-to-end flow validation starting from natural language queries
- **Benchmark Suite**: Synthetic test suite for model comparison and architectural fidelity

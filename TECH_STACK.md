# MEF-Immobili - Complete Technology Stack

## Overview

This document defines the complete technology stack for the separated backend and frontend architecture.

---

## 🐍 Backend Stack (Python)

### Core Framework
- **FastAPI** `^0.109.0` - Modern async web framework
  - Auto-generated OpenAPI documentation
  - Pydantic integration for validation
  - Native async/await support
  - WebSocket support

### Web Server & ASGI
- **Uvicorn** `^0.27.0` - ASGI server
  - With `uvloop` for better performance
  - With `httptools` for faster HTTP parsing
- **Gunicorn** (production) `^21.2.0` - Process manager

### Database & ORM
- **SQLAlchemy** `^2.0.25` - SQL toolkit and ORM
- **Alembic** `^1.13.1` - Database migrations
- **asyncpg** `^0.29.0` - Async PostgreSQL driver
- **psycopg2-binary** `^2.9.9` - PostgreSQL adapter (fallback)

### Data Processing (KEEP from current app)
- **pandas** `^2.2.0` - Data manipulation
- **numpy** `<2.0` - Numerical computing
- **pyarrow** `^15.0.0` - Parquet file support
- **fastparquet** - Alternative Parquet library

### LLM & AI (KEEP from current app)
- **openai** - OpenAI API client
- **google-genai** - Google Gemini API
- **langchain** - LLM orchestration framework
- **langchain-google-genai** - Gemini integration
- **langchain-openai** - OpenAI integration
- **langgraph** - Agent workflow management
- **pydantic** `>=2` - Data validation

### Geospatial & GIS
- **lxml** - XML parsing (for APE files)
- Network analysis libraries will be handled by frontend

### Authentication & Security
- **python-jose[cryptography]** `^3.3.0` - JWT tokens
- **passlib[bcrypt]** `^1.7.4` - Password hashing
- **python-multipart** `^0.0.6` - Form data parsing

### Caching & Performance
- **redis** `^5.0.1` - Redis client
- **aiocache** `^0.12.2` - Async caching framework

### Utilities
- **python-dotenv** - Environment variables
- **loguru** `^0.7.2` - Better logging
- **requests** - HTTP library
- **httpx** `^0.26.0` - Async HTTP client
- **tenacity** `^8.2.3` - Retry logic

### Development Tools
- **pytest** `^7.4.4` - Testing framework
- **pytest-asyncio** `^0.23.3` - Async test support
- **pytest-cov** `^4.1.0` - Coverage reporting
- **black** `^24.1.0` - Code formatter
- **ruff** `^0.1.14` - Fast linter
- **mypy** `^1.8.0` - Type checking

### API Documentation
- **FastAPI** includes automatic Swagger UI and ReDoc

---

## ⚛️ Frontend Stack (React + TypeScript)

### Core Framework
- **React** `^18.2.0` - UI library
- **TypeScript** `^5.3.3` - Type safety
- **Vite** `^5.0.11` - Build tool & dev server
  - Lightning-fast HMR
  - Optimized production builds
  - Built-in TypeScript support

### Routing
- **React Router** `^6.21.3` - Client-side routing
  - Nested routes
  - Lazy loading
  - Protected routes

### State Management
- **TanStack Query (React Query)** `^5.17.19` - Server state management
  - Automatic caching
  - Background refetching
  - Optimistic updates
  - Request deduplication
- **Zustand** `^4.4.7` - Lightweight global state (optional, for client state)
- **React Context** - Built-in, for auth and theme

### UI Framework & Styling
- **Tailwind CSS** `^3.4.1` - Utility-first CSS framework
- **PostCSS** `^8.4.33` - CSS processing
- **Autoprefixer** `^10.4.17` - Vendor prefixes
- **clsx** `^2.1.0` - Conditional classNames utility
- **tailwind-merge** `^2.2.0` - Merge Tailwind classes

### UI Component Libraries
- **Headless UI** `^1.7.18` - Unstyled, accessible components
  - Modals, Dropdowns, Tabs, etc.
  - Full keyboard navigation
  - ARIA compliant
- **Radix UI** `^1.3.0` (alternative/additional)
  - More primitive components
  - Excellent accessibility
- **Lucide React** `^0.312.0` - Icon library
  - Modern, consistent icons
  - Tree-shakeable

### Map & Geospatial
- **React Leaflet** `^4.2.1` - React bindings for Leaflet
- **Leaflet** `^1.9.4` - Interactive maps
- **leaflet.markercluster** `^1.5.3` - Marker clustering
- **@react-leaflet/core** - Core React Leaflet utilities

### Forms & Validation
- **React Hook Form** `^7.49.3` - Performant form library
  - Minimal re-renders
  - Built-in validation
- **Zod** `^3.22.4` - TypeScript-first schema validation
  - Type inference
  - Composable schemas

### HTTP Client
- **Axios** `^1.6.5` - HTTP client
  - Interceptors for auth
  - Request/response transformation
  - Better error handling than fetch

### Data Visualization (Optional, future)
- **Recharts** `^2.10.4` - Chart library
- **D3.js** (if needed for custom visualizations)

### Utilities
- **date-fns** `^3.2.0` - Date manipulation
- **lodash-es** `^4.17.21` - Utility functions (tree-shakeable)
- **nanoid** `^5.0.4` - Unique ID generation

### Development Tools
- **ESLint** `^8.56.0` - Linting
  - `eslint-plugin-react` - React rules
  - `eslint-plugin-react-hooks` - Hooks rules
  - `eslint-plugin-jsx-a11y` - Accessibility
- **Prettier** `^3.2.4` - Code formatting
- **TypeScript ESLint** - TS linting
- **Vite Plugin React SWC** - Fast refresh with SWC

### Testing
- **Vitest** `^1.2.0` - Unit testing (Vite-native)
- **@testing-library/react** `^14.1.2` - Component testing
- **@testing-library/jest-dom** - Custom matchers
- **@testing-library/user-event** - User interaction simulation
- **MSW (Mock Service Worker)** `^2.0.11` - API mocking

### Build & Optimization
- **vite-plugin-compression** - Gzip compression
- **vite-plugin-pwa** - Progressive Web App
- **rollup-plugin-visualizer** - Bundle analysis

---

## 🗄️ Database

### Primary Database (Production)
- **PostgreSQL** `15+`
  - JSONB support for flexible data
  - Full-text search
  - GIS extensions (PostGIS) if needed

### Development Database (Optional)
- **SQLite** (for local development/testing)

### Caching Layer
- **Redis** `7+`
  - Session storage
  - Query result caching
  - Real-time data pub/sub

---

## 🔧 DevOps & Infrastructure

### Containerization
- **Docker** `^24.0.0`
- **Docker Compose** `^2.23.0`

### Web Server (Production)
- **Nginx** `^1.25.0`
  - Reverse proxy
  - Static file serving
  - SSL termination
  - Load balancing

### CI/CD (Recommended)
- **GitHub Actions** - Automated testing and deployment
- **Docker Hub** / **GitHub Container Registry** - Image storage

### Monitoring & Logging (Production)
- **Sentry** - Error tracking (both frontend and backend)
- **Prometheus** + **Grafana** - Metrics and monitoring
- **ELK Stack** (optional) - Centralized logging

---

## 📦 Package Managers

### Backend
- **pip** with `requirements.txt` or **Poetry** for dependency management
  ```bash
  # Option 1: pip + requirements.txt
  pip install -r requirements.txt
  
  # Option 2: Poetry (recommended)
  poetry install
  ```

### Frontend
- **pnpm** `^8.14.0` (recommended - faster, more efficient)
  ```bash
  pnpm install
  ```
- **npm** `^10.2.0` (alternative)
- **yarn** (alternative)

---

## 🌐 Environment Configuration

### Backend Environment Variables
```env
# App Config
APP_NAME=MEF-Immobili-API
APP_VERSION=1.0.0
DEBUG=false
LOG_LEVEL=info

# Server
HOST=0.0.0.0
PORT=8000
WORKERS=4

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/mef_immobili
DATABASE_POOL_SIZE=5
DATABASE_MAX_OVERFLOW=10

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your-secret-key-here-min-32-chars
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# CORS
CORS_ORIGINS=http://localhost:3000,https://yourdomain.com

# LLM APIs (from current app)
GEMINI_API_KEY=your-gemini-key
OPENAI_API_KEY=your-openai-key

# External APIs
NOMINATIM_USER_AGENT=MEF-Immobili/1.0

# File Paths
DATA_DIR=/app/data
UPLOAD_DIR=/app/uploads
```

### Frontend Environment Variables
```env
# API
VITE_API_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000/api/v1/ws

# App Config
VITE_APP_NAME=MEF Immobili
VITE_APP_VERSION=1.0.0

# Map Config
VITE_MAP_CENTER_LAT=45.070860
VITE_MAP_CENTER_LON=7.685588
VITE_MAP_DEFAULT_ZOOM=13

# Feature Flags
VITE_ENABLE_ANALYTICS=false
VITE_ENABLE_PWA=false
```

---

## 📁 Project Structure Summary

```
mef-immobili/
├── backend/                    # Python FastAPI backend
│   ├── app/
│   ├── tests/
│   ├── alembic/
│   ├── requirements.txt       # or pyproject.toml
│   ├── Dockerfile
│   └── .env.example
│
├── frontend/                   # React TypeScript frontend
│   ├── src/
│   ├── public/
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   ├── vite.config.ts
│   ├── Dockerfile
│   └── .env.example
│
├── docker-compose.yml          # Development orchestration
├── docker-compose.prod.yml     # Production orchestration
├── nginx.conf                  # Nginx configuration
├── .gitignore
└── README.md
```

---

## 🚀 Quick Start Commands

### Backend Development
```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Development
```bash
cd frontend

# Install dependencies
pnpm install

# Start development server
pnpm dev

# Build for production
pnpm build

# Preview production build
pnpm preview
```

### Docker Development (Both)
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
```

---

## 🎨 Design System

### Tailwind Configuration
We'll use a custom design system based on your current app's aesthetics:

```javascript
// tailwind.config.js
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#f0f9ff',
          100: '#e0f2fe',
          500: '#0ea5e9',
          600: '#0284c7',
          700: '#0369a1',
          900: '#0c4a6e',
        },
        secondary: {
          500: '#6f42c1',
          600: '#5a2da8',
        },
        success: '#00C853',
        warning: '#ffc107',
        danger: '#dc3545',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
  ],
}
```

### Typography
- **Primary Font:** Inter (Google Fonts)
- **Monospace:** JetBrains Mono (for code)

---

## 🔐 Security Considerations

### Backend
- JWT tokens with refresh mechanism
- Password hashing with bcrypt (12 rounds)
- SQL injection prevention (SQLAlchemy ORM)
- XSS prevention (output escaping)
- CORS properly configured
- Rate limiting on endpoints
- Input validation with Pydantic

### Frontend
- XSS prevention (React's automatic escaping)
- CSRF tokens for forms
- Secure token storage (httpOnly cookies preferred)
- Content Security Policy headers
- Dependency vulnerability scanning

---

## 📊 Performance Targets

### Backend
- API response time: <100ms (95th percentile)
- WebSocket message latency: <50ms
- Concurrent connections: 1000+
- Database query time: <50ms (average)

### Frontend
- Initial load: <3s
- Time to Interactive: <3s
- Lighthouse score: >90
- First Contentful Paint: <1.5s
- Bundle size: <300KB (initial)

---

## 🧪 Testing Strategy

### Backend
- **Unit tests:** 80%+ coverage
- **Integration tests:** API endpoints
- **Load tests:** Artillery or Locust
- **Security tests:** OWASP ZAP

### Frontend
- **Unit tests:** Components, hooks, utilities
- **Integration tests:** User flows with Testing Library
- **E2E tests:** Playwright or Cypress (future)
- **Visual regression:** Chromatic (optional)

---

## 📚 Documentation

### Backend
- Auto-generated OpenAPI docs at `/docs`
- API reference documentation
- Architecture decision records (ADRs)

### Frontend
- Storybook for component documentation (optional)
- JSDoc comments for complex functions
- README with setup instructions

---

## 🔄 Version Control Strategy

### Branch Strategy
```
main              # Production-ready code
├── develop       # Integration branch
├── feature/*     # Feature branches
├── bugfix/*      # Bug fix branches
└── release/*     # Release branches
```

### Commit Convention
```
feat: Add new analysis endpoint
fix: Resolve marker clustering bug
docs: Update API documentation
refactor: Simplify authentication logic
test: Add tests for building service
chore: Update dependencies
```

---

## 📋 Migration Checklist

- [ ] Review and approve tech stack
- [ ] Set up development environment
- [ ] Install all dependencies
- [ ] Configure linters and formatters
- [ ] Set up Docker development environment
- [ ] Create environment variable templates
- [ ] Initialize Git repository structure
- [ ] Set up CI/CD pipeline
- [ ] Begin Phase 1 implementation

---

## 🔗 Useful Resources

### Documentation
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [React Docs](https://react.dev/)
- [Tailwind CSS](https://tailwindcss.com/)
- [TanStack Query](https://tanstack.com/query/latest)
- [React Leaflet](https://react-leaflet.js.org/)

### Tutorials & Guides
- [FastAPI Best Practices](https://github.com/zhanymkanov/fastapi-best-practices)
- [React TypeScript Cheatsheet](https://react-typescript-cheatsheet.netlify.app/)
- [Bulletproof React](https://github.com/alan2207/bulletproof-react)

---

## ✅ Next Steps

1. ✅ Review this tech stack document
2. Create `backend/` folder structure
3. Create `frontend/` folder structure  
4. Initialize both projects with dependencies
5. Set up Docker development environment
6. Begin implementing authentication

**Ready to proceed with setup!** 🚀

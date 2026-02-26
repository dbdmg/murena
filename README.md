# MEF-Immobili - Backend & Frontend Separation

Applicazione per l'analisi immobiliare con backend REST API (FastAPI) e frontend moderno (React + TypeScript).

## USER ACCOUNT:
Username: admin
Password: admin123

## 🏗️ Architettura

```
mef-immobili/
├──backend/                # Python FastAPI backend
├── frontend/               # React TypeScript frontend
├── docker-compose.yml      # Development environment
└── TECH_STACK.md          # Complete tech stack documentation
```

## 🚀 Quick Start

### Requisiti

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose (opzionale ma raccomandato)

### Opzione 1: Setup Automatico (Consigliato per nuove macchine)

```powershell
# Esegui lo script di setup dalla root del repository
pwsh -File scripts/setup.ps1
```

Questo script:
- Crea il virtual environment Python
- Installa le dipendenze backend e frontend
- Esegue i test del backend
- Crea l'utente admin di default (admin / admin123)

Flags opzionali:
- `-SkipTests`: Salta l'esecuzione dei test
- `-SkipUser`: Salta la creazione dell'utente admin

### Opzione 2: Docker

```bash
# Avvia tutti i servizi
docker-compose up -d

# Backend: http://localhost:8000
# Frontend: http://localhost:3000
# API Docs: http://localhost:8000/docs
```

### Opzione 2: Sviluppo Locale

**Backend:**
```bash
cd backend

# Crea virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Installa dipendenze
pip install -r requirements.txt

# Configura environment
cp .env.example .env
# Modifica .env con le tue configurazioni

# Avvia server
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend

# Installa dipendenze
npm install

# Configura environment
cp .env.example .env.local

# Avvia development server
npm run dev
```

## 📚 Documentazione

- [`TECH_STACK.md`](TECH_STACK.md) - Stack tecnologico completo
- [`backend/README.md`](backend/README.md) - Documentazione backend
- [`frontend/README.md`](frontend/README.md) - Documentazione frontend
- [`docs/AGENT_ARCHITECTURE.md`](docs/AGENT_ARCHITECTURE.md) - Architettura Agenti LLM
- [`backend/API_GUIDE.md`](backend/API_GUIDE.md) - Guida API

## 🛠️ Stack Tecnologico

### Backend
- **FastAPI** - Framework web moderno
- **PostgreSQL** - Database relazionale
- **Redis** - Caching
- **SQLAlchemy** - ORM
- **LangChain** - Orchestrazione LLM (8 agents)

### Frontend
- **React 18** + **TypeScript**
- **Tailwind CSS** - Styling
- **Vite** - Build tool
- **TanStack Query** - Data fetching
- **React Router** - Routing
- **React Leaflet** - Mappe interattive

## 📊 Funzionalità

- ✅ Analisi immobiliare con AI (LLM multi-agent)
- ✅ Mappa interattiva con clustering
- ✅ Gestione certificati energetici (APE)
- ✅ Valutazione Points of Interest (POI)
- ✅ Sistema di feedback
- ✅ Autenticazione JWT
- ✅ Real-time updates via WebSocket

## 🔄 Stato Migrazione

**Completato:**
- [x] Definizione stack tecnologico
- [x] Struttura backend
- [x] Struttura frontend
- [x] Configurazione Docker
- [x] Setup base FastAPI
- [x] Setup base React + Tailwind

**In corso:**
- [ ] Migrazione LLM agents
- [ ] Implementazione API endpoints
- [ ] Creazione componenti React
- [ ] Integrazione mappe

## 📝 Licenza

Vedere file [LICENSE](LICENSE)

## 👥 Team

Progetto MEF-Immobili

## 👥 Gestione Utenti

Il sistema fornisce script CLI per gestire gli utenti.

### Creare un Utente

```bash
cd backend
python create_user.py
```

### Eliminare un Utente

```bash
cd backend
python delete_user.py
```

Seguire le istruzioni a schermo.

## 🧪 Esecuzione dei Test

Il progetto include una suite di test completa per il backend.

### Setup Test

Assicurarsi di essere nella directory `backend` e di avere l'ambiente virtuale attivo.

### Eseguire i test

```bash
# Esegui tutti i test
pytest

# Esegui test specifici per repository (incluso db)
python -m tests.test_repositories

# Esegui test di integrazione
python -m tests.test_integration
```

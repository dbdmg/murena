# RealEstate-AI Setup Script
# Run this script from the repository root to set up a new development environment.
#
# Usage:
#   pwsh -File scripts/setup.ps1
#
# Optional flags:
#   -SkipTests      Skip running backend tests
#   -SkipUser       Skip creating default admin user

param(
    [switch]$SkipTests,
    [switch]$SkipUser
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   RealEstate-AI Development Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# =============================================================================
# Step 1: Backend Setup
# =============================================================================
Write-Host "[1/4] Setting up Backend..." -ForegroundColor Yellow

$BackendDir = Join-Path $RepoRoot "backend"
$VenvDir = Join-Path $BackendDir ".venv"

Push-Location $BackendDir

# Create virtual environment if it doesn't exist
if (-Not (Test-Path $VenvDir)) {
    Write-Host "  Creating Python virtual environment..."
    python -m venv .venv
}

# Activate virtual environment and install dependencies
Write-Host "  Installing Python dependencies..."
if ($IsWindows -or $env:OS -match "Windows") {
    & "$VenvDir\Scripts\Activate.ps1"
}
else {
    & "$VenvDir/bin/Activate.ps1"
}

pip install -r requirements.txt --quiet

Write-Host "  Backend dependencies installed." -ForegroundColor Green

Pop-Location

# =============================================================================
# Step 2: Frontend Setup
# =============================================================================
Write-Host "[2/4] Setting up Frontend..." -ForegroundColor Yellow

$FrontendDir = Join-Path $RepoRoot "frontend"
Push-Location $FrontendDir

Write-Host "  Installing npm dependencies..."
npm install --silent

Write-Host "  Frontend dependencies installed." -ForegroundColor Green

Pop-Location

# =============================================================================
# Step 3: Run Backend Tests
# =============================================================================
if (-Not $SkipTests) {
    Write-Host "[3/4] Running Backend Tests..." -ForegroundColor Yellow

    Push-Location $BackendDir

    # Activate venv again (in case it was deactivated)
    if ($IsWindows -or $env:OS -match "Windows") {
        & "$VenvDir\Scripts\Activate.ps1"
    }
    else {
        & "$VenvDir/bin/Activate.ps1"
    }

    pytest -v --tb=short

    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Some tests failed. Please review the output above." -ForegroundColor Yellow
    }
    else {
        Write-Host "  All tests passed." -ForegroundColor Green
    }

    Pop-Location
}
else {
    Write-Host "[3/4] Skipping tests (--SkipTests flag set)." -ForegroundColor DarkGray
}

# =============================================================================
# Step 4: Create Default Admin User
# =============================================================================
if (-Not $SkipUser) {
    Write-Host "[4/4] Creating default admin user..." -ForegroundColor Yellow

    Push-Location $BackendDir

    # Activate venv
    if ($IsWindows -or $env:OS -match "Windows") {
        & "$VenvDir\Scripts\Activate.ps1"
    }
    else {
        & "$VenvDir/bin/Activate.ps1"
    }

    # Create admin user non-interactively
    python -c @"
import sys
sys.path.insert(0, '.')
from app.database.connection import SessionLocal
from app.repositories import UserRepository
from app.core.security import get_password_hash

db = SessionLocal()
try:
    repo = UserRepository(db)
    if repo.get_by_username('admin'):
        print('  Admin user already exists. Skipping.')
    else:
        hashed = get_password_hash('admin123')
        user = repo.create_user(username='admin', password_hash=hashed, email='admin@example.com')
        print(f'  Created admin user (ID: {user.id})')
except Exception as e:
    print(f'  Error creating admin user: {e}')
finally:
    db.close()
"@

    Write-Host "  Default admin user ready (admin / admin123)." -ForegroundColor Green

    Pop-Location
}
else {
    Write-Host "[4/4] Skipping user creation (--SkipUser flag set)." -ForegroundColor DarkGray
}

# =============================================================================
# Done
# =============================================================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "   Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "To start the application:" -ForegroundColor Cyan
Write-Host "  Backend:  cd backend && .venv\Scripts\Activate.ps1 && py -m app.main"
Write-Host "  Frontend: cd frontend && npm run dev"
Write-Host ""
Write-Host "Default login: admin / admin123" -ForegroundColor Yellow
Write-Host ""

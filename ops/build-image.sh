#!/bin/bash
# Exit on error
set -e

# Ensure we are in the directory of the script
cd "$(dirname "$0")"

echo "🔍 Reading versions..."

# Extract Frontend Version (from package.json)
# Uses grep/awk/sed to avoid dependency on jq
FRONTEND_VERSION=$(grep '"version":' ../frontend/package.json | head -n 1 | awk -F: '{ print $2 }' | sed 's/[",]//g' | tr -d '[[:space:]]')

# Extract Backend Version (from config.py)
BACKEND_VERSION=$(grep 'APP_VERSION: str =' ../backend/app/core/config.py | awk -F'=' '{print $2}' | sed 's/[ ""]//g')

if [ -z "$FRONTEND_VERSION" ] || [ -z "$BACKEND_VERSION" ]; then
    echo "❌ Error: Could not detect versions."
    echo "Frontend: $FRONTEND_VERSION"
    echo "Backend: $BACKEND_VERSION"
    exit 1
fi

echo "=========================================="
echo "🏗️  RealEstate-AI Build System"
echo "=========================================="
echo "Frontend Version: $FRONTEND_VERSION"
echo "Backend Version:  $BACKEND_VERSION"
echo "=========================================="
echo ""

# Build Backend
echo "📦 Building Backend (realestate-backend:$BACKEND_VERSION)..."
docker build -t realestate-backend:$BACKEND_VERSION -t realestate-backend:latest -t realestate-backend:local -f ../backend/Dockerfile ../backend

# Build Frontend
echo "📦 Building Frontend (realestate-frontend:$FRONTEND_VERSION)..."
docker build -t realestate-frontend:$FRONTEND_VERSION -t realestate-frontend:latest -t realestate-frontend:local -f ../frontend/Dockerfile ../frontend

echo ""
echo "✅ Build Complete!"
echo "------------------------------------------"
echo "Images created:"
echo " - realestate-backend:$BACKEND_VERSION (latest)"
echo " - realestate-frontend:$FRONTEND_VERSION (latest)"
echo "------------------------------------------"
echo "To run production:"
echo "cd ops/production && docker-compose up -d"
echo "------------------------------------------"

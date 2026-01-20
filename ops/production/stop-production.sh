#!/bin/bash
clear;

set -e

pushd "$(dirname "$0")"

echo "🛑 Stopping staging environment..."

docker compose down
docker compose rm -f

echo ""
echo "📊 Container status:"
docker compose ps

echo ""
echo "✅ Staging environment stopped successfully!"

popd

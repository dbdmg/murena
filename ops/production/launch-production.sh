#!/bin/bash

clear;
set -e

pushd "$(dirname "$0")"

echo "🚀 Launching staging environment..."

docker compose up -d

echo ""
echo "📊 Container status:"
docker compose ps

echo ""
echo "✅ Staging environment launched successfully!"
echo "🌐 Application should be available at http://localhost"

popd

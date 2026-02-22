#!/bin/bash
set -e

# Check if 'docker compose' is available
if docker compose version >/dev/null 2>&1; then
    CDM="docker compose"
else
    echo "Error: 'docker compose' (v2) is not found. Please update Docker Desktop or install the compose plugin."
    echo "The legacy 'docker-compose' (v1) tool is incompatible with this setup."
    exit 1
fi

echo "Cleaning up old containers to prevent compatibility issues..."
$CDM down --remove-orphans || true

echo "Building and starting services using $CDM..."
$CDM up -d --build

echo "Waiting for services to be healthy..."
sleep 5
$CDM ps

echo "System started!"
echo "Frontend: http://localhost:3010"
echo "Admin API: http://localhost:8000/docs"
echo "Website: http://localhost:8080"

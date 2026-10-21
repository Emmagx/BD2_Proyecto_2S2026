#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

echo "1. Deteniendo contenedor..."
docker compose down

echo "2. Eliminando volumen residual (si existe)..."
docker volume rm fase2_pgdata 2>/dev/null || true

echo "3. Eliminando datos de pgdata..."
docker run --rm -v "$(pwd)/pgdata:/target" alpine sh -c "rm -rf /target/* /target/.[!.]* 2>/dev/null || true"

echo "4. Verificando limpieza..."
if docker ps -a --format '{{.Names}}' | grep -q "^postgres_fase2$"; then
    echo "ERROR: el contenedor postgres_fase2 aun existe"
    exit 1
fi

if [ -n "$(ls -A ./pgdata 2>/dev/null)" ]; then
    echo "ERROR: el directorio pgdata no esta vacio"
    exit 1
fi

echo "=== Entorno limpio ==="

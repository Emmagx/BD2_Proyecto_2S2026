#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

start=$(date +%s.%N)
echo "=== RESTAURANDO: Full + Incrementales ==="

echo "1. Preparando directorio ./pgdata..."
mkdir -p ./pgdata

echo "2. Combinando full + incrementales con pg_combinebackup..."
sudo rm -rf ./restore_combined
docker run --rm \
  -v "$(pwd)/backups:/backups" \
  -v "$(pwd)/restore_combined:/restore_combined" \
  postgres:17-alpine \
  pg_combinebackup -o /restore_combined \
    /backups/00_completo \
    /backups/01_incremental \
    /backups/02_incremental

echo "3. Copiando los datos combinados a ./pgdata..."
docker run --rm \
  -v "$(pwd)/pgdata:/var/lib/postgresql/data" \
  -v "$(pwd)/restore_combined:/backup_source:ro" \
  alpine sh -c "cp -a /backup_source/. /var/lib/postgresql/data/ && chown -R 70:70 /var/lib/postgresql/data && chmod 700 /var/lib/postgresql/data"

echo "4. Levantando el contenedor..."
docker compose up -d

echo "5. Esperando a que PostgreSQL acepte conexiones..."
until docker exec postgres_cali pg_isready -U postgres -q; do
    sleep 0.1
done

echo "6. Limpieza de archivos temporales..."
sudo rm -rf ./restore_combined

end=$(date +%s.%N)
echo
echo "=== Restauración FULL + INCREMENTALES completada ==="
echo "Duración: $(echo "$end - $start" | bc) segundos"

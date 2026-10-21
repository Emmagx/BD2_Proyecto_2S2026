#!/usr/bin/env bash
# Ejecuta Fase 1 + Fases 2-5 desde cero.
# Requisitos: Docker, contenedor postgres_cali completo, .venv con pymongo.
set -euo pipefail
FASE3="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$FASE3"

PY="$FASE3/../.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"
export PYTHON="$PY"

echo "== Levantando MongoDB =="
docker compose up -d
for i in $(seq 1 60); do
  if docker exec mongo_fase3 mongosh --quiet --eval 'db.adminCommand({ping:1}).ok' >/dev/null 2>&1; then
    echo "MongoDB listo"
    break
  fi
  sleep 1
  if [ "$i" -eq 60 ]; then
    echo "MongoDB no respondió"; docker logs mongo_fase3 --tail 30; exit 1
  fi
done

mkdir -p evidencia
LOG="evidencia/run_all_$(date +%Y%m%d_%H%M%S).log"
{
  echo "################################################################"
  echo "# FASE 3 COMPLETA - $(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "################################################################"
  ./fase1/scripts/run_fase1.sh --fuente pg
  ./fase2/run_fase2.sh
  ./fase3/run_fase3.sh
  ./fase4/run_fase4.sh
  ./fase5/run_fase5.sh
  echo "################################################################"
  echo "# FIN - $(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "################################################################"
} 2>&1 | tee "$LOG"

echo
echo "Pipeline completo. Evidencia final: evidencia/fase5/validacion.md"
echo "Log: $LOG"

#!/usr/bin/env bash
# Fase 2: verificación + catálogos
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FASE3="$(cd "$DIR/.." && pwd)"
cd "$FASE3"
PY="$FASE3/../.venv/bin/python"; [ -x "$PY" ] || PY="$(command -v python3)"
mkdir -p evidencia/fase2
LOG="evidencia/fase2/ejecucion_$(date +%Y%m%d_%H%M%S).log"
{
  echo "# FASE 2 - CATALOGOS - $(date '+%Y-%m-%d %H:%M:%S %Z')"
  "$PY" fase2/scripts/00_verificar_entorno.py
  "$PY" fase2/scripts/01_catalogos.py --recrear
  echo "# FIN $(date '+%Y-%m-%d %H:%M:%S %Z')"
} 2>&1 | tee "$LOG"

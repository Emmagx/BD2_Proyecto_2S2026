#!/usr/bin/env bash
# Fase 3: resultados
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FASE3="$(cd "$DIR/.." && pwd)"
cd "$FASE3"
PY="$FASE3/../.venv/bin/python"; [ -x "$PY" ] || PY="$(command -v python3)"
mkdir -p evidencia/fase3
LOG="evidencia/fase3/ejecucion_$(date +%Y%m%d_%H%M%S).log"
{
  echo "# FASE 3 - RESULTADOS - $(date '+%Y-%m-%d %H:%M:%S %Z')"
  "$PY" fase3/scripts/01_resultados.py --recrear
  echo "# FIN $(date '+%Y-%m-%d %H:%M:%S %Z')"
} 2>&1 | tee "$LOG"

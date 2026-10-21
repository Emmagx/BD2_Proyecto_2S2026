#!/usr/bin/env bash
# Fase 4: atletas y países
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FASE3="$(cd "$DIR/.." && pwd)"
cd "$FASE3"
PY="$FASE3/../.venv/bin/python"; [ -x "$PY" ] || PY="$(command -v python3)"
mkdir -p evidencia/fase4
LOG="evidencia/fase4/ejecucion_$(date +%Y%m%d_%H%M%S).log"
{
  echo "# FASE 4 - ATLETAS Y PAISES - $(date '+%Y-%m-%d %H:%M:%S %Z')"
  "$PY" fase4/scripts/01_atletas.py --recrear
  "$PY" fase4/scripts/02_paises.py --recrear
  echo "# FIN $(date '+%Y-%m-%d %H:%M:%S %Z')"
} 2>&1 | tee "$LOG"

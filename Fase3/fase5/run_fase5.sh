#!/usr/bin/env bash
# Fase 5: índices + validación
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FASE3="$(cd "$DIR/.." && pwd)"
cd "$FASE3"
PY="$FASE3/../.venv/bin/python"; [ -x "$PY" ] || PY="$(command -v python3)"
mkdir -p evidencia/fase5
LOG="evidencia/fase5/ejecucion_$(date +%Y%m%d_%H%M%S).log"
{
  echo "# FASE 5 - INDICES Y VALIDACION - $(date '+%Y-%m-%d %H:%M:%S %Z')"
  "$PY" fase5/scripts/01_indices.py
  "$PY" fase5/scripts/02_validar.py
  echo "# FIN $(date '+%Y-%m-%d %H:%M:%S %Z')"
} 2>&1 | tee "$LOG"

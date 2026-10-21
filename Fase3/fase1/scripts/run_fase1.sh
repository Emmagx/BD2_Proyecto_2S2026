#!/usr/bin/env bash
# ============================================================================
# Fase 1 de la Fase 3 - Ejecución completa
#
# Uso:
#   ./fase1/scripts/run_fase1.sh
#   ./fase1/scripts/run_fase1.sh --fuente csv
#   ./fase1/scripts/run_fase1.sh --fuente pg
#
# Genera: insumos curados, dim_juegos, dim_sedes, alias, nombres
# normalizados, validación y evidencia con fecha/hora.
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FASE1_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$FASE1_DIR"

PY="${PYTHON:-python3}"
mkdir -p datos/insumos evidencia
LOG="evidencia/ejecucion_$(date +%Y%m%d_%H%M%S).log"

echo "Salida completa en: $LOG"
{
  echo "################################################################"
  echo "# FASE 3 - FASE 1: PREPARACIÓN DE DATOS"
  echo "# Inicio: $(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "################################################################"

  echo
  echo "== 1/5 Insumos curados (sedes y alias) =="
  "$PY" scripts/00_generar_insumos.py "$@"

  echo
  echo "== 2/5 dim_juegos y dim_sedes =="
  "$PY" scripts/01_generar_dim_juegos.py "$@"

  echo
  echo "== 3/5 Alias de países =="
  "$PY" scripts/02_generar_alias_paises.py "$@"

  echo
  echo "== 4/5 Normalización de nombres =="
  "$PY" scripts/03_generar_nombres_normalizados.py "$@"

  echo
  echo "== 5/5 Validación y evidencia =="
  "$PY" scripts/04_validar_fase1.py "$@"

  echo
  echo "################################################################"
  echo "# Fin: $(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "################################################################"
} 2>&1 | tee "$LOG"

echo
echo "Fase 1 completada. Evidencia: $FASE1_DIR/evidencia/validacion_fase1.md"

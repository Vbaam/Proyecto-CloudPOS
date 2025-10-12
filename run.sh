#!/usr/bin/env bash
# run.sh — Ejecuta CloudPOS con entorno virtual si existe.
# Uso:
#   ./run.sh
#   RUN_DEBUG=1 ./run.sh   # modo depuración (set -x)

set -Eeuo pipefail

# Activa traza si se pide
if [[ "${RUN_DEBUG:-0}" == "1" ]]; then
  set -x
fi

# Ir al directorio del script (raíz del proyecto), cuidando espacios
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
cd "$SCRIPT_DIR"

# Variables de entorno para Qt (HiDPI y Wayland si corresponde)
export QT_ENABLE_HIGHDPI_SCALING=1
if [[ "${XDG_SESSION_TYPE:-}" == "wayland" ]]; then
  export QT_QPA_PLATFORM=wayland
fi

# Opcional: mostrar todas las vistas en desarrollo (descomenta si quieres)
# export CLOUDPOS_SHOW_ALL=1

# Detectar intérprete de Python
if [[ -x "$SCRIPT_DIR/.venv/bin/python" ]]; then
  PY="$SCRIPT_DIR/.venv/bin/python"
elif [[ -x "$SCRIPT_DIR/venv/bin/python" ]]; then
  PY="$SCRIPT_DIR/venv/bin/python"
else
  # Fallback al python del sistema
  PY="$(command -v python3 || true)"
  if [[ -z "${PY}" ]]; then
    echo "Error: no se encontró python3 en el PATH y no hay .venv/venv." >&2
    exit 1
  fi
fi

# Mostrar información útil en modo debug
if [[ "${RUN_DEBUG:-0}" == "1" ]]; then
  echo "SCRIPT_DIR=$SCRIPT_DIR"
  echo "PY=$PY"
  "$PY" -c 'import sys; print(sys.version); print("python:", sys.executable)'
fi

# Ejecutar la app sin usar pyc (más fiable al actualizar código)
exec "$PY" -B -m app.main
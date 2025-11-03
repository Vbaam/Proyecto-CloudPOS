# Utilidades para normalizar/convertir roles entre formas (id, texto, objeto)
from typing import Any

ROLE_MAP = {
    1: "Administrador",
    2: "Cajero",
    3: "Bodega",
}

def normalize_role(role_raw: Any, default: str = "Cajero") -> str:
    if role_raw is None:
        return default

    # Si es dict, intentar extraer un id o nombre
    if isinstance(role_raw, dict):
        for key in ("rol_id", "role_id", "id_rol", "rolid", "id"):
            if key in role_raw and role_raw.get(key) is not None:
                try:
                    return ROLE_MAP.get(int(role_raw.get(key)), default)
                except Exception:
                    break
        for key in ("rol", "role", "nombre_rol", "nombre"):
            if key in role_raw and isinstance(role_raw.get(key), str):
                role_raw = role_raw.get(key)
                break
        else:
            return default

    # Si es entero
    if isinstance(role_raw, int):
        return ROLE_MAP.get(role_raw, default)

    # Si es string
    if isinstance(role_raw, str):
        s = role_raw.strip().lower()
        # si es numérico en texto
        if s.isdigit():
            try:
                return ROLE_MAP.get(int(s), default)
            except Exception:
                return default
        if s in ("administrador", "admin", "administrator"):
            return "Administrador"
        if s in ("caja", "cajero"):
            return "Cajero"
        if s in ("bodega", "almacen", "warehouse"):
            return "Bodega"
        return s.capitalize()

    return default
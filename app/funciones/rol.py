# Utilidades para normalizar/convertir roles entre formas (id, texto, objeto)
from typing import Any

ROLE_MAP = {
    1: "Administrador",
    2: "Cajero",
    3: "Bodega",
}

def normalize_role(role_raw: Any, default: str = "Cajero") -> str:
    """
    Normaliza role_raw a una de las claves usadas por la UI:
    'Administrador', 'Cajero', 'Bodega'.
    Acepta integers, strings (numéricos o nombres), o dicts que contengan rol/rol_id.
    """
    if role_raw is None:
        return default

    # Si es dict, intentar extraer un id o nombre
    if isinstance(role_raw, dict):
        # Buscar id numérico en keys típicas
        for key in ("rol_id", "role_id", "id_rol", "rolid", "id"):
            if key in role_raw and role_raw.get(key) is not None:
                try:
                    return ROLE_MAP.get(int(role_raw.get(key)), default)
                except Exception:
                    break
        # Buscar nombre de rol en keys típicas
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
        # mapear nombres conocidos
        if s in ("administrador", "admin", "administrator"):
            return "Administrador"
        if s in ("caja", "cajero"):
            return "Cajero"
        if s in ("bodega", "almacen", "warehouse"):
            return "Bodega"
        # fallback: capitalizar
        return s.capitalize()

    # fallback
    return default
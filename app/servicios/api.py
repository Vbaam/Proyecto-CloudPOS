import os
import json
from urllib import request, error


def _get_qapp_property(name: str) -> str | None:
    """Lee propiedades efímeras guardadas en QApplication (memoria de la app)."""
    try:
        from PySide6 import QtWidgets  
        app = QtWidgets.QApplication.instance()
        if app is not None:
            val = app.property(name)
            if val:
                return str(val)
    except Exception:
        pass
    return None


def _get_runtime_auth_token() -> str | None:
    """
    Token de sesión entregado por /login (el que DEBE usarse en el resto de endpoints):
    guardado como QApplication.property("auth_token").
    """
    return _get_qapp_property("auth_token")


class ApiClient:
    def __init__(self, base_url: str | None = None, timeout: int = 10):
        self.base_url = (base_url or os.getenv("CLOUDPOS_API_BASE", "http://18.233.18.214:8000")).rstrip("/")
        self.timeout = timeout

    # ---------------- Internos ----------------

    def _parse_body(self, raw: bytes):
        text = raw.decode("utf-8", errors="ignore")
        try:
            return json.loads(text)
        except Exception:
            return {"detail": text or "HTTP error"}

    def _auth_headers(self) -> dict:
        """
        Cabecera Authorization estándar para TODOS los endpoints de negocio.
        Usa el token de sesión guardado tras /login (auth_token).
        """
        token = _get_runtime_auth_token()
        return {"Authorization": f"Bearer {token}"} if token else {}

    def _request(self, method: str, path: str, payload: dict | None = None, include_auth: bool = True):
        url = f"{self.base_url}/{path.replace('//','/').lstrip('/')}"
        data = None
        headers = {
            "accept": "application/json",
        }
        if include_auth:
            headers.update(self._auth_headers())

        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["content-type"] = "application/json"

        req = request.Request(url, data=data, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                text = resp.read().decode("utf-8", errors="ignore")
                try:
                    return json.loads(text)
                except Exception:
                    return {"detail": text or "OK", "status": getattr(resp, "status", 200)}
        except error.HTTPError as e:
            body = e.read() or b""
            parsed = self._parse_body(body) or {}
            return {"error": True, "status": e.code, **parsed}
        except error.URLError as e:
            return {"error": True, "status": 0, "detail": str(getattr(e, "reason", "Error de red"))}

    # ---------------- API pública ----------------

    def get_json(self, path: str):
        return self._request("GET", path, None, include_auth=True)

    def post_json(self, path: str, payload: dict):
        return self._request("POST", path, payload, include_auth=True)

    def put_json(self, path: str, payload: dict):
        return self._request("PUT", path, payload, include_auth=True)

    def delete_json(self, path: str):
        return self._request("DELETE", path, None, include_auth=True)

    def check_api(self) -> bool:
        # Health simple: sin token
        try:
            url = f"{self.base_url}/"
            req = request.Request(url, headers={"accept": "application/json"})
            with request.urlopen(req, timeout=min(5, self.timeout)):
                return True
        except Exception:
            return False

import os
import json
from urllib import request, error


class ApiClient:
    def __init__(self, base_url: str | None = None, timeout: int = 10):
        self.base_url = (base_url or os.getenv("CLOUDPOS_API_BASE", "http://18.233.18.214:8000")).rstrip("/")
        self.timeout = timeout

    def get_json(self, path: str):
        url = f"{self.base_url}/{path.lstrip('/')}"
        req = request.Request(url, headers={"accept": "application/json"})
        with request.urlopen(req, timeout=self.timeout) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
            return json.loads(raw)

    def post_json(self, path: str, payload: dict):
        url = f"{self.base_url}/{path.lstrip('/')}"
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url,
            data=data,
            headers={
                "accept": "application/json",
                "content-type": "application/json",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=self.timeout) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
            try:
                return json.loads(raw)
            except Exception:
                return raw

    def check_api(self) -> bool:
        """
        Ping ligero a la API para verificar conectividad.
        Usa /categorias porque sabemos que existe.
        Devuelve True si responde 2xx, False en cualquier error.
        """
        try:
            url = f"{self.base_url}/categorias"
            req = request.Request(url, headers={"accept": "application/json"})
            with request.urlopen(req, timeout=min(5, self.timeout)) as _:
                return True
        except error.URLError:
            return False
        except Exception:
            return False
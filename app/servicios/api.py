import os
import json
from urllib import request, error

##
class ApiClient:
    def __init__(self, base_url: str | None = None, timeout: int = 10):
        self.base_url = (base_url or os.getenv("CLOUDPOS_API_BASE", "http://18.233.18.214:8000")).rstrip("/")
        self.timeout = timeout

    def _parse_body(self, raw: bytes):
        text = raw.decode("utf-8", errors="ignore")
        try:
            return json.loads(text)
        except Exception:
            return {"detail": text or "HTTP error"}

    def get_json(self, path: str):
        url = f"{self.base_url}/{path.replace('//','/').lstrip('/')}"
        req = request.Request(url, headers={"accept": "application/json"})
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8", errors="ignore"))
        except error.HTTPError as e:
            body = e.read() or b""
            parsed = self._parse_body(body) or {}
            msg = (
                (parsed.get("detail") if isinstance(parsed.get("detail"), str) else None)
                or parsed.get("message")
                or f"HTTP {e.code}"
            )
            raise RuntimeError(msg)
        except error.URLError as e:
            raise RuntimeError(getattr(e, "reason", "Error de red"))
##
    def post_json(self, path: str, payload: dict):
        url = f"{self.base_url}/{path.replace('//','/').lstrip('/')}"
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

    def put_json(self, path: str, payload: dict):
        """
        PUT JSON. Éxito -> JSON o texto; Error -> {'error': True, 'status': <code>, 'detail': '...'}
        """
        url = f"{self.base_url}/{path.replace('//','/').lstrip('/')}"
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url,
            data=data,
            headers={
                "accept": "application/json",
                "content-type": "application/json",
            },
            method="PUT",
        )
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

    def delete_json(self, path: str):
        """
        DELETE. Éxito -> JSON o texto; Error -> {'error': True, 'status': <code>, 'detail': '...'}
        """
        url = f"{self.base_url}/{path.replace('//','/').lstrip('/')}"
        req = request.Request(
            url,
            headers={
                "accept": "application/json",
            },
            method="DELETE",
        )
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


    def check_api(self) -> bool:
        try:
            url = f"{self.base_url}/"
            req = request.Request(url, headers={"accept": "application/json"})
            with request.urlopen(req, timeout=min(5, self.timeout)):
                return True
        except Exception:
            return False
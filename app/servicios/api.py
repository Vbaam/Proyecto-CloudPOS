import os
import json
from urllib import request


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
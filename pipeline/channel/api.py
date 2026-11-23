"""Cliente HTTP SOMENTE LEITURA para as APIs do YouTube (Data v3, Analytics v2, Reporting v1). So metodo GET e so os hosts do YouTube:
alterar/excluir/publicar nao e possivel por aqui (uploads ficam em tools/youtube_upload.sh e exigem ordem expressa do usuario)."""
import json, time, urllib.error, urllib.parse, urllib.request
from . import auth

ALLOWED = ("https://www.googleapis.com/youtube/", "https://youtubeanalytics.googleapis.com/", "https://youtubereporting.googleapis.com/")


class ApiError(RuntimeError):
    def __init__(self, code, msg, reason=""):
        super().__init__(f"HTTP {code} {reason}: {msg}")
        self.code, self.reason = code, reason


class Client:
    def __init__(self, token_fn=None):
        self.token_fn = token_fn or auth.access_token
        self.calls = 0

    def get(self, url, params=None, retries=3):
        if not url.startswith(ALLOWED):
            raise ValueError(f"host/rota nao permitido (cliente somente leitura): {url}")
        full = url + ("?" + urllib.parse.urlencode(params) if params else "")
        for k in range(retries):
            h = {"Accept": "application/json"}
            tok = self.token_fn()
            if tok:
                h["Authorization"] = "Bearer " + tok          # modo local; no modo proxy o proxy injeta o cabecalho
            try:
                with urllib.request.urlopen(urllib.request.Request(full, headers=h, method="GET"), timeout=60) as r:
                    self.calls += 1
                    return json.loads(r.read().decode())
            except urllib.error.HTTPError as e:
                body = e.read().decode()
                try:
                    j = json.loads(body)["error"]
                    reason = (j.get("errors") or [{}])[0].get("reason", "") or j.get("status", "")
                    msg = j.get("message", "")
                except Exception:
                    reason, msg = "", body[:200]
                if e.code in (429, 500, 502, 503) and k < retries - 1 and reason != "quotaExceeded":
                    time.sleep(3 * (k + 1)); continue
                raise ApiError(e.code, msg, reason)

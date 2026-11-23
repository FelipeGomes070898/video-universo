"""Autenticacao OAuth 2.0 oficial do Google, SOMENTE LEITURA. Nunca pede senha; nunca grava token dentro do repositorio.

Dois modos:
 1) proxy  (sessoes Claude Code na nuvem): o token e injetado pelo proxy do ambiente (ferramenta request_credential, host www.googleapis.com).
    Este codigo NAO ve nem grava o token. Nada a fazer aqui (access_token() devolve None e o cliente nao envia Authorization).
 2) local  (sua maquina): fluxo 'aplicativo instalado' com PKCE + servidor de retorno em 127.0.0.1. Voce cria no Google Cloud Console um
    cliente OAuth tipo 'App para computador', baixa o JSON e aponta VU_GOOGLE_CLIENT_FILE para ele (fora do repositorio).
    Token em ~/.config/video-universo/youtube_token.json (chmod 600). 'disconnect' revoga no Google e apaga o arquivo.
Escopos (so leitura): youtube.readonly + yt-analytics.readonly. (yt-analytics-monetary.readonly so com --monetary.)"""
import base64, hashlib, http.server, json, os, secrets, subprocess, sys, threading, time, urllib.parse, urllib.request

SCOPES_READ = ["https://www.googleapis.com/auth/youtube.readonly", "https://www.googleapis.com/auth/yt-analytics.readonly"]
SCOPE_MONETARY = "https://www.googleapis.com/auth/yt-analytics-monetary.readonly"
AUTH_URL, TOKEN_URL, REVOKE_URL = "https://accounts.google.com/o/oauth2/v2/auth", "https://oauth2.googleapis.com/token", "https://oauth2.googleapis.com/revoke"
CONF_DIR = os.environ.get("VU_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".config", "video-universo")
TOKEN_FILE = os.path.join(CONF_DIR, "youtube_token.json")
CLIENT_FILE = os.environ.get("VU_GOOGLE_CLIENT_FILE") or os.path.join(CONF_DIR, "client_secret.json")


class AuthError(RuntimeError):
    pass


def _inside_git_repo(path):
    d = os.path.abspath(path if os.path.isdir(path) else os.path.dirname(path))
    while d and not os.path.exists(os.path.join(d, ".git")):
        nd = os.path.dirname(d)
        if nd == d:
            return False
        d = nd
    return True


def _guard():
    for p in (TOKEN_FILE, CLIENT_FILE):
        if _inside_git_repo(os.path.dirname(p)):
            raise AuthError(f"{p} esta dentro de um repositorio git: tokens/credenciais NUNCA ficam no repositorio. Defina VU_CONFIG_DIR / VU_GOOGLE_CLIENT_FILE fora dele.")


def _post(url, data):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(), headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raise AuthError(f"{url} -> HTTP {e.code}: {e.read().decode()[:200]}")


def _client():
    if not os.path.exists(CLIENT_FILE):
        raise AuthError(f"cliente OAuth nao encontrado em {CLIENT_FILE}. Crie um 'App para computador' no Google Cloud Console (APIs: YouTube Data v3 e YouTube Analytics), baixe o JSON e aponte VU_GOOGLE_CLIENT_FILE.")
    j = json.load(open(CLIENT_FILE))
    c = j.get("installed") or j.get("web") or j
    return c["client_id"], c.get("client_secret", "")


def _save(tok):
    os.makedirs(CONF_DIR, exist_ok=True)
    tok["obtained_at"] = int(time.time())
    fd = os.open(TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(tok, f)
    os.chmod(TOKEN_FILE, 0o600)


def connect(monetary=False, open_browser=True):
    """Abre o consentimento do Google (voce escolhe a conta/canal). Salva o token so no seu computador."""
    _guard()
    cid, csec = _client()
    scopes = SCOPES_READ + ([SCOPE_MONETARY] if monetary else [])
    ver = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
    chal = base64.urlsafe_b64encode(hashlib.sha256(ver.encode()).digest()).rstrip(b"=").decode()
    state, got = secrets.token_urlsafe(16), {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            got.update({k: v[0] for k, v in q.items()})
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers()
            self.wfile.write("<h3>Conectado. Pode fechar esta aba e voltar ao terminal.</h3>".encode())
        def log_message(self, *a):
            pass
    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    redirect = f"http://127.0.0.1:{srv.server_port}"
    url = AUTH_URL + "?" + urllib.parse.urlencode(dict(client_id=cid, redirect_uri=redirect, response_type="code", scope=" ".join(scopes), state=state,
                                                       code_challenge=chal, code_challenge_method="S256", access_type="offline", prompt="consent"))
    print("Abra este link e autorize (somente leitura):\n", url)
    if open_browser:
        try:
            import webbrowser; webbrowser.open(url)
        except Exception:
            pass
    t = threading.Thread(target=srv.handle_request, daemon=True); t.start(); t.join(300)
    if got.get("state") != state or "code" not in got:
        raise AuthError("autorizacao nao concluida (tempo esgotado ou estado invalido)")
    tok = _post(TOKEN_URL, dict(code=got["code"], client_id=cid, client_secret=csec, redirect_uri=redirect, grant_type="authorization_code", code_verifier=ver))
    _save(tok)
    return status()


def refresh():
    _guard()
    tok = json.load(open(TOKEN_FILE))
    if "refresh_token" not in tok:
        raise AuthError("sem refresh_token: rode 'channel.py connect' de novo")
    cid, csec = _client()
    new = _post(TOKEN_URL, dict(client_id=cid, client_secret=csec, refresh_token=tok["refresh_token"], grant_type="refresh_token"))
    tok.update(new)
    _save(tok)
    return tok


def access_token():
    """Token local valido (renova se faltar < 60 s). None se nao ha token local (modo proxy)."""
    if not os.path.exists(TOKEN_FILE):
        return None
    tok = json.load(open(TOKEN_FILE))
    if time.time() > tok.get("obtained_at", 0) + tok.get("expires_in", 0) - 60:
        tok = refresh()
    return tok["access_token"]


def disconnect():
    """Revoga o acesso no Google e apaga o token local. (Tambem revogavel em myaccount.google.com/permissions.)"""
    if not os.path.exists(TOKEN_FILE):
        return {"disconnected": False, "motivo": "nao havia token local"}
    tok = json.load(open(TOKEN_FILE))
    ok = True
    try:
        _post(REVOKE_URL, dict(token=tok.get("refresh_token") or tok.get("access_token")))
    except AuthError:
        ok = False
    os.remove(TOKEN_FILE)
    return {"disconnected": True, "revogado_no_google": ok}


def status():
    if not os.path.exists(TOKEN_FILE):
        return {"modo": "proxy ou desconectado", "token_local": False}
    tok = json.load(open(TOKEN_FILE))
    exp = tok.get("obtained_at", 0) + tok.get("expires_in", 0)
    return {"modo": "local", "token_local": True, "escopos": tok.get("scope", "").split(), "access_expira_em_s": int(exp - time.time()), "tem_refresh_token": "refresh_token" in tok}

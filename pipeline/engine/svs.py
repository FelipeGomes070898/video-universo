"""NASA Scientific Visualization Studio (svs.gsfc.nasa.gov): busca, baixa e registra fonte/licenca/credito de visualizacoes e videos cientificos.
  python -m engine.svs search "enceladus" [-n 8]              lista itens (id, titulo, data)
  python -m engine.svs info 20384                              arquivos de midia do item (resolucao, URL)
  python -m engine.svs get 20384/OceanVents_web.mp4            baixa para assets/svs/<id>/ e imprime caminho + credito
Cena: media=[dict(src="svs:20384/OceanVents_web.mp4", at="#2", dur=8)]   (imagens e videos; media.py aplica zoom/pan/fade).
LICENCA/USO: material da NASA/SVS em geral e de dominio publico (o SVS pede CREDITO: 'Please give credit for this item to: ...'); itens com musica ou
arte de terceiros trazem aviso na pagina (ex.: 13693 tem musica licenciada: NAO usar o audio). Este modulo grava a frase de credito de cada item e o
build gera credits.txt. NASA nao endossa o video."""
import html, json, os, re, sys, urllib.parse, urllib.request

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "svs")
CREDIT_OVERRIDE = {"31271/Saturn_STScI-01H41MQX2YG2A1S99G86D74CD3.png": "NASA, ESA, CSA, STScI; M. Tiscareno (SETI), M. Hedman (U. Idaho), M. Showalter (SETI), L. Fletcher (U. Leicester), H. Hammel (AURA); processing J. DePasquale (STScI)"}
UA = {"User-Agent": "documentary-asset-research/1.0"}


def _get(url, timeout=120):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def search(q, n=8):
    j = json.loads(_get("https://svs.gsfc.nasa.gov/api/search/?search=" + urllib.parse.quote(q) + f"&limit={n}"))
    return [dict(id=r.get("id"), title=r.get("title", ""), date=(r.get("release_date") or "")[:10]) for r in (j.get("results") or [])[:n]]


def info(item_id):
    j = json.loads(_get(f"https://svs.gsfc.nasa.gov/api/{item_id}/"))
    files = []
    for g in j.get("media_groups", []):
        for it in g.get("items", []):
            m = it.get("instance") or {}
            u = m.get("url") or ""
            if u:
                files.append(dict(name=u.split("/")[-1], url=u, w=m.get("width"), h=m.get("height")))
    return j, files


def _credit(item_id):
    t = _get(f"https://svs.gsfc.nasa.gov/{item_id}/").decode("utf-8", "ignore")
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", t, flags=re.S)
    t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t)))
    m = re.search(r"Please give credit for this item to:\s*(.+?)(?:\s(?:Animator|Artist|Producer|Technical support|Writer|Scientist|Narrator|Support|Visualizer|Editor|Cover image|Video courtesy|Scientific consulting|Directed|Lead)\b|$)", t)
    return (m.group(1).strip()[:200] if m else "NASA's Scientific Visualization Studio")


def get(spec):
    """spec = '<id>/<arquivo>' -> dict(path, kind, credit, title, url, license)."""
    item_id, name = spec.split("/", 1)
    d = os.path.join(ROOT, item_id)
    meta_p = os.path.join(d, name + ".meta.json")
    if os.path.exists(meta_p):
        m = json.load(open(meta_p))
        if os.path.exists(m["path"]):
            return m
    os.makedirs(d, exist_ok=True)
    j, files = info(item_id)
    f = next((x for x in files if x["name"] == name), None)
    if not f:
        raise RuntimeError(f"{spec}: arquivo nao encontrado no item {item_id}")
    path = os.path.join(d, name)
    data = _get(f["url"].replace("http://", "https://"), timeout=600)
    with open(path, "wb") as fh:
        fh.write(data)
    kind = "video" if name.lower().endswith((".mp4", ".mov", ".webm")) else "image"
    m = dict(id=spec, path=path, kind=kind, title=j.get("title", ""), credit=CREDIT_OVERRIDE.get(spec) or _credit(item_id), url=f"https://svs.gsfc.nasa.gov/{item_id}/", width=f.get("w"), height=f.get("h"),
             license="NASA / dominio publico (credito solicitado pelo SVS)", released=(j.get("release_date") or "")[:10], bytes=len(data))
    json.dump(m, open(meta_p, "w"), indent=1)
    return m


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) >= 2 and a[0] == "search":
        for r in search(a[1], int(a[a.index("-n") + 1]) if "-n" in a else 8):
            print(f"{r['id']:<7} {r['date']}  {r['title'][:80]}")
    elif len(a) == 2 and a[0] == "info":
        j, fs = info(a[1])
        print(j.get("title"), "|", j.get("url"))
        for f in fs:
            print(f"  {f['w']}x{f['h']}  {f['name']}")
    elif len(a) == 2 and a[0] == "get":
        m = get(a[1]); print(m["path"], m["kind"], "|", m["credit"], "|", m["title"])
    else:
        print(__doc__)

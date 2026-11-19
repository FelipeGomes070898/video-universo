"""Acervo da NASA (NASA Image and Video Library, images.nasa.gov): busca e cache local de fotos e videos, com credito.
  python -m engine.nasa search "voyager jupiter ring" [--video] [-n 8]     lista candidatos (id, titulo, centro, data)
  python -m engine.nasa get PIA00452                                       baixa (foto ou video) e imprime o caminho local + credito
Uso nas cenas (scenes.py):  media=[dict(src="nasa:PIA00452", at="#2", dur=7, zoom=[1.0, 1.25])]
REGRAS: o material da NASA em geral nao tem copyright, mas (1) sempre dar credito ('Credit: NASA/JPL-Caltech'), (2) nao sugerir
apoio/endosso da NASA, (3) conferir 'secondary_creator'/'center' (alguns itens trazem terceiros) e (4) o texto vai na descricao do video."""
import json, os, re, sys, urllib.parse, urllib.request

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "nasa")
API = "https://images-api.nasa.gov"
UA = {"User-Agent": "space-video-engine/1.0"}


def _get(url, timeout=60):
    url = urllib.parse.quote(url, safe=":/%?=&~+,;@")
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def _json(url):
    return json.loads(_get(url).decode("utf-8"))


def search(q, video=False, n=8):
    url = f"{API}/search?q={urllib.parse.quote(q)}&media_type={'video' if video else 'image'}&page_size={n}"
    out = []
    for it in _json(url)["collection"]["items"][:n]:
        d = it["data"][0]
        out.append(dict(id=d["nasa_id"], title=d.get("title", ""), center=d.get("center", ""), date=(d.get("date_created") or "")[:10],
                        creator=d.get("secondary_creator", ""), desc=(d.get("description") or "")[:140]))
    return out


def _head(url):
    try:
        r = urllib.request.urlopen(urllib.request.Request(urllib.parse.quote(url, safe=":/%?=&~+,;@"), headers=UA, method="HEAD"), timeout=30)
        return int(r.headers.get("Content-Length", 0))
    except Exception:
        return 0


def get(nasa_id):
    """Baixa o melhor arquivo (foto orig/large ou video large/medium) para assets/nasa/<id>/ e devolve dict(path, kind, credit, title)."""
    d = os.path.join(ROOT, re.sub(r"[^A-Za-z0-9_.-]", "_", nasa_id))
    meta_p = os.path.join(d, "meta.json")
    if os.path.exists(meta_p):
        m = json.load(open(meta_p))
        if os.path.exists(m["path"]):
            return m
    os.makedirs(d, exist_ok=True)
    assets = _json(f"{API}/asset/{urllib.parse.quote(nasa_id)}")["collection"]["items"]
    urls = [a["href"].replace("http://", "https://") for a in assets]
    md = _json(f"{API}/search?nasa_id={urllib.parse.quote(nasa_id)}")["collection"]["items"][0]["data"][0]
    kind = "video" if md.get("media_type") == "video" else "image"
    if kind == "video":
        pref = ["~large.mp4", "~medium.mp4", "~mobile.mp4", "~small.mp4", "~orig.mp4"]
        cap = 350e6
    else:
        pref = ["~orig.jpg", "~large.jpg", "~medium.jpg", "~orig.png", "~large.png"]
        cap = 40e6
    pick, best = None, -1
    for u in urls:
        if any(u.lower().endswith(p_) for p_ in pref):
            sz = _head(u)
            if sz <= cap and (sz > best or (sz == 0 and best < 0)):
                pick, best = u, sz
    if not pick:
        raise RuntimeError(f"{nasa_id}: nenhum arquivo utilizavel em {urls[:4]}")
    path = os.path.join(d, os.path.basename(urllib.parse.urlparse(pick).path))
    data = _get(pick, timeout=900)
    with open(path, "wb") as f:
        f.write(data)
    sec, ctr = (md.get("secondary_creator") or "").strip(), (md.get("center") or "").strip()
    if sec.upper().startswith("NASA"):
        credit = "NASA/JPL-Caltech" if sec.upper() == "NASA/JPL" else sec
    elif ctr == "JPL":
        credit = "NASA/JPL-Caltech"
    else:
        credit = f"NASA/{ctr}" if ctr else "NASA"
    m = dict(id=nasa_id, path=path, kind=kind, title=md.get("title", ""), center=md.get("center", ""), credit=credit, date=(md.get("date_created") or "")[:10],
             url=f"https://images.nasa.gov/details/{nasa_id}", secondary_creator=md.get("secondary_creator", ""))
    json.dump(m, open(meta_p, "w"), indent=1)
    return m


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "search":
        n = 8
        if "-n" in sys.argv:
            n = int(sys.argv[sys.argv.index("-n") + 1])
        for r in search(sys.argv[2], video="--video" in sys.argv, n=n):
            print(f"{r['id']:<28} {r['date']}  {r['center']:<6} {r['title'][:60]}  | {r['creator']}")
    elif len(sys.argv) >= 3 and sys.argv[1] == "get":
        m = get(sys.argv[2])
        print(m["path"], m["kind"], "|", m["credit"], "|", m["title"])
    else:
        print(__doc__)

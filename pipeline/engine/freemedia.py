"""Fotos e VIDEOS REAIS livres (nao gerados): Openverse (Flickr/Wikimedia etc. com licenca), Wikimedia Commons (videos), Internet Archive (video PD).
  python -m engine.freemedia img "praca da se sao paulo aerial" [-n 12] [--sheet out.png]   lista/miniaturas (so licencas aceitas)
  python -m engine.freemedia vid "airplane flying above clouds" [-n 8]                       videos do Wikimedia Commons
  python -m engine.freemedia get ov:<id> | cm:<File:Nome.webm> | ia:<identifier>/<arquivo>   baixa para assets/free/ e imprime caminho+credito
Licencas aceitas: CC0, PDM (dominio publico), CC BY. (BY-SA so com --allow-sa; BY-NC/ND nunca.) O credito (titulo, autor, licenca, URL) vai para credits.txt
e aparece na tela. Cena: media=[dict(src="free:ov:<id>", at="#1", dur=8, zoom=[1, 1.25])]"""
import hashlib, json, os, re, sys, time, urllib.parse, urllib.request

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "free")
UA = {"User-Agent": "DocumentaryAssetFetcher/1.0 (educational video project)"}
OK_LIC = {"cc0", "pdm", "by"}


def _get(url, timeout=90, tries=4):
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except Exception as e:
            if k == tries - 1:
                raise
            time.sleep(4 * (k + 1))


def _j(url):
    return json.loads(_get(url).decode("utf-8"))


def search_images(q, n=12, allow_sa=False, ext="jpg,jpeg,png"):
    lic = ",".join(sorted(OK_LIC | ({"by-sa"} if allow_sa else set())))
    url = f"https://api.openverse.org/v1/images/?q={urllib.parse.quote(q)}&license={lic}&extension={ext}&page_size={min(n * 2, 20)}&mature=false"
    out = []
    for r in _j(url).get("results", []):
        if r["license"] not in (OK_LIC | ({"by-sa"} if allow_sa else set())):
            continue
        out.append(dict(id="ov:" + r["id"], title=r.get("title") or "", creator=r.get("creator") or "unknown", license=r["license"].upper() + (" " + (r.get("license_version") or "")),
                        url=r["url"], thumb=r.get("thumbnail"), landing=r.get("foreign_landing_url"), w=r.get("width"), h=r.get("height"), source=r.get("source")))
        if len(out) >= n:
            break
    return out


def search_videos(q, n=8):
    url = ("https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrnamespace=6&gsrlimit=%d&gsrsearch=%s&prop=imageinfo&iiprop=url|extmetadata|mime|size&format=json"
           % (n * 2, urllib.parse.quote(q + " filetype:video")))
    out = []
    for p in (_j(url).get("query", {}).get("pages", {}) or {}).values():
        ii = (p.get("imageinfo") or [{}])[0]
        md = ii.get("extmetadata", {})
        lic = (md.get("LicenseShortName", {}).get("value") or "").lower()
        okl = lic.startswith(("cc0", "public domain", "pd", "cc by 1", "cc by 2", "cc by 3", "cc by 4")) and "sa" not in lic and "nc" not in lic and "nd" not in lic
        if not okl or not ii.get("url"):
            continue
        out.append(dict(id="cm:" + p["title"], title=p["title"][5:], creator=re.sub(r"<[^>]+>", "", md.get("Artist", {}).get("value", "unknown")), license=md.get("LicenseShortName", {}).get("value", ""),
                        url=ii["url"], landing=ii.get("descriptionurl"), size=ii.get("size", 0)))
        if len(out) >= n:
            break
    return out


def get(aid):
    d = os.path.join(ROOT, hashlib.sha1(aid.encode()).hexdigest()[:12])
    mp = os.path.join(d, "meta.json")
    if os.path.exists(mp):
        m = json.load(open(mp))
        if os.path.exists(m["path"]):
            return m
    os.makedirs(d, exist_ok=True)
    kind, ref = aid.split(":", 1)
    if kind == "ov":
        r = _j(f"https://api.openverse.org/v1/images/{ref}/")
        url, kd = r["url"], "image"
        meta = dict(title=r.get("title") or "", creator=r.get("creator") or "unknown", license=(r["license"].upper() + " " + (r.get("license_version") or "")).strip(), landing=r.get("foreign_landing_url"))
    elif kind == "cm":
        info = _j("https://commons.wikimedia.org/w/api.php?action=query&titles=%s&prop=imageinfo&iiprop=url|extmetadata|mime&format=json" % urllib.parse.quote(ref))
        p = list(info["query"]["pages"].values())[0]
        ii = p["imageinfo"][0]
        md = ii.get("extmetadata", {})
        url, kd = ii["url"], ("video" if ii.get("mime", "").startswith(("video", "application/ogg")) else "image")
        meta = dict(title=ref[5:], creator=re.sub(r"<[^>]+>", "", md.get("Artist", {}).get("value", "unknown")), license=md.get("LicenseShortName", {}).get("value", ""), landing=ii.get("descriptionurl"))
    elif kind == "ia":
        ident, fname = ref.split("/", 1)
        md = _j(f"https://archive.org/metadata/{ident}")
        url, kd = f"https://archive.org/download/{ident}/{urllib.parse.quote(fname)}", "video"
        meta = dict(title=md.get("metadata", {}).get("title", ident), creator=str(md.get("metadata", {}).get("creator", "Internet Archive")), license=md.get("metadata", {}).get("licenseurl", "Public domain / Internet Archive"), landing=f"https://archive.org/details/{ident}")
    else:
        raise ValueError(aid)
    ext = os.path.splitext(urllib.parse.urlparse(url).path)[1] or (".mp4" if kd == "video" else ".jpg")
    path = os.path.join(d, "asset" + ext)
    data = _get(url, timeout=900)
    open(path, "wb").write(data)
    m = dict(id=aid, path=path, kind=kd, credit=f'{meta["creator"]} / {meta["license"]}', **meta)
    json.dump(m, open(mp, "w"), indent=1)
    return m


def sheet(items, out, cols=4, w=320):
    from PIL import Image, ImageDraw
    import io
    ims = []
    for i, it in enumerate(items):
        try:
            im = Image.open(io.BytesIO(_get(it["url"], timeout=40))).convert("RGB")
        except Exception:
            im = Image.new("RGB", (w, 180), (40, 40, 40))
        im.thumbnail((w, 220))
        c = Image.new("RGB", (w, 240), (0, 0, 0))
        c.paste(im, (0, 0))
        d = ImageDraw.Draw(c)
        d.text((3, 224), f'{i} {it["license"][:10]} {it["title"][:40]}', fill=(255, 255, 0))
        ims.append(c)
    rows = (len(ims) + cols - 1) // cols
    S = Image.new("RGB", (cols * w, rows * 240))
    for i, c in enumerate(ims):
        S.paste(c, ((i % cols) * w, (i // cols) * 240))
    S.save(out)


if __name__ == "__main__":
    a = sys.argv
    if len(a) >= 3 and a[1] in ("img", "vid"):
        n = int(a[a.index("-n") + 1]) if "-n" in a else 12
        res = search_images(a[2], n, "--allow-sa" in a) if a[1] == "img" else search_videos(a[2], n)
        for i, r in enumerate(res):
            print(i, r["id"], r["license"], "|", r["title"][:60], "|", r["creator"][:30], "|", r.get("w"), r.get("h"))
        if "--sheet" in a:
            sheet(res, a[a.index("--sheet") + 1])
    elif len(a) >= 3 and a[1] == "get":
        m = get(a[2])
        print(m["path"], m["kind"], "|", m["credit"])
    else:
        print(__doc__)

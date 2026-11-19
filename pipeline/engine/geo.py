"""GEOGRAFIA REAL: relevo (SRTM via AWS Terrain Tiles, dominio publico) + imagem (NASA GIBS Blue Marble) -> grade equirretangular em cache.
  python -m engine.geo build brasil_se       # baixa/monta assets/geo/brasil_se.npz
Coordenadas de cena em km: x = leste, z = SUL (para o mapa ficar com o norte para cima/longe da camera); origem (0,0) = canto noroeste."""
import io, math, os, urllib.request
import numpy as np
import cv2

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "geo")
UA = {"User-Agent": "space-video-engine/1.0"}
REGIONS = {"brasil_se": dict(lon=(-53.8, -33.6), lat=(-27.4, -8.0), N=2048, zdem=7, zimg=8)}
DEM = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
IMG = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_ShadedRelief_Bathymetry/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg"


def _tile(url, cache):
    if os.path.exists(cache) and os.path.getsize(cache) > 100:
        return open(cache, "rb").read()
    d = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    open(cache, "wb").write(d)
    return d


def _xy(lon, lat, z):
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def _mosaic(r, tpl, z, decode):
    x0, y1 = _xy(r["lon"][0], r["lat"][0], z)
    x1, y0 = _xy(r["lon"][1], r["lat"][1], z)
    tx0, tx1, ty0, ty1 = int(x0), int(x1), int(y0), int(y1)
    w, h = (tx1 - tx0 + 1) * 256, (ty1 - ty0 + 1) * 256
    ch = 3
    M = np.zeros((h, w, ch), np.float32 if decode else np.uint8)
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            u = tpl.format(z=z, x=tx, y=ty)
            data = _tile(u, os.path.join(ROOT, "tiles", "dem" if decode else "img", f"{z}_{tx}_{ty}.bin"))
            im = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)[..., ::-1]
            M[(ty - ty0) * 256:(ty - ty0 + 1) * 256, (tx - tx0) * 256:(tx - tx0 + 1) * 256] = im
    return M, (tx0, ty0)


def build(name):
    r = REGIONS[name]
    N = r["N"]
    out = {}
    lons = np.linspace(r["lon"][0], r["lon"][1], N)
    lats = np.linspace(r["lat"][1], r["lat"][0], N)                   # topo = norte
    for key, tpl, z, dec in (("dem", DEM, r["zdem"], True), ("rgb", IMG, r["zimg"], False)):
        M, (tx0, ty0) = _mosaic(r, tpl, z, dec)
        n = 2 ** z
        px = (lons[None, :] + 180.0) / 360.0 * n
        py = (1 - np.arcsinh(np.tan(np.radians(lats[:, None]))) / np.pi) / 2 * n
        mx = ((px - tx0) * 256).astype(np.float32) * np.ones((N, 1), np.float32)
        my = ((py - ty0) * 256).astype(np.float32) * np.ones((1, N), np.float32)
        R = cv2.remap(M, mx, my, cv2.INTER_LINEAR)
        out[key] = (R[..., 0] * 256.0 + R[..., 1] + R[..., 2] / 256.0 - 32768.0).astype(np.float32) if dec else R.astype(np.uint8)
    np.savez_compressed(os.path.join(ROOT, name + ".npz"), **out)
    return out


def earth_equirect(z=4):
    """Terra inteira (NASA Blue Marble, GIBS) reprojetada para equirretangular 4096x2048 -> assets/geo/earth_eq.jpg."""
    out = os.path.join(ROOT, "earth_eq.jpg")
    if not os.path.exists(out):
        n = 2 ** z
        M = np.zeros((n * 256, n * 256, 3), np.uint8)
        for ty in range(n):
            for tx in range(n):
                data = _tile(IMG.format(z=z, x=tx, y=ty), os.path.join(ROOT, "tiles", "img", f"{z}_{tx}_{ty}.bin"))
                M[ty * 256:(ty + 1) * 256, tx * 256:(tx + 1) * 256] = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)[..., ::-1]
        W_, H_ = 4096, 2048
        lat = np.linspace(85.0, -85.0, H_)
        lon = np.linspace(-180, 180, W_)
        py = ((1 - np.arcsinh(np.tan(np.radians(lat))) / np.pi) / 2 * n * 256).astype(np.float32)
        px = ((lon + 180) / 360 * n * 256).astype(np.float32)
        E = cv2.remap(M, np.tile(px[None, :], (H_, 1)), np.tile(py[:, None], (1, W_)), cv2.INTER_LINEAR)
        cv2.imwrite(out, E[..., ::-1], [cv2.IMWRITE_JPEG_QUALITY, 92])
    return out


def load(name):
    p = os.path.join(ROOT, name + ".npz")
    if not os.path.exists(p):
        build(name)
    return dict(np.load(p))


class Grid:
    """conversao lon/lat <-> km de cena para uma regiao."""
    def __init__(self, name):
        r = REGIONS[name]
        self.r, self.N = r, r["N"]
        self.lat0 = (r["lat"][0] + r["lat"][1]) / 2
        self.lon0 = (r["lon"][0] + r["lon"][1]) / 2
        self.kx = 111.32 * math.cos(math.radians(self.lat0))
        self.kz = 110.57
        self.sx = (r["lon"][1] - r["lon"][0]) * self.kx
        self.sz = (r["lat"][1] - r["lat"][0]) * self.kz
        self.size = max(self.sx, self.sz)

    def xz(self, lon, lat):
        return (lon - self.r["lon"][0]) * self.kx, (self.r["lat"][1] - lat) * self.kz   # x leste, z sul; (0,0) = canto noroeste (igual aos indices da imagem)

    def ij(self, lon, lat):
        r = self.r
        return (lon - r["lon"][0]) / (r["lon"][1] - r["lon"][0]) * (self.N - 1), (r["lat"][1] - lat) / (r["lat"][1] - r["lat"][0]) * (self.N - 1)


def haversine(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[1], a[0], b[1], b[0]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def great_circle(a, b, n=200):
    """a,b = (lon, lat) -> n pontos (lon, lat) ao longo do circulo maximo."""
    la1, lo1, la2, lo2 = map(math.radians, (a[1], a[0], b[1], b[0]))
    p1 = np.array([math.cos(la1) * math.cos(lo1), math.cos(la1) * math.sin(lo1), math.sin(la1)])
    p2 = np.array([math.cos(la2) * math.cos(lo2), math.cos(la2) * math.sin(lo2), math.sin(la2)])
    om = math.acos(np.clip(p1 @ p2, -1, 1))
    out = []
    for t in np.linspace(0, 1, n):
        p = (math.sin((1 - t) * om) * p1 + math.sin(t * om) * p2) / math.sin(om)
        out.append((math.degrees(math.atan2(p[1], p[0])), math.degrees(math.asin(p[2]))))
    return out


if __name__ == "__main__":
    import sys
    d = build(sys.argv[2])
    print({k: (v.shape, v.dtype, float(v.min()), float(v.max())) for k, v in d.items()})

"""Banco de dados do aprendizado (SQLite, fora do git: data/channel.db). Guarda snapshots do canal, metricas por video/janela, retencao, trafego,
geografia, demografia, disponibilidade de metricas e o REGISTRO DE CADA PRODUCAO (tema, roteiro, titulo, thumbnail, duracao, estrategia, desempenho,
pontos positivos, problemas, recomendacoes). `export_json`/`import_json` geram arquivos agregados versionaveis (analises/historico/), sem tokens."""
import json, os, sqlite3, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.environ.get("VU_DB") or os.path.join(os.path.dirname(ROOT), "data", "channel.db")
SCHEMA = """
CREATE TABLE IF NOT EXISTS channel(ts INTEGER, data TEXT);
CREATE TABLE IF NOT EXISTS videos(video_id TEXT PRIMARY KEY, title TEXT, description TEXT, published_at TEXT, duration_s REAL, thumb_url TEXT, tags TEXT,
  category TEXT, privacy TEXT, source TEXT DEFAULT 'api', last_sync INTEGER);
CREATE TABLE IF NOT EXISTS metrics(video_id TEXT, ts INTEGER, win TEXT, metric TEXT, value REAL, source TEXT DEFAULT 'api');
CREATE TABLE IF NOT EXISTS retention(video_id TEXT, ts INTEGER, ratio REAL, watch_ratio REAL, relative REAL);
CREATE TABLE IF NOT EXISTS traffic(video_id TEXT, ts INTEGER, source TEXT, views REAL, minutes REAL);
CREATE TABLE IF NOT EXISTS geo(video_id TEXT, ts INTEGER, country TEXT, views REAL);
CREATE TABLE IF NOT EXISTS demo(video_id TEXT, ts INTEGER, age TEXT, gender TEXT, pct REAL);
CREATE TABLE IF NOT EXISTS availability(video_id TEXT, ts INTEGER, what TEXT, status TEXT, note TEXT);
CREATE TABLE IF NOT EXISTS productions(slug TEXT PRIMARY KEY, video_id TEXT, theme TEXT, script_path TEXT, title TEXT, thumbnail_path TEXT, duration_s REAL,
  strategy TEXT, published_at TEXT, positives TEXT, problems TEXT, recommendations TEXT, created_ts INTEGER, updated_ts INTEGER);
CREATE TABLE IF NOT EXISTS analyses(ts INTEGER, kind TEXT, data TEXT);
CREATE INDEX IF NOT EXISTS ix_m ON metrics(video_id, win, metric, ts);
"""
TABLES = ["channel", "videos", "metrics", "retention", "traffic", "geo", "demo", "availability", "productions", "analyses"]


class Store:
    def __init__(self, path=None):
        self.path = path or DB_PATH
        if self.path != ":memory:":
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def q(self, sql, a=()):
        return [dict(r) for r in self.db.execute(sql, a).fetchall()]

    def add_channel(self, data, ts=None):
        self.db.execute("INSERT INTO channel VALUES(?,?)", (ts or int(time.time()), json.dumps(data, ensure_ascii=False))); self.db.commit()

    def upsert_video(self, v):
        cols = ["video_id", "title", "description", "published_at", "duration_s", "thumb_url", "tags", "category", "privacy", "source", "last_sync"]
        v = {**dict(source="api", last_sync=int(time.time())), **v}
        if isinstance(v.get("tags"), list):
            v["tags"] = json.dumps(v["tags"], ensure_ascii=False)
        self.db.execute(f"INSERT OR REPLACE INTO videos({','.join(cols)}) VALUES({','.join('?' * len(cols))})", [v.get(c) for c in cols]); self.db.commit()

    def add_metrics(self, vid, win, d, ts=None, source="api"):
        ts = ts or int(time.time())
        self.db.executemany("INSERT INTO metrics VALUES(?,?,?,?,?,?)", [(vid, ts, win, k, float(x), source) for k, x in d.items() if x is not None]); self.db.commit()

    def add_rows(self, table, vid, rows, ts=None):
        ts = ts or int(time.time())
        n = {"retention": 3, "traffic": 3, "geo": 2, "demo": 3}[table]
        self.db.executemany(f"INSERT INTO {table} VALUES(?,?,{','.join('?' * n)})", [(vid, ts, *r) for r in rows]); self.db.commit()

    def avail(self, vid, what, status, note="", ts=None):
        self.db.execute("INSERT INTO availability VALUES(?,?,?,?,?)", (vid, ts or int(time.time()), what, status, note[:300])); self.db.commit()

    def latest(self, vid, win="lifetime"):
        """metrica -> valor mais recente da janela."""
        out = {}
        for r in self.q("SELECT metric, value FROM metrics WHERE video_id=? AND win=? ORDER BY ts ASC, rowid ASC", (vid, win)):
            out[r["metric"]] = r["value"]
        return out

    def latest_rows(self, table, vid):
        t = self.q(f"SELECT MAX(ts) m FROM {table} WHERE video_id=?", (vid,))[0]["m"]
        return self.q(f"SELECT * FROM {table} WHERE video_id=? AND ts=?", (vid, t)) if t else []

    def register_production(self, slug, **kw):
        row = (self.q("SELECT * FROM productions WHERE slug=?", (slug,)) or [dict(slug=slug, created_ts=int(time.time()))])[0]
        row.update({k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v) for k, v in kw.items()})
        row["updated_ts"] = int(time.time())
        cols = ["slug", "video_id", "theme", "script_path", "title", "thumbnail_path", "duration_s", "strategy", "published_at", "positives", "problems", "recommendations", "created_ts", "updated_ts"]
        self.db.execute(f"INSERT OR REPLACE INTO productions({','.join(cols)}) VALUES({','.join('?' * len(cols))})", [row.get(c) for c in cols]); self.db.commit()

    def save_analysis(self, kind, data):
        self.db.execute("INSERT INTO analyses VALUES(?,?,?)", (int(time.time()), kind, json.dumps(data, ensure_ascii=False))); self.db.commit()

    # ---- historico versionavel (dados agregados do canal; sem tokens)
    def export_json(self, folder):
        os.makedirs(folder, exist_ok=True)
        for t in TABLES:
            json.dump(self.q(f"SELECT * FROM {t}"), open(os.path.join(folder, t + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    def import_json(self, folder):
        for t in TABLES:
            p = os.path.join(folder, t + ".json")
            if not os.path.exists(p):
                continue
            rows = json.load(open(p, encoding="utf-8"))
            if not rows:
                continue
            self.db.execute(f"DELETE FROM {t}")
            cols = list(rows[0].keys())
            self.db.executemany(f"INSERT INTO {t}({','.join(cols)}) VALUES({','.join('?' * len(cols))})", [[r[c] for c in cols] for r in rows])
        self.db.commit()

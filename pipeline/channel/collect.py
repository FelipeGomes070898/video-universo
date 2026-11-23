"""Coleta (SOMENTE LEITURA) via YouTube Data API v3 e YouTube Analytics API v2. Nao inventa metricas: toda consulta que a API recusar vira um
registro em `availability` (status 'indisponivel' + motivo) e fica fora das analises.
LIMITES (documentados pelo YouTube): Analytics tem granularidade DIARIA (24 h = dias 0-1 apos a publicacao, aproximado); retencao e CTR podem demorar
ate ~2 dias para aparecer; dados demograficos/geograficos so aparecem com volume minimo; Reporting API (relatorios em massa) nao e necessaria para
consultas por video e NAO foi implementada (pendente)."""
import datetime as dt
import re
from .api import ApiError

DATA = "https://www.googleapis.com/youtube/v3/"
ANA = "https://youtubeanalytics.googleapis.com/v2/reports"
CORE = "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained,subscribersLost,likes,comments,shares"
IMPR = "videoThumbnailImpressions,videoThumbnailImpressionsClickRate"     # existencia/semantica a confirmar com dados reais (ver BRIEF: pendente)


def iso_dur(s):
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    h, mi, se = (int(x or 0) for x in m.groups()) if m else (0, 0, 0)
    return h * 3600 + mi * 60 + se


def channel_info(c):
    j = c.get(DATA + "channels", dict(part="snippet,statistics,contentDetails,brandingSettings,status", mine="true"))
    it = j["items"][0]
    sn, st = it["snippet"], it.get("statistics", {})
    return dict(channel_id=it["id"], title=sn.get("title"), description=sn.get("description"), custom_url=sn.get("customUrl"), published_at=sn.get("publishedAt"),
                country=sn.get("country"), subscribers=int(st["subscriberCount"]) if "subscriberCount" in st else None,
                subscribers_hidden=st.get("hiddenSubscriberCount"), video_count=int(st.get("videoCount", 0)), view_count=int(st.get("viewCount", 0)),
                uploads_playlist=it["contentDetails"]["relatedPlaylists"]["uploads"], keywords=it.get("brandingSettings", {}).get("channel", {}).get("keywords"),
                privacy=it.get("status", {}).get("privacyStatus"))


def list_upload_ids(c, playlist, max_videos=200):
    ids, tok = [], None
    while len(ids) < max_videos:
        p = dict(part="contentDetails", playlistId=playlist, maxResults=50)
        if tok:
            p["pageToken"] = tok
        j = c.get(DATA + "playlistItems", p)
        ids += [i["contentDetails"]["videoId"] for i in j.get("items", [])]
        tok = j.get("nextPageToken")
        if not tok:
            break
    return ids[:max_videos]


def video_details(c, ids):
    out = []
    for k in range(0, len(ids), 50):
        j = c.get(DATA + "videos", dict(part="snippet,contentDetails,statistics,status", id=",".join(ids[k:k + 50])))
        for it in j.get("items", []):
            sn, st = it["snippet"], it.get("statistics", {})
            th = sn.get("thumbnails", {})
            url = (th.get("maxres") or th.get("standard") or th.get("high") or th.get("default") or {}).get("url")
            out.append(dict(video=dict(video_id=it["id"], title=sn["title"], description=sn.get("description", ""), published_at=sn["publishedAt"],
                                       duration_s=iso_dur(it["contentDetails"]["duration"]), thumb_url=url, tags=sn.get("tags", []), category=sn.get("categoryId"),
                                       privacy=it.get("status", {}).get("privacyStatus")),
                            stats={k_: float(st[k_]) for k_ in ("viewCount", "likeCount", "commentCount") if k_ in st}))
    return out


def _rows(j):
    names = [h["name"] for h in j.get("columnHeaders", [])]
    return [dict(zip(names, r)) for r in j.get("rows", [])]


def _q(c, st, vid, what, **p):
    """consulta Analytics; em erro registra indisponibilidade e devolve None."""
    base = dict(ids="channel==MINE", filters=f"video=={vid}")
    base.update(p)
    try:
        return _rows(c.get(ANA, base))
    except ApiError as e:
        st.avail(vid, what, "indisponivel", f"{e.code} {e.reason}: {e}")
        return None


def collect_video(c, st, vid, published_at, duration_s, today=None):
    today = today or dt.date.today()
    start = published_at[:10]
    end = today.isoformat()
    life = _q(c, st, vid, "core", startDate=start, endDate=end, metrics=CORE)
    if life:
        st.add_metrics(vid, "lifetime", {k: v for k, v in life[0].items() if v is not None})
    imp = _q(c, st, vid, "impressoes_ctr", startDate=start, endDate=end, metrics=IMPR)
    if imp:
        r = imp[0]
        ctr = r.get("videoThumbnailImpressionsClickRate")
        if ctr is not None and ctr > 1:
            ctr = ctr / 100.0                                   # normaliza porcentagem -> fracao (a confirmar com dados reais)
        st.add_metrics(vid, "lifetime", {"impressions": r.get("videoThumbnailImpressions"), "ctr": ctr})
    day = _q(c, st, vid, "serie_diaria", startDate=start, endDate=end, dimensions="day", sort="day", metrics="views,estimatedMinutesWatched,subscribersGained")
    if day:
        p0 = dt.date.fromisoformat(start)
        for win, n in (("d1", 2), ("d7", 7), ("d28", 28)):         # d1 = dias 0-1 (24 h aproximado; a API e diaria)
            sel = [r for r in day if (dt.date.fromisoformat(r["day"]) - p0).days < n]
            if sel and (today - p0).days >= n - 1:
                st.add_metrics(vid, win, {m: sum(r.get(m) or 0 for r in sel) for m in ("views", "estimatedMinutesWatched", "subscribersGained")})
        tot = sum(r.get("views") or 0 for r in day)
        late = sum(r.get("views") or 0 for r in day if (dt.date.fromisoformat(r["day"]) - p0).days >= 28)
        if tot:
            st.add_metrics(vid, "lifetime", {"views_after_day28_share": late / tot, "days_with_data": len(day)})
    ret = _q(c, st, vid, "retencao", startDate=start, endDate=end, dimensions="elapsedVideoTimeRatio", sort="elapsedVideoTimeRatio", metrics="audienceWatchRatio,relativeRetentionPerformance")
    if ret:
        st.add_rows("retention", vid, [(r["elapsedVideoTimeRatio"], r.get("audienceWatchRatio"), r.get("relativeRetentionPerformance")) for r in ret])
    tr = _q(c, st, vid, "fontes_de_trafego", startDate=start, endDate=end, dimensions="insightTrafficSourceType", sort="-views", metrics="views,estimatedMinutesWatched")
    if tr:
        st.add_rows("traffic", vid, [(r["insightTrafficSourceType"], r.get("views"), r.get("estimatedMinutesWatched")) for r in tr])
    ge = _q(c, st, vid, "geografia", startDate=start, endDate=end, dimensions="country", sort="-views", maxResults=25, metrics="views")
    if ge:
        st.add_rows("geo", vid, [(r["country"], r.get("views")) for r in ge])
    de = _q(c, st, vid, "demografia", startDate=start, endDate=end, dimensions="ageGroup,gender", metrics="viewerPercentage")
    if de:
        st.add_rows("demo", vid, [(r["ageGroup"], r["gender"], r.get("viewerPercentage")) for r in de])


def sync(c, st, max_videos=100, today=None):
    ch = channel_info(c)
    st.add_channel(ch)
    ids = list_upload_ids(c, ch["uploads_playlist"], max_videos)
    n = 0
    for d in video_details(c, ids):
        v = d["video"]
        st.upsert_video(v)
        st.add_metrics(v["video_id"], "public", {"views": d["stats"].get("viewCount"), "likes": d["stats"].get("likeCount"), "comments": d["stats"].get("commentCount")})
        collect_video(c, st, v["video_id"], v["published_at"], v["duration_s"], today)
        n += 1
    return dict(channel=ch["title"], subscribers=ch["subscribers"], videos=n, api_calls=c.calls)

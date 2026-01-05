# BUILD: 26-01-05 v462 (NEWS BOX: auto refresh only + countdown + smaller font + ranking + top1 glow)
# BASE: user's v459 (center notice EN) + v461 (news box in left blank area)
# RULE: Do NOT touch other UI/layout. ONLY modify NEWS box section.

from flask import Flask, render_template_string, request, redirect, make_response, jsonify
import requests, re, time, uuid, hashlib
from datetime import datetime, timezone
from urllib.parse import quote_plus
import xml.etree.ElementTree as ET


app = Flask(__name__)
HEADERS = {"User-Agent": "Mozilla/5.0"}
COOKIE_NAME = "vsr_uid"

# -----------------------------
# News cache (server memory)
# -----------------------------
NEWS_CACHE = {"ts": 0.0, "items": []}
NEWS_TTL_SEC = 180  # 3 min server fetch cache; client can refresh UI every 60s

# Google News RSS feeds (English)
NEWS_FEEDS = [
    "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=viral&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=meme&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=breaking%20news&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=AI&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=crypto&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=solana&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=pump.fun&hl=en-US&gl=US&ceid=US:en",
]

def safe_text(x: str) -> str:
    return (x or "").strip()

def normalize_title_key(title: str) -> str:
    t = title.lower()
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    toks = [w for w in t.split() if w]
    return " ".join(toks[:9])

def parse_rfc822_to_ts(dt_str: str) -> float:
    try:
        from email.utils import parsedate_to_datetime
        d = parsedate_to_datetime(dt_str)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.timestamp()
    except Exception:
        return time.time()

def fetch_rss_items(url: str, timeout=8):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        xml = r.text
    except Exception:
        return []

    items = []
    try:
        root = ET.fromstring(xml)
        channel = root.find("channel")
        if channel is None:
            return []

        for it in channel.findall("item"):
            title = safe_text(it.findtext("title"))
            link = safe_text(it.findtext("link"))
            pub = safe_text(it.findtext("pubDate"))

            publisher = ""
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                if len(parts) == 2:
                    title_clean = parts[0].strip()
                    publisher = parts[1].strip()
                else:
                    title_clean = title
            else:
                title_clean = title

            items.append({
                "title": title_clean or title,
                "publisher": publisher,
                "link": link,
                "pub_ts": parse_rfc822_to_ts(pub) if pub else time.time(),
            })
    except Exception:
        return []

    return items

def build_ranked_news(limit=7):
    raw = []
    for feed in NEWS_FEEDS:
        raw.extend(fetch_rss_items(feed))

    if not raw:
        return []

    clusters = {}
    for x in raw:
        key = normalize_title_key(x["title"])
        if not key:
            continue

        c = clusters.get(key)
        if not c:
            c = {
                "title": x["title"],
                "pub_ts": x["pub_ts"],
                "publishers": set([x["publisher"] or ""]),
                "mentions": 1,
            }
            clusters[key] = c
        else:
            c["mentions"] += 1
            if x["pub_ts"] > c["pub_ts"]:
                c["pub_ts"] = x["pub_ts"]
                c["title"] = x["title"]
            c["publishers"].add(x["publisher"] or "")

    ranked = []
    now_ts = time.time()
    for _, c in clusters.items():
        pub_set = set([p for p in c["publishers"] if p])
        unique_sources = max(len(pub_set), 1)
        mentions = c["mentions"]

        age_hours = max((now_ts - c["pub_ts"]) / 3600.0, 0.0)
        recency = max(0.0, 24.0 - age_hours)

        score = (8 * unique_sources) + (3 * mentions) + recency
        ranked.append({
            "title": c["title"],
            "sources": unique_sources,
            "mentions": mentions,
            "pub_ts": c["pub_ts"],
            "score": round(score, 2),
            "q": quote_plus(c["title"]),
        })

    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked[:limit]

def get_ranked_news_cached():
    if time.time() - NEWS_CACHE["ts"] < NEWS_TTL_SEC and NEWS_CACHE["items"]:
        return NEWS_CACHE["items"]
    items = build_ranked_news(limit=7)
    NEWS_CACHE["ts"] = time.time()
    NEWS_CACHE["items"] = items
    return items

@app.get("/api/news")
def api_news():
    items = get_ranked_news_cached()
    return jsonify({"ok": True, "items": items})

@app.get("/api/pump_pack")
def api_pump_pack():
    vid = request.args.get("vid", "").strip()
    if not vid:
        return jsonify({"ok": False, "error": "missing vid"}), 400

    url = f"https://www.youtube.com/shorts/{vid}"
    thumb = f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"

    seed = int(hashlib.sha256(vid.encode()).hexdigest()[:8], 16)
    adjs = ["Viral", "Neon", "Turbo", "Prime", "Hyper"]
    nouns = ["Capsule", "Coin", "Wave", "Clip", "Buzz"]
    name = f"{adjs[seed % len(adjs)]}{nouns[(seed // 3) % len(nouns)]}"
    ticker = hashlib.md5(vid.encode()).hexdigest().upper()[:4]

    desc = (
        f"{name} (${ticker}) — minted from today’s viral short.\n"
        f"Source: {url}\n"
        f"No roadmap. Just vibes."
    )

    return jsonify({
        "ok": True,
        "vid": vid,
        "name": name,
        "ticker": ticker,
        "description": desc,
        "source_url": url,
        "thumb": thumb
    })

# -----------------------------
# Shorts collection
# -----------------------------
def extract_ids(html: str):
    return re.findall(r"/shorts/([a-zA-Z0-9_-]{11})", html)

def fetch_html(url: str):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.text
    except Exception:
        return ""

def build_daily_videos(limit: int = 12):
    ids = []
    sources = [
        "https://www.youtube.com/shorts",
        "https://www.youtube.com/results?search_query=viral+shorts",
        "https://www.youtube.com/results?search_query=trending+shorts",
        "https://www.youtube.com/results?search_query=meme+shorts",
    ]
    for url in sources:
        html = fetch_html(url)
        if not html:
            continue
        for vid in extract_ids(html):
            if vid not in ids:
                ids.append(vid)
            if len(ids) >= limit:
                break
        if len(ids) >= limit:
            break

    now = time.time()
    videos = {}
    for vid in ids[:limit]:
        videos[vid] = {
            "id": vid,
            "url": f"https://www.youtube.com/shorts/{vid}",
            "thumb": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
            "first_seen": now,
        }
    return videos

# -----------------------------
# Daily reset at UTC 00:00
# -----------------------------
def utc_midnight_ts():
    now = datetime.now(timezone.utc)
    return datetime(now.year, now.month, now.day, tzinfo=timezone.utc).timestamp()

DAY_START_TS = utc_midnight_ts()
VIDEOS = build_daily_videos(limit=12)
USERS = {}

# -----------------------------
# Visitors (server-memory)
# - Total: never reset
# - Today: reset at UTC 00:00
# -----------------------------
VISITOR_UIDS_TOTAL = set()
VISITOR_TOTAL = 0
VISITOR_UIDS_TODAY = set()
VISITOR_TODAY = 0

def ensure_daily_reset():
    global VIDEOS, USERS, DAY_START_TS
    global VISITOR_UIDS_TODAY, VISITOR_TODAY

    if time.time() - DAY_START_TS >= 86400:
        VIDEOS = build_daily_videos(limit=12)
        USERS = {}
        DAY_START_TS = utc_midnight_ts()
        VISITOR_UIDS_TODAY = set()
        VISITOR_TODAY = 0

def track_visit(uid: str):
    global VISITOR_TOTAL, VISITOR_TODAY
    if uid not in VISITOR_UIDS_TOTAL:
        VISITOR_UIDS_TOTAL.add(uid)
        VISITOR_TOTAL += 1
    if uid not in VISITOR_UIDS_TODAY:
        VISITOR_UIDS_TODAY.add(uid)
        VISITOR_TODAY += 1

# -----------------------------
# User helpers
# -----------------------------
def get_uid():
    return request.cookies.get(COOKIE_NAME) or uuid.uuid4().hex

def get_user(uid: str):
    if uid not in USERS:
        USERS[uid] = {"points": 1000, "boosts": {}}
    return USERS[uid]

# -----------------------------
# Scoring / ranking
# -----------------------------
def total_boosts(vid: str) -> int:
    return sum(u["boosts"].get(vid, 0) for u in USERS.values())

def viral_score(vid: str) -> float:
    base = 30
    boost_score = total_boosts(vid) * 50
    age_hours = max((time.time() - VIDEOS[vid]["first_seen"]) / 3600, 1)
    time_score = max(40 - age_hours, 0)
    return round(base + boost_score + time_score, 1)

def build_view_model(uid: str):
    me = get_user(uid)

    items = []
    for vid, meta in VIDEOS.items():
        my_boost = me["boosts"].get(vid, 0)
        tot = total_boosts(vid)
        score = viral_score(vid)
        items.append({
            "id": vid,
            "url": meta["url"],
            "thumb": meta["thumb"],
            "my_boost": my_boost,
            "total_boost": tot,
            "score": score,
        })

    items.sort(key=lambda x: x["score"], reverse=True)
    for i, it in enumerate(items, start=1):
        it["rank"] = i

    winner = items[0] if items else None
    return me, items, winner


# -----------------------------
# UI (kept) + NEWS-only changes
# -----------------------------
HTML = r"""
<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Viral Shorts Radar</title>
<style>
:root{
  --bg:#0f0f0f; --card:#1a1a1a; --muted:#aaa; --accent:#00ffcc;
  --hot:#ff3300; --boost:#ff6600; --gold:#ffcc00; --pill:#222;
}
body { background:var(--bg); color:white; font-family:Arial; padding:28px; margin:0; }
a { color:var(--accent); text-decoration:none; }
.container { max-width:1100px; margin:0 auto; }
.nav{ position:relative; }
.brand{ position:absolute; left:50%; transform:translateX(-50%); }
.brand{ top: calc(50% + 16px); }
.nav-right{ margin-left:auto; }

.nav{
  display:flex; justify-content:space-between; align-items:center;
  gap:12px; padding:14px 0 6px 0;
}

.brand{ font-weight:900; letter-spacing:.3px; font-size:36px; }
.brand span{ color:var(--accent); }

.nav-right{ display:flex; gap:10px; align-items:center; flex-wrap:wrap; }
.chip{
  background:var(--pill); color:#ddd; padding:8px 12px; border-radius:999px;
  font-size:13px;
}
.btn{
  background:var(--accent); color:#00110c; font-weight:900;
  padding:9px 12px; border-radius:999px; border:0; cursor:pointer;
}
.btn.secondary{ background:#2a2a2a; color:#fff; font-weight:800; }

.hero{ padding:22px 0 10px 0; text-align:center; position:relative; }
.h-title{ font-size:15px; line-height:1.05; margin:18px 0 10px 0; }
.h-title .accent{ color:var(--accent); }
.h-sub{ color:var(--muted); font-size:15px; max-width:760px; margin:0 auto; }
.cta{ margin-top:16px; display:flex; justify-content:center; gap:10px; flex-wrap:wrap; }
.smallnote{ margin-top:10px; color:#777; font-size:12px; }

.countdown-wrap{
  margin-top:12px;
  display:flex;
  justify-content:center;
}
.countdown{
  background:#121212;
  border:1px solid #202020;
  border-radius:999px;
  padding:10px 16px;
  font-weight:900;
  letter-spacing:.6px;
  display:flex;
  gap:10px;
  align-items:center;
}
.countdown span.label{ color:#9beee0; font-size:12px; font-weight:900; text-transform:uppercase; }
.countdown b.time{
  color:var(--accent);
  font-size:18px;
}

.panel{ background:var(--card); border-radius:18px; padding:16px; margin:18px 0; }
.panel h2{ margin:0 0 10px 0; font-size:18px; text-align:center; }
.kpis{ display:flex; gap:10px; justify-content:center; flex-wrap:wrap; margin-top:12px; }
.pill{ background:var(--pill); color:#ddd; padding:8px 14px; border-radius:999px; font-size:13px; }

.grid{
  display:grid;
  grid-template-columns:repeat(auto-fill,minmax(240px,1fr));
  gap:16px;
  margin:18px 0 30px 0;
}
.card{
  background:var(--card);
  border-radius:16px;
  padding:12px;
  text-align:center;
  position:relative;
  transition:transform .15s ease, box-shadow .15s ease;
}
.card:hover{ transform:translateY(-4px); }

.boosted{ box-shadow:0 0 18px rgba(255,204,0,0.45); border:2px solid rgba(255,204,0,0.35); }
.badge{
  position:absolute; top:10px; left:10px;
  padding:5px 9px; border-radius:999px;
  font-size:12px; font-weight:900;
}
.badge.boosted{ background:var(--gold); color:#111; border:0; box-shadow:none; }
.badge.hot{ background:var(--hot); color:#fff; left:auto; right:10px; }
.badge.winner{ background:var(--accent); color:#00110c; left:auto; right:10px; top:auto; bottom:10px; }

.thumb{ width:100%; border-radius:12px; display:block; }
.titlelink{ display:block; margin-top:8px; font-weight:900; text-align:center; }
.meta{ margin-top:6px; color:var(--muted); font-size:12px; text-align:center; }
.score{ margin-top:6px; color:var(--accent); font-weight:900; text-align:center; }

form{ margin:0; }
.boost-btn{
  margin-top:8px;
  padding:9px 12px;
  border-radius:999px;
  border:0;
  cursor:pointer;
  font-weight:900;
  background:var(--boost);
  color:white;
  animation:pulse 1.6s infinite;
}
.boost-btn:active{ transform:scale(.98); }

@keyframes pulse{
  0%{ box-shadow:0 0 0 0 rgba(255,102,0,.7); }
  70%{ box-shadow:0 0 0 10px rgba(255,102,0,0); }
  100%{ box-shadow:0 0 0 0 rgba(255,102,0,0); }
}

.how{
  display:grid;
  grid-template-columns:repeat(auto-fit,minmax(240px,1fr));
  gap:12px;
}
.how .step{ background:#161616; border-radius:16px; padding:14px; }
.step p{ margin:8px 0 0 0; color:var(--muted); font-size:13px; line-height:1.45; }

.footer{ margin:28px 0 20px 0; text-align:center; color:#666; font-size:12px; }
hr.sep{ border:0; border-top:1px solid #232323; margin:16px 0; }

.how.leader-steps{
  display:flex;
  flex-direction:column;
  align-items:flex-end;
  gap:14px;
}
.how.leader-steps .step{
  width:240px;
  max-width:100%;
  min-height:94px;
  display:flex;
  flex-direction:column;
  justify-content:center;
}

/* TODAY'S LEADER LAYOUT (kept) */
.leaderGrid{ position: relative; display: block; }
.leaderLeft{ width: 100%; display: flex; justify-content: center; }
.leaderVideo{ width: min(420px, 100%); text-align: center; }
.leaderRight{
  position: absolute;
  right: 16px;
  top: 50%;
  transform: translateY(-50%);
  width: 260px;
  text-align: center !important;
}
.leaderVideo .titlelink,
.leaderVideo .meta,
.leaderVideo .score{
  display: block;
  text-align: center;
}
.leaderVideo .meta,
.leaderVideo .score{
  line-height: 1.4;
}
.leaderRight > *{ text-align: center !important; }
.leaderRight .card,
.leaderRight .miniCard,
.leaderRight .box,
.leaderRight .pill{
  display: flex;
  flex-direction: column;
  align-items: center;
}
.how{ text-align: center; }
.how .step{ text-align: center; }
.how .step h3,
.how .step h4,
.how .step p{ text-align: center; }
.how .step strong,
.how .step span{
  display: block;
  text-align: center;
}

.btn.secondary.pump{
  background: linear-gradient(135deg,#22c55e,#4ade80);
  color:#0b1f12;
  border: none;
  box-shadow:
    0 0 0 1px rgba(34,197,94,.25) inset,
    0 6px 18px rgba(34,197,94,.35);
}
.btn.secondary.pump:hover{
  background: linear-gradient(135deg,#16a34a,#22c55e);
  box-shadow:
    0 0 0 1px rgba(34,197,94,.35) inset,
    0 10px 26px rgba(34,197,94,.5);
}
.btn.secondary.pump:active{ transform: translateY(1px); }

@media (max-width:900px){
  .leaderGrid{ grid-template-columns: 1fr; }
  .leaderRight{ justify-content:center; position:static; transform:none; width:auto; margin-top:14px; }
}
@media (max-width:520px){
  body{ padding:18px; }
  .h-title{ font-size:32px; }
  .brand{ font-size:22px; }
}

/* Visitors overlay (kept) */
.visitorsOverlay{
  position:absolute;
  right: 6px;
  top: 8px;
  display:flex;
  flex-direction:column;
  gap:8px;
  align-items:flex-end;
  pointer-events:none;
}
.visitorsOverlay .chip{ pointer-events:auto; }

/* Center notice (kept) */
.centerNotice{
  position:fixed;
  left:50%;
  top:50%;
  transform:translate(-50%, -50%);
  background:rgba(18,18,18,.94);
  border:1px solid #2a2a2a;
  color:#fff;
  padding:14px 16px;
  border-radius:14px;
  box-shadow:0 18px 60px rgba(0,0,0,.55);
  z-index:10001;
  display:none;
  min-width:min(420px, 92vw);
  text-align:center;
  font-weight:900;
}
.centerNotice.show{ display:block; }
.centerNotice .sub{
  margin-top:6px;
  font-weight:700;
  color:#bdbdbd;
  font-size:12px;
}

/* ============================
   ✅ NEWS BOX (ONLY CHANGES BELOW)
   - keep SAME position/shape/colors
   - ONLY: make the inside fit + scroll + slightly smaller font
   ============================ */
.leaderNews{
  position:absolute;
  left:16px;
  top:50%;
  transform:translateY(-50%);
  width:260px;
  text-align:center !important;
}

/* ✅ 핵심: 뉴스 카드(step) 자체가 패널 밖으로 길어지지 않게 "고정 높이 + 내부만 스크롤" */
.leaderNews .step{
  width:240px;
  max-width:100%;
  text-align:center;
  position:relative;

  /* NEW (fit inside panel) */
  max-height: 520px;   /* 패널 안에 들어가게 제한 */
  overflow: hidden;    /* step 밖으로 튀는 것 방지 */
}

.newsTopRow{
  display:flex;
  align-items:center;
  justify-content:center;
  gap:8px;
}
.newsRefresh{
  margin-top:8px;
  color:#888;
  font-size:10px;    /* 11 -> 10 (slightly smaller) */
  font-weight:800;
}

/* ✅ 리스트만 스크롤 */
.newsList{
  display:flex;
  flex-direction:column;
  gap:10px;
  margin-top:10px;

  /* NEW (scroll inside box) */
  max-height: 410px;  /* step 안에서 위아래 스크롤 */
  overflow-y: auto;
  padding-right: 6px;
}

.newsItem{
  background:#161616;
  border-radius:16px;
  padding:10px 10px 10px 10px;
  text-align:center;
  position:relative;
  overflow:hidden;
}

.newsRank{
  position:absolute;
  left:10px;
  top:10px;
  width:20px;
  height:20px;
  border-radius:6px;
  background:#2a2a2a;
  color:#fff;
  font-weight:900;
  font-size:10px;   /* 11 -> 10 */
  display:flex;
  align-items:center;
  justify-content:center;
}

.newsItem a{
  color:#fff;
  font-weight:900;
  display:block;
  line-height:1.22;  /* 1.25 -> 1.22 */
  font-size:11px;    /* 12 -> 11 */
  padding:0 6px 0 28px; /* leave space for rank */
}

.newsMeta{
  margin-top:6px;
  color:var(--muted);
  font-size:10px;    /* 11 -> 10 */
  padding-left:28px; /* align with title */
}

.newsHint{
  margin-top:8px;
  color:#777;
  font-size:10px;    /* 11 -> 10 */
}

/* ✅ Top #1: burning glow + flicker (unchanged) */
.newsItem.top1{
  border:1px solid rgba(255,102,0,.55);
  box-shadow:0 0 18px rgba(255,102,0,.35);
  animation:newsFlicker 1.15s infinite;
}
.newsItem.top1::before{
  content:"";
  position:absolute;
  left:-40%;
  top:-60%;
  width:180%;
  height:220%;
  background:radial-gradient(circle at 50% 70%, rgba(255,102,0,.35), rgba(255,51,0,.18), rgba(0,0,0,0) 60%);
  transform:rotate(8deg);
  filter:blur(10px);
  opacity:.9;
  pointer-events:none;
  animation:newsHeat 1.25s infinite;
}
.newsItem.top1 .newsRank{
  background:linear-gradient(135deg,#ff3300,#ffcc00);
  color:#111;
  box-shadow:0 0 12px rgba(255,153,0,.55);
}

@keyframes newsFlicker{
  0%{ box-shadow:0 0 14px rgba(255,102,0,.28); transform:translateY(0); }
  35%{ box-shadow:0 0 22px rgba(255,102,0,.48); transform:translateY(-1px); }
  70%{ box-shadow:0 0 16px rgba(255,102,0,.30); transform:translateY(0); }
  100%{ box-shadow:0 0 20px rgba(255,102,0,.40); transform:translateY(-1px); }
}
@keyframes newsHeat{
  0%{ transform:rotate(8deg) translateY(0); opacity:.75; }
  50%{ transform:rotate(8deg) translateY(6px); opacity:.95; }
  100%{ transform:rotate(8deg) translateY(0); opacity:.80; }
}

@media (max-width:900px){
  .leaderNews{
    position:static;
    transform:none;
    width:auto;
    margin-bottom:14px;
  }
  .leaderNews .step{ margin:0 auto; max-height:none; overflow:visible; }
  .newsList{ max-height: 360px; }
}
</style>
</head>
<body>
<div class="container">

  <div class="nav">
    <div class="brand">Viral<span>Radar</span></div>
    <div class="nav-right">
      <div class="chip">Reset: <b>00:00 UTC</b></div>
      <div class="chip">Points: <b>{{ my_points }}</b></div>
      <button class="btn secondary" onclick="document.getElementById('how').scrollIntoView({behavior:'smooth'});">How it works</button>
      <button class="btn" onclick="alert('Wallet connect coming next.\\nWe will keep this smooth & cheap (Solana).');">Connect Wallet</button>
    </div>
  </div>

  <div class="hero">
    <div class="visitorsOverlay" aria-label="Visitors">
      <div class="chip">Today: <b>{{ visitors_today }}</b></div>
      <div class="chip">Total: <b>{{ visitors_total }}</b></div>
    </div>

    <div class="h-title">Boost what goes <span class="accent">viral</span>.</div>
    <div class="h-sub">
      A daily radar of trending Shorts — boosted by the community.
      Spend points now, plug in the token later. Same UX.
    </div>
    <div class="cta">
      <button class="btn" onclick="document.getElementById('feed').scrollIntoView({behavior:'smooth'});">Enter the Feed</button>
      <button class="btn secondary" onclick="alert('Token utility (draft):\\nBOOST = burn-to-boost attention.\\nBoost 100 -> 70% burn / 20% creator pool / 10% ops.');">Token Draft</button>
    </div>
    <div class="smallnote">MVP: server restart = new day. Daily reset at 00:00 UTC.</div>

    <div class="countdown-wrap">
      <div class="countdown">
        <span class="label">RESET IN</span>
        <b class="time" id="resetCountdownHero">--:--:--</b>
        <span style="color:#777; font-size:12px;">(UTC)</span>
      </div>
    </div>

    <div style="margin-top:8px; text-align:center; color:#888; font-size:12px;">
      UTC Now: <b id="utcNow">----</b>
    </div>

  {% if winner %}
  <div class="panel">
    <h2>🏆 Today’s Leader</h2>

    <div class="leaderGrid">

      <!-- ✅ NEWS BOX (ONLY AREA we modify) -->
      <div class="leaderNews">
        <div class="how leader-steps" style="align-items:center;">
          <div class="step">
            <div class="newsTopRow">
              <b>📰 Trending News</b>
            </div>
            <div class="newsRefresh" id="newsRefreshLabel">Refresh in 60s</div>

            <div class="newsList" id="newsList">
              {% for n in news %}
              <div class="newsItem {% if loop.index == 1 %}top1{% endif %}">
                <div class="newsRank">{{ loop.index }}</div>
                <a href="https://www.google.com/search?q={{ n.q }}" target="_blank" rel="noopener noreferrer">
                  {{ n.title }}
                </a>
                <div class="newsMeta">
                  Sources: <b>{{ n.sources }}</b> • Mentions: <b>{{ n.mentions }}</b>
                </div>
              </div>
              {% endfor %}
              {% if not news %}
              <div class="newsItem">
                <div class="newsRank">1</div>
                <a href="https://www.google.com/search?q=breaking+news" target="_blank" rel="noopener noreferrer">
                  No news yet — click to search.
                </a>
                <div class="newsMeta">Try again in a moment.</div>
              </div>
              {% endif %}
            </div>

            <div class="newsHint">Click a title → Google search</div>
          </div>
        </div>
      </div>

      <div class="leaderLeft">
        <div class="leaderVideo">
          <img class="thumb" src="{{ winner.thumb }}" />
          <a class="titlelink" href="{{ winner.url }}" target="_blank">▶ Watch #1 Shorts</a>
          <div class="meta">Total Boosts: <b>{{ winner.total_boost }}</b> • Your Boosts: <b>{{ winner.my_boost }}</b></div>
          <div class="score">🔥 Viral Score: {{ winner.score }}</div>

          <button
            type="button"
            class="btn secondary pump"
            data-vid="{{ winner.id }}"
            style="display:inline-flex; align-items:center; justify-content:center; gap:10px; text-align:center;"
          >
            <svg width="30" height="30" viewBox="0 0 128 128" aria-hidden="true" style="display:block;">
              <g transform="translate(64 64) rotate(-35) translate(-64 -64)">
                <rect x="14" y="26" width="100" height="76" rx="38" fill="#0a2f2a" opacity="0.85"/>
                <rect x="18" y="30" width="92" height="68" rx="34" fill="#ffffff" opacity="0.18"/>
                <rect x="22" y="34" width="84" height="60" rx="30" fill="#eafff5"/>
                <path d="M22 94 L22 34 L58 34 L106 94 Z" fill="#22c55e"/>
                <path d="M58 34 H106 V94 H86 Z" fill="#ffffff"/>
                <path d="M52 34 H70 L106 94 H88 Z" fill="#0a2f2a" opacity="0.55"/>
                <path d="M34 76 C29 68 29 56 37 49" fill="none" stroke="#ffffff" stroke-width="8" stroke-linecap="round" opacity="0.85"/>
                <path d="M46 88 C41 81 41 70 48 63" fill="none" stroke="#ffffff" stroke-width="6" stroke-linecap="round" opacity="0.55"/>
              </g>
            </svg>
            <span style="display:inline-block; line-height:1; text-align:center;">Mint on Pump.fun</span>
          </button>

          <div style="display:flex; gap:10px; justify-content:center; margin-top:10px;">
            <button type="button" class="btn secondary" id="copyPackBtn" data-vid="{{ winner.id }}">
              Copy Pack (Text + Image)
            </button>
          </div>

        </div>
      </div>

      <div class="leaderRight">
        <div class="how leader-steps">
          <div class="step">
            <b>🚀 Boost-to-Rank</b>
            <p>Boost a video to push it up the feed. The UX is the token utility.</p>
          </div>
          <div class="step">
            <b>🔥 Burn-to-Boost (next)</b>
            <p>Replace points with token burning. Spend → burn → rank.</p>
          </div>
          <div class="step">
            <b>🗳 Community Picks (next)</b>
            <p>Daily winner gets highlighted. Later: creator reward pool.</p>
          </div>
        </div>
      </div>

    </div>
  </div>
  {% endif %}

  <div class="panel" id="how">
    <h2>How it works</h2>
    <div class="how">
      <div class="step">
        <b>1) Daily Drop</b>
        <p>We fetch a fresh Shorts set. Reset at <b>00:00 UTC</b> (and on server restart in MVP).</p>
      </div>
      <div class="step">
        <b>2) Boost</b>
        <p>Boost costs <b>100</b> points. Your boosts are tracked per browser (cookie).</p>
      </div>
      <div class="step">
        <b>3) Rank</b>
        <p>Ranking is driven by community boosts + time decay. Top videos get <b>HOT</b>.</p>
      </div>
      <div class="step">
        <b>4) Token (next)</b>
        <p>Points become a token. Boost becomes burn-to-boost attention.</p>
      </div>
    </div>
    <hr class="sep"/>
    <div class="kpis">
      <div class="pill">Your Points: <b>{{ my_points }}</b></div>
      <div class="pill">Feed Size: <b>{{ feed_size }}</b></div>
      <div class="pill">Total Boosts Today: <b>{{ total_boosts_today }}</b></div>
    </div>
  </div>

  <div id="feed" class="panel" style="padding-bottom:6px;">
    <h2>🔥 Feed</h2>
    <div style="color:#888; font-size:12px; text-align:center;">Boosted videos rise. Top 3 show <b>HOT</b>. Your boosts persist in this browser.</div>
  </div>

  <div class="grid">
  {% for v in videos %}
    <div class="card {% if v.my_boost > 0 %}boosted{% endif %}">
      {% if v.my_boost > 0 %}
        <div class="badge boosted">BOOSTED</div>
      {% endif %}
      {% if v.rank <= 3 %}
        <div class="badge hot">🔥 HOT</div>
      {% endif %}
      {% if v.rank == 1 %}
        <div class="badge winner">🏆 #1</div>
      {% endif %}

      <img class="thumb" src="{{ v.thumb }}" />
      <a class="titlelink" href="{{ v.url }}" target="_blank">▶ Watch Shorts</a>
      <div class="meta">Your Boosts: <b>{{ v.my_boost }}</b> • Total: <b>{{ v.total_boost }}</b></div>
      <div class="score">🔥 Viral Score: {{ v.score }}</div>

      <form method="post" action="/boost">
        <input type="hidden" name="vid" value="{{ v.id }}"/>
        <button class="boost-btn">🚀 BOOST (-100)</button>
      </form>
    </div>
  {% endfor %}
  </div>

  <div class="footer">
    MVP build. Next: wallet connect + burn-to-boost token flow.
  </div>

</div>

<div class="centerNotice" id="centerNotice" aria-live="polite">
  <div id="centerNoticeText">Ready to make a token. Check out the clipboard.</div>
  <div class="sub">Paste on Pump.fun (Ctrl+V)</div>
</div>

<script>
  const resetAtMs = {{ reset_at_ms }};

  function pad(n){ return String(n).padStart(2,'0'); }
  function tick(){
    let diff = resetAtMs - Date.now();
    if (diff < 0) diff = 0;
    const totalSec = Math.floor(diff / 1000);
    const h = Math.floor(totalSec / 3600);
    const m = Math.floor((totalSec % 3600) / 60);
    const s = totalSec % 60;
    const el = document.getElementById("resetCountdownHero");
    if (el) el.textContent = `${pad(h)}:${pad(m)}:${pad(s)}`;
  }
  tick();
  setInterval(tick, 1000);

  function tickUTC(){
    const d = new Date();
    const Y = d.getUTCFullYear();
    const M = String(d.getUTCMonth() + 1).padStart(2,'0');
    const D = String(d.getUTCDate()).padStart(2,'0');
    const h = String(d.getUTCHours()).padStart(2,'0');
    const m = String(d.getUTCMinutes()).padStart(2,'0');
    const s = String(d.getUTCSeconds()).padStart(2,'0');
    const el = document.getElementById("utcNow");
    if (el) el.textContent = `${Y}-${M}-${D} ${h}:${m}:${s} UTC`;
  }
  tickUTC();
  setInterval(tickUTC, 1000);

  function showCenterNotice(msg){
    const box = document.getElementById("centerNotice");
    const text = document.getElementById("centerNoticeText");
    if(!box || !text) return;
    text.textContent = msg;
    box.classList.add("show");
    clearTimeout(window.__centerNoticeTimer);
    window.__centerNoticeTimer = setTimeout(() => box.classList.remove("show"), 1800);
  }

  function buildPackText(d){
    return `Name: ${d.name}
Ticker: ${d.ticker}

Description:
${d.description}

Source:
${d.source_url}
`;
  }

  async function fetchPack(vid){
    const res = await fetch(`/api/pump_pack?vid=${encodeURIComponent(vid)}`, { cache: "no-store" });
    const data = await res.json();
    if(!data.ok) throw new Error(data.error || "failed");
    return data;
  }

  async function copyTextOnly(vid){
    const data = await fetchPack(vid);
    const text = buildPackText(data);

    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return "clipboard";
    } else {
      window.prompt("Copy this and paste:", text);
      return "prompt";
    }
  }

  async function copyImageTry(vid){
    const data = await fetchPack(vid);
    const imgUrl = data.thumb;

    const imgRes = await fetch(imgUrl, { mode: "cors", cache: "no-store" });
    const blob = await imgRes.blob();

    if (navigator.clipboard && window.isSecureContext && window.ClipboardItem) {
      await navigator.clipboard.write([
        new ClipboardItem({ [blob.type]: blob })
      ]);
      return "clipboard";
    }

    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `thumb_${vid}.jpg`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(a.href);
    return "download";
  }

  async function copyPack(vid){
    await copyTextOnly(vid);
    try { await copyImageTry(vid); } catch(e){ console.error(e); }
    showCenterNotice("Ready to make a token. Check out the clipboard.");
  }

  async function mintFlow(vid){
    try{
      await copyPack(vid);
      window.open("https://pump.fun", "_blank", "noopener,noreferrer");
    } catch(e){
      console.error(e);
      showCenterNotice("Copy failed. Try again.");
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    const b = document.getElementById("copyPackBtn");
    if (b) b.addEventListener("click", () => copyPack(b.dataset.vid));

    document.querySelectorAll("button.pump[data-vid]").forEach((btn) => {
      btn.addEventListener("click", (ev) => {
        ev.preventDefault();
        mintFlow(btn.dataset.vid);
      });
    });

    // ============================
    // ✅ NEWS AUTO REFRESH (NEWS ONLY)
    // - countdown: "Refresh in 60s" -> ... -> "Refreshing..."
    // - updates only #newsList content + top1 effect
    // ============================
    const listEl = document.getElementById("newsList");
    const labelEl = document.getElementById("newsRefreshLabel");
    if (listEl && labelEl) {
      let left = 60;

      function renderNews(items){
        if (!items || !items.length) {
          listEl.innerHTML = `
            <div class="newsItem top1">
              <div class="newsRank">1</div>
              <a href="https://www.google.com/search?q=breaking+news" target="_blank" rel="noopener noreferrer">
                No news yet — click to search.
              </a>
              <div class="newsMeta">Try again in a moment.</div>
            </div>
          `;
          return;
        }

        const html = items.map((n, idx) => {
          const rank = idx + 1;
          const top1 = rank === 1 ? " top1" : "";
          const title = (n.title || "").replace(/</g,"&lt;").replace(/>/g,"&gt;");
          const q = encodeURIComponent(n.title || "");
          const sources = n.sources ?? "-";
          const mentions = n.mentions ?? "-";

          return `
            <div class="newsItem${top1}">
              <div class="newsRank">${rank}</div>
              <a href="https://www.google.com/search?q=${q}" target="_blank" rel="noopener noreferrer">${title}</a>
              <div class="newsMeta">Sources: <b>${sources}</b> • Mentions: <b>${mentions}</b></div>
            </div>
          `;
        }).join("");

        listEl.innerHTML = html;
      }

      async function refreshNews(){
        labelEl.textContent = "Refreshing...";
        try{
          const res = await fetch("/api/news", { cache: "no-store" });
          const data = await res.json();
          if (data && data.ok) renderNews(data.items || []);
        } catch(e){
          console.error(e);
        } finally {
          left = 60;
          labelEl.textContent = `Refresh in ${left}s`;
        }
      }

      setInterval(() => {
        left -= 1;
        if (left <= 0) {
          refreshNews();
        } else {
          labelEl.textContent = `Refresh in ${left}s`;
        }
      }, 1000);

      labelEl.textContent = `Refresh in ${left}s`;
    }
  });
</script>
</body>
</html>
"""

@app.route("/")
def home():
    ensure_daily_reset()
    uid = get_uid()
    track_visit(uid)

    me, items, winner = build_view_model(uid)
    reset_at_ms = int((DAY_START_TS + 86400) * 1000)
    total_boosts_today = sum(total_boosts(vid) for vid in VIDEOS.keys())

    news = get_ranked_news_cached()

    html = render_template_string(
        HTML,
        videos=items,
        winner=winner,
        my_points=me["points"],
        feed_size=len(items),
        total_boosts_today=total_boosts_today,
        reset_at_ms=reset_at_ms,
        visitors_today=VISITOR_TODAY,
        visitors_total=VISITOR_TOTAL,
        news=news,
    )

    resp = make_response(html)
    if request.cookies.get(COOKIE_NAME) is None:
        resp.set_cookie(COOKIE_NAME, uid, max_age=31536000, samesite="Lax")
    return resp

@app.route("/boost", methods=["POST"])
def boost():
    ensure_daily_reset()
    uid = get_uid()
    me = get_user(uid)

    vid = request.form.get("vid")
    if vid in VIDEOS and me["points"] >= 100:
        me["points"] -= 100
        me["boosts"][vid] = me["boosts"].get(vid, 0) + 1
    return redirect("/")

if __name__ == "__main__":
    app.run()

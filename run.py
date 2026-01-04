# BUILD: 26-01-04 v454-ui (do not overwrite)
# SOURCE OF TRUTH: GitHub main

from flask import Flask, render_template_string, request, redirect, make_response
import requests, re, time, uuid
from datetime import datetime, timezone

app = Flask(__name__)
HEADERS = {"User-Agent": "Mozilla/5.0"}
COOKIE_NAME = "vsr_uid"

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

def ensure_daily_reset():
    global VIDEOS, USERS, DAY_START_TS
    if time.time() - DAY_START_TS >= 86400:
        VIDEOS = build_daily_videos(limit=12)
        USERS = {}
        DAY_START_TS = utc_midnight_ts()

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
# UI (Countdown moved under MVP note)
# -----------------------------
HTML = """
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

.nav{
  display:flex; justify-content:space-between; align-items:center;
  gap:12px; padding:14px 0 6px 0;
}

/* CHANGED: brand font size increased (only change) */
.brand{ font-weight:900; letter-spacing:.3px; font-size:26px; }
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

.hero{ padding:22px 0 10px 0; text-align:center; }
.h-title{ font-size:40px; line-height:1.05; margin:10px 0 10px 0; }
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
.panel h2{ margin:0 0 10px 0; font-size:18px; }
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
.titlelink{ display:block; margin-top:8px; font-weight:900; }
.meta{ margin-top:6px; color:var(--muted); font-size:12px; }
.score{ margin-top:6px; color:var(--accent); font-weight:900; }

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

@media (max-width:520px){
  body{ padding:18px; }
  .h-title{ font-size:32px; }
  .brand{ font-size:22px; }
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

    <!-- ✅ countdown moved here -->
    <div class="countdown-wrap">
      <div class="countdown">
        <span class="label">RESET IN</span>
        <b class="time" id="resetCountdownHero">--:--:--</b>
        <span style="color:#777; font-size:12px;">(UTC)</span>
      </div>
    </div>
  </div>

  {% if winner %}
  <div class="panel">
    <h2>🏆 Today’s Leader</h2>
    <div style="display:flex; gap:14px; flex-wrap:wrap; align-items:center; justify-content:center;">
      <div style="width:min(420px,100%);">
        <img class="thumb" src="{{ winner.thumb }}" />
        <a class="titlelink" href="{{ winner.url }}" target="_blank">▶ Watch #1 Shorts</a>
        <div class="meta">Total Boosts: <b>{{ winner.total_boost }}</b> • Your Boosts: <b>{{ winner.my_boost }}</b></div>
        <div class="score">🔥 Viral Score: {{ winner.score }}</div>
      </div>
      <div style="min-width:240px; flex:1;">
        <div class="how">
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
    <div style="color:#888; font-size:12px;">Boosted videos rise. Top 3 show <b>HOT</b>. Your boosts persist in this browser.</div>
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

<script>
  const resetAtMs = {{ reset_at_ms }}; // milliseconds
  function pad(n){ return String(n).padStart(2,'0'); }
  function tick(){
    let diff = resetAtMs - Date.now();
    if (diff < 0) diff = 0;
    const totalSec = Math.floor(diff / 1000);
    const h = Math.floor(totalSec / 3600);
    const m = Math.floor((totalSec % 3600) / 60);
    const s = totalSec % 60;
    const txt = `${pad(h)}:${pad(m)}:${pad(s)}`;
    const el = document.getElementById("resetCountdownHero");
    if (el) el.textContent = txt;
  }
  tick();
  setInterval(tick, 1000);
</script>

</body>
</html>
"""

@app.route("/")
def home():
    ensure_daily_reset()
    uid = get_uid()
    me, items, winner = build_view_model(uid)

    reset_at_ms = int((DAY_START_TS + 86400) * 1000)
    total_boosts_today = sum(total_boosts(vid) for vid in VIDEOS.keys())

    html = render_template_string(
        HTML,
        videos=items,
        winner=winner,
        my_points=me["points"],
        feed_size=len(items),
        total_boosts_today=total_boosts_today,
        reset_at_ms=reset_at_ms,
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

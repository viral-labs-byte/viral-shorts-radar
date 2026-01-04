from __future__ import annotations

from flask import Flask, request, redirect, url_for, render_template_string
from datetime import datetime, timezone, timedelta
import hashlib

app = Flask(__name__)

# --------------------------------------------------
# MVP sample data (replace with real collectors later)
# --------------------------------------------------
VIDEOS = [
    {
        "id": "pudgy_penguins",
        "title": "Why Pudgy Penguins is trending right now",
        "url": "https://www.youtube.com/shorts/2sQ0v2hQk1o",
        "source": "YouTube Shorts",
    },
    {
        "id": "render_token",
        "title": "Render Token narrative explained in 60 seconds",
        "url": "https://www.youtube.com/shorts/3k8yNw5Fj2A",
        "source": "YouTube Shorts",
    },
    {
        "id": "meme_wave",
        "title": "Fast-moving meme wave you should not ignore",
        "url": "https://www.youtube.com/shorts/9vQm0l1Zb2c",
        "source": "YouTube Shorts",
    },
]

# In-memory boost storage (MVP)
BOOSTS: dict[str, int] = {}


# --------------------------------------------------
# Helpers
# --------------------------------------------------
def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def next_reset_utc() -> datetime:
    """Daily reset at 00:00 UTC"""
    now = utc_now()
    tomorrow = (now + timedelta(days=1)).date()
    return datetime(
        tomorrow.year, tomorrow.month, tomorrow.day, 0, 0, 0, tzinfo=timezone.utc
    )


def pick_daily_video(videos: list[dict]) -> dict:
    """Pick one stable daily leader based on UTC date"""
    today = utc_now().date().isoformat()
    h = hashlib.sha256(today.encode("utf-8")).hexdigest()
    idx = int(h[:8], 16) % max(1, len(videos))
    return videos[idx]


def sorted_by_boost(videos: list[dict]) -> list[dict]:
    return sorted(videos, key=lambda v: BOOSTS.get(v["id"], 0), reverse=True)


# --------------------------------------------------
# Routes
# --------------------------------------------------
@app.get("/")
def home():
    daily = pick_daily_video(VIDEOS)
    ranked = sorted_by_boost(VIDEOS)
    reset_at = next_reset_utc()

    HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Viral Shorts Radar</title>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial;
           margin:0; background:#0b0b10; color:#ffffff; }
    .wrap { max-width: 980px; margin: 0 auto; padding: 32px 16px 64px; }
    .hero { text-align:center; }
    .hero h1 { margin:0; font-size:42px; letter-spacing:-0.5px; }
    .hero p { margin-top:10px; color:#b8b8c8; }
    .pill { display:inline-block; margin-top:14px; padding:8px 14px;
            border:1px solid #2a2a3a; border-radius:999px;
            background:rgba(255,255,255,0.03); color:#b8b8c8; }
    .grid { display:grid; grid-template-columns:1fr; gap:16px; margin-top:28px; }
    @media (min-width:860px){ .grid { grid-template-columns:1fr 1fr; } }
    .card { border:1px solid #242438; border-radius:14px;
            padding:16px; background:rgba(255,255,255,0.03); }
    h2 { margin:0 0 8px; font-size:18px; }
    .meta { font-size:13px; color:#9a9ab0; }
    a { color:#8ab4ff; text-decoration:none; }
    a:hover { text-decoration:underline; }
    .row { display:flex; justify-content:space-between; align-items:center; gap:12px; }
    .btn { background:#ffffff; color:#0b0b10; border:0; border-radius:10px;
           padding:10px 14px; font-weight:700; cursor:pointer; }
    .btn:active { transform:translateY(1px); }
    .count { color:#b8b8c8; font-size:14px; }
    .footer { text-align:center; margin-top:32px; font-size:12px; color:#9a9ab0; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <h1>Viral Shorts Radar</h1>
      <p>Boost what goes viral. A community-powered signal for short-form videos.</p>
      <div class="pill">
        MVP · Daily reset in <span id="countdown">--:--:--</span> (UTC)
      </div>
    </div>

    <div class="grid">
      <div class="card">
        <div class="row">
          <h2>🏆 Today's Viral Leader</h2>
          <span class="count">{{ boosts.get(daily.id, 0) }} boosts</span>
        </div>
        <div class="meta">{{ daily.source }}</div>
        <p style="margin:10px 0 12px;">
          <a href="{{ daily.url }}" target="_blank" rel="noopener">{{ daily.title }}</a>
        </p>
        <form method="POST" action="/boost">
          <input type="hidden" name="vid" value="{{ daily.id }}"/>
          <button class="btn" type="submit">BOOST</button>
        </form>
      </div>

      <div class="card">
        <div class="row">
          <h2>🔥 Boostboard</h2>
          <span class="meta">Top boosted today</span>
        </div>
        {% for v in ranked %}
        <div style="padding:10px 0; border-top:1px solid #242438;">
          <div class="row">
            <div>
              <strong>
                <a href="{{ v.url }}" target="_blank" rel="noopener">{{ v.title }}</a>
              </strong>
              <div class="meta">{{ v.source }}</div>
            </div>
            <div style="text-align:right;">
              <div class="count">{{ boosts.get(v.id, 0) }} boosts</div>
              <a class="meta" href="/boost?vid={{ v.id }}">+ boost</a>
            </div>
          </div>
        </div>
        {% endfor %}
      </div>
    </div>

    <div class="footer">
      Built by Viral Labs · Experimental MVP · Not financial advice
    </div>
  </div>

<script>
  const resetAt = new Date("{{ reset_at_iso }}");
  function tick(){
    const now = new Date();
    let diff = Math.max(0, resetAt - now);
    const h = String(Math.floor(diff / 3600000)).padStart(2,'0');
    diff %= 3600000;
    const m = String(Math.floor(diff / 60000)).padStart(2,'0');
    diff %= 60000;
    const s = String(Math.floor(diff / 1000)).padStart(2,'0');
    document.getElementById("countdown").innerText = `${h}:${m}:${s}`;
  }
  tick();
  setInterval(tick, 1000);
</script>
</body>
</html>
"""
    return render_template_string(
        HTML,
        daily=daily,
        ranked=ranked,
        boosts=BOOSTS,
        reset_at_iso=reset_at.isoformat(),
    )


@app.route("/boost", methods=["GET", "POST"])
@app.route("/boost/<vid>", methods=["GET", "POST"])
def boost(vid=None):
    target = vid or request.args.get("vid") or request.form.get("vid")
    valid_ids = {v["id"] for v in VIDEOS}

    if not target or target not in valid_ids:
        return redirect(url_for("home"))

    BOOSTS[target] = BOOSTS.get(target, 0) + 1
    return redirect(url_for("home"))


@app.get("/health")
def health():
    return {"ok": True}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)

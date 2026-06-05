import os
import math
import requests
from datetime import datetime, timedelta

USERNAME = os.environ.get("GITHUB_USERNAME", "Git-Shashi")
TOKEN = os.environ.get("GITHUB_TOKEN", "")

HEADERS = {
    "Authorization": f"bearer {TOKEN}",
    "Content-Type": "application/json",
}

QUERY = """
query($username: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $username) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      totalPullRequestReviewContributions
    }
  }
}
"""

def fetch_stats():
    now = datetime.utcnow()
    one_year_ago = now - timedelta(days=365)
    variables = {
        "username": USERNAME,
        "from": one_year_ago.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "to": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    resp = requests.post(
        "https://api.github.com/graphql",
        json={"query": QUERY, "variables": variables},
        headers=HEADERS,
    )
    resp.raise_for_status()
    data = resp.json()
    c = data["data"]["user"]["contributionsCollection"]
    return {
        "commits": c["totalCommitContributions"],
        "prs": c["totalPullRequestContributions"],
        "issues": c["totalIssueContributions"],
        "reviews": c["totalPullRequestReviewContributions"],
    }

def compute_percentages(stats):
    total = sum(stats.values()) or 1
    return {k: round(v / total * 100) for k, v in stats.items()}

def polar_to_cart(cx, cy, radius, angle_deg):
    angle_rad = math.radians(angle_deg)
    return (
        round(cx + radius * math.cos(angle_rad), 2),
        round(cy + radius * math.sin(angle_rad), 2),
    )

def generate_svg(pct):
    cx, cy = 220, 160
    max_r = 100

    axes = [
        ("reviews",  -90, "Code review",   pct["reviews"],  0,   -18),
        ("issues",     0, "Issues",         pct["issues"],  18,    0),
        ("prs",       90, "Pull requests",  pct["prs"],      0,   18),
        ("commits",  180, "Commits",        pct["commits"], -18,   0),
    ]

    points = []
    for key, angle, label, p, dx, dy in axes:
        r = max_r * (p / 100)
        x, y = polar_to_cart(cx, cy, r, angle)
        points.append((x, y))

    polygon_pts = " ".join(f"{x},{y}" for x, y in points)

    axis_lines = ""
    labels = ""
    dots = ""
    for key, angle, label, p, dx, dy in axes:
        ex, ey = polar_to_cart(cx, cy, max_r, angle)
        axis_lines += f'<line x1="{cx}" y1="{cy}" x2="{ex}" y2="{ey}" stroke="#3d4f3d" stroke-width="1.5"/>\n'

        lx, ly = polar_to_cart(cx, cy, max_r + 28, angle)
        anchor = "middle"
        if angle == 0:
            anchor = "start"
        elif angle == 180:
            anchor = "end"

        labels += f'''
<text x="{lx + dx}" y="{ly - 6}" text-anchor="{anchor}" font-family="sans-serif" font-size="12" fill="#8b949e">{p}%</text>
<text x="{lx + dx}" y="{ly + 8}" text-anchor="{anchor}" font-family="sans-serif" font-size="12" fill="#8b949e">{label}</text>
'''
        px2, py2 = polar_to_cart(cx, cy, max_r * (p / 100), angle)
        dots += f'<circle cx="{px2}" cy="{py2}" r="4" fill="#3fb950"/>\n'

    svg = f'''<svg width="440" height="320" viewBox="0 0 440 320" xmlns="http://www.w3.org/2000/svg">
  <rect width="440" height="320" rx="8" fill="#161b22"/>
  {axis_lines}
  <polygon points="{polygon_pts}" fill="#196c2e" fill-opacity="0.55" stroke="#2ea043" stroke-width="1.5"/>
  {dots}
  {labels}
  <text x="220" y="308" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#484f58">
    Updated: {datetime.utcnow().strftime("%Y-%m-%d")}
  </text>
</svg>'''
    return svg

def main():
    print(f"Fetching stats for {USERNAME}...")
    stats = fetch_stats()
    print(f"Raw stats: {stats}")
    pct = compute_percentages(stats)
    print(f"Percentages: {pct}")
    svg = generate_svg(pct)
    out_path = "activity_chart.svg"
    with open(out_path, "w") as f:
        f.write(svg)
    print(f"SVG written to {out_path}")

if __name__ == "__main__":
    main()

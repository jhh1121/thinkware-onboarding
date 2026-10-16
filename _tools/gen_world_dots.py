"""Generate a dot-matrix world map (Equal Earth projection) for the onboarding page.

Usage: python -I gen_world_dots.py <land-110m.json> <out.svg>
Prints the projection values (scale, ox, oy, W, H) to copy into the page script.
Data: https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/land-110m.json
"""
import json, math, sys

src, out = sys.argv[1], sys.argv[2]
topo = json.load(open(src, encoding="utf-8"))

# --- decode TopoJSON arcs -------------------------------------------------
sx, sy = topo["transform"]["scale"]
tx, ty = topo["transform"]["translate"]
arcs = []
for arc in topo["arcs"]:
    x = y = 0
    pts = []
    for dx, dy in arc:
        x += dx; y += dy
        pts.append((x * sx + tx, y * sy + ty))
    arcs.append(pts)

def arc_pts(i):
    return arcs[i] if i >= 0 else arcs[~i][::-1]

rings = []
for geom in topo["objects"]["land"]["geometries"]:
    polys = geom["arcs"] if geom["type"] == "MultiPolygon" else [geom["arcs"]]
    for poly in polys:
        for ring in poly:
            pts = []
            for a in ring:
                p = arc_pts(a)
                pts.extend(p if not pts else p[1:])
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            rings.append((pts, min(xs), max(xs), min(ys), max(ys)))

def on_land(lon, lat):
    inside = False
    for pts, x0, x1, y0, y1 in rings:
        if not (x0 <= lon <= x1 and y0 <= lat <= y1):
            continue
        c = False
        n = len(pts)
        j = n - 1
        for i in range(n):
            xi, yi = pts[i]; xj, yj = pts[j]
            if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
                c = not c
            j = i
        if c:
            inside = not inside  # holes (lakes) toggle back
    return inside

# --- Equal Earth projection -------------------------------------------------
A1, A2, A3, A4 = 1.340264, -0.081106, 0.000893, 0.003796
M = math.sqrt(3) / 2
CENTER = 145.0

def wrap(lon):
    return (lon + 180) % 360 - 180

def fwd(lon, lat):
    lam = math.radians(wrap(lon - CENTER))
    th = math.asin(M * math.sin(math.radians(lat)))
    t2 = th * th; t6 = t2 ** 3
    x = lam * math.cos(th) / (M * (A1 + 3 * A2 * t2 + t6 * (7 * A3 + 9 * A4 * t2)))
    y = th * (A1 + A2 * t2 + t6 * (A3 + A4 * t2))
    return x, y

def inv(x, y):
    th = y
    for _ in range(12):
        t2 = th * th; t6 = t2 ** 3
        fy = th * (A1 + A2 * t2 + t6 * (A3 + A4 * t2)) - y
        fpy = A1 + 3 * A2 * t2 + t6 * (7 * A3 + 9 * A4 * t2)
        d = fy / fpy
        th -= d
        if abs(d) < 1e-9:
            break
    t2 = th * th; t6 = t2 ** 3
    lam = M * x * (A1 + 3 * A2 * t2 + t6 * (7 * A3 + 9 * A4 * t2)) / math.cos(th)
    s = math.sin(th) / M
    if abs(s) > 1 or abs(lam) > math.pi:
        return None
    return wrap(math.degrees(lam) + CENTER), math.degrees(math.asin(s))

# --- frame: full Equal Earth outline (rounded edges) --------------------------
xmax = fwd(CENTER + 180 - 1e-9, 0)[0]
ymax = fwd(CENTER, 90)[1]
W = 1000.0
PAD = 4.0
scale = (W - 2 * PAD) / (2 * xmax)
H = round(2 * ymax * scale + 2 * PAD, 2)
ox, oy = W / 2, ymax * scale + PAD  # svg = (ox + x*scale, oy - y*scale)

def svgpt(lon, lat):
    x, y = fwd(lon, lat)
    return ox + x * scale, oy - y * scale

def line(pts):
    return "M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in pts)

EPS = 1e-6
right = [svgpt(CENTER + 180 - EPS, lat) for lat in range(-90, 91)]
left = [svgpt(CENTER - 180 + EPS, lat) for lat in range(90, -91, -1)]
outline = line(right + left) + "Z"

grat = []
for lat in (-60, -30, 0, 30, 60):
    grat.append(line([svgpt(CENTER - 180 + EPS + k * 2, lat) for k in range(0, 181)]))
for k in range(-150, 181, 30):
    grat.append(line([svgpt(CENTER + k - (EPS if k == 180 else 0), lat) for lat in range(-90, 91, 2)]))

STEP = 5.0   # dot spacing in svg units
R = 1.5      # dot radius
parts = []
count = 0
yv = STEP / 2
while yv < H:
    xv = STEP / 2
    while xv < W:
        ll = inv((xv - ox) / scale, (oy - yv) / scale)
        if ll and ll[1] > -58 and on_land(*ll):
            parts.append(f"M{xv - R:.1f} {yv:.1f}a{R} {R} 0 1 0 {2*R:.1f} 0a{R} {R} 0 1 0 {-2*R:.1f} 0")
            count += 1
        xv += STEP
    yv += STEP

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} {H}" width="{W:.0f}" height="{H}">'
       '<defs><radialGradient id="g" cx="50%" cy="42%" r="62%">'
       '<stop offset="0" stop-color="#1c2430"/><stop offset="1" stop-color="#0e131a"/></radialGradient>'
       '<clipPath id="c"><path d="' + outline + '"/></clipPath></defs>'
       '<path d="' + outline + '" fill="url(#g)"/>'
       '<g clip-path="url(#c)"><path fill="none" stroke="#ffffff" stroke-opacity=".06" stroke-width="1" d="' + "".join(grat) + '"/></g>'
       '<path fill="#566070" d="' + "".join(parts) + '"/>'
       '<path d="' + outline + '" fill="none" stroke="#ffffff" stroke-opacity=".14" stroke-width="1.2"/>'
       '</svg>')
open(out, "w", encoding="utf-8").write(svg)
print("dots", count, "W", W, "H", H, "scale", scale, "ox", ox, "oy", oy, "bytes", len(svg))

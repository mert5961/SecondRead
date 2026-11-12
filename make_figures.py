"""Draw the README figures from the saved results (light + dark SVG). Standard library only.
Run: python3 make_figures.py  -> figures/*.svg
"""
import glob
import json
import os
from xml.sax.saxutils import escape

THEMES = {
    "light": {"bg": "#fcfcfb", "panel": "#f3f2ef", "ink": "#0b0b0b", "ink2": "#52514e", "muted": "#898781",
              "line": "#c3c2b7", "grid": "#e6e5e0", "a": "#eb6834", "b": "#2a78d6", "bad": "#d03b3b", "good": "#0a7d0a"},
    "dark": {"bg": "#1a1a19", "panel": "#242422", "ink": "#f0efec", "ink2": "#c3c2b7", "muted": "#898781",
             "line": "#383835", "grid": "#2c2c2a", "a": "#d95926", "b": "#3987e5", "bad": "#e66767", "good": "#3fbf3f"},
}
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"


def text(x, y, s, size=14, fill="ink", weight=400, family=SANS, anchor="start", t=None):
    return ('<text x="%g" y="%g" font-family="%s" font-size="%g" font-weight="%d" fill="%s" text-anchor="%s">%s</text>'
            % (x, y, family, size, weight, t[fill], anchor, escape(s)))


def svg(w, h, body, t, title):
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" role="img">'
            '<title>%s</title><rect width="100%%" height="100%%" rx="12" fill="%s"/>%s</svg>'
            % (w, h, w, h, escape(title), t["bg"], "".join(body)))


# ---------- figure 1: one case, two answers ----------
def hero(t):
    case = {c["id"]: c for c in json.load(open("cases.json"))}["pd_from_nadir_not_baseline"]
    W, H = 1000, 452
    b = [text(32, 46, "Same report, same rules. Two ways to get the answer.", 22, "ink", 650, t=t),
         text(32, 72, "Synthetic case from the eval. Model: qwen3.8:27b (local). RECIST 1.1.", 13, "muted", t=t)]
    # left: the report
    b.append('<rect x="32" y="92" width="420" height="328" rx="8" fill="%s"/>' % t["panel"])
    b.append(text(52, 122, "THE REPORT", 12, "muted", 700, t=t))
    y = 150
    for line in case["report"].split("\n")[2:]:
        if not line.strip():
            y += 8
            continue
        line = line.replace("Segment 6 liver lesion", "Liver lesion").replace("segment 6 liver lesion", "liver lesion")
        line = line.replace("Left lower lobe mass", "Lung mass").replace("left lower lobe mass", "lung mass")
        bold = line.endswith(":")
        b.append(text(52, y, line, 13.5, "ink" if bold else "ink2", 700 if bold else 400, MONO, t=t))
        y += 24
    b.append(text(52, 398, "Sum of sizes: 100 mm \u2192 50 mm (lowest) \u2192 62 mm", 13.5, "muted", 600, t=t))
    # right: two answers
    X = 476

    def card(y0, h, label, verdict, ok, lines):
        out = ['<rect x="%d" y="%d" width="492" height="%d" rx="8" fill="%s"/>' % (X, y0, h, t["panel"]),
               '<rect x="%d" y="%d" width="4" height="%d" rx="2" fill="%s"/>' % (X, y0, h, t["good" if ok else "bad"]),
               text(X + 20, y0 + 28, label, 12, "muted", 700, t=t),
               text(X + 20, y0 + 60, verdict, 22, "ink", 700, t=t),
               text(X + 472, y0 + 60, ("✓ correct" if ok else "✗ wrong"), 15, "good" if ok else "bad", 700,
                    anchor="end", t=t)]
        for i, l in enumerate(lines):
            out.append(text(X + 20, y0 + 90 + i * 21, l, 13.5, "ink2", 400, MONO if l.startswith(("sum", "needs", "→")) else SANS, t=t))
        return out

    b += card(92, 152, "A.  THE AI DECIDES ALONE (rules in its prompt)", "Stable disease", False,
              ["“...a 20% increase from the nadir (52 mm) but fails to", "meet the >= 5 mm absolute increase...”",
               "Lowest sum was 50 mm, and +12 mm is more than 5 mm."])
    b += card(256, 164, "B.  THE AI ONLY READS, CODE DECIDES (SecondRead)", "Progressive disease", True,
              ["sum 62 mm vs nadir 50 mm = +12 mm (+24.0%)", "needs >= +20% and >= +5 mm  →  both met",
               "Every answer comes with this working, so a reader", "can check it in seconds."])
    return svg(W, H, b, t, "One case: the AI alone says stable disease (wrong), SecondRead says progressive disease (right)")


# ---------- figure 2: accuracy on the 20 edge cases ----------
def chart(t):
    s = json.load(open("results/summary.json"))
    names = {"qwen3.8:27b": "Large model (27B)", "qwen2.5:7b-instruct": "Small model (7B)"}
    rows = []
    for m in sorted(s["models"], key=lambda m: m["model"] != "qwen3.8:27b"):
        a = int(m["alone"]["edge"].split("/")[0])
        bb = int(m["extract"]["edge"].split("/")[0])
        rows.append((names.get(m["model"], m["model"]), a, bb))
    W, H = 1000, 330
    L, R, top = 220, 930, 118
    scale = (R - L) / 20.0
    out = [text(32, 46, "Right answers on the 20 tricky cases", 22, "ink", 650, t=t),
           text(32, 72, "Edge cases written by hand: +19% vs +20%, growth from the lowest point, lymph node short axis, 2 per organ...",
                13, "muted", t=t)]
    # legend
    lx = L
    for key, lab in (("a", "AI decides alone"), ("b", "AI reads, code decides")):
        out.append('<rect x="%d" y="88" width="14" height="14" rx="3" fill="%s"/>' % (lx, t[key]))
        out.append(text(lx + 22, 100, lab, 14, "ink2", t=t))
        lx += 210
    # grid
    for v in range(0, 21, 5):
        x = L + v * scale
        out.append('<line x1="%g" y1="%d" x2="%g" y2="%d" stroke="%s" stroke-width="1"/>' % (x, top, x, H - 44, t["grid"] if v else t["line"]))
        out.append(text(x, H - 22, str(v), 12, "muted", anchor="middle", t=t))
    bar_h, gap = 26, 2
    for i, (label, a, bb) in enumerate(rows):
        y = top + 14 + i * 92
        out.append(text(L - 16, y + bar_h + 6, label, 15, "ink", 600, anchor="end", t=t))
        for j, (key, v) in enumerate((("a", a), ("b", bb))):
            yy = y + j * (bar_h + gap)
            w = max(v * scale, 4)
            r = 4
            out.append('<path d="M%g %g H%g Q%g %g %g %g V%g Q%g %g %g %g H%g Z" fill="%s"/>'
                       % (L, yy, L + w - r, L + w, yy, L + w, yy + r, yy + bar_h - r, L + w, yy + bar_h, L + w - r, yy + bar_h,
                          L, t[key]))
            out.append(text(L + w + 8, yy + bar_h - 8, "%d/20" % v, 14, "ink", 700, t=t))
    return svg(W, H, out, t, "Right answers on 20 tricky cases: large model alone %d of 20, with code %d of 20; small model alone %d of 20, with code %d of 20"
               % (rows[0][1], rows[0][2], rows[1][1], rows[1][2]))


if __name__ == "__main__":
    os.makedirs("figures", exist_ok=True)
    for mode, t in THEMES.items():
        open("figures/hero-%s.svg" % mode, "w").write(hero(t))
        open("figures/edge-cases-%s.svg" % mode, "w").write(chart(t))
    print(sorted(glob.glob("figures/*.svg")))

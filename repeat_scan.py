"""Same tumor, scanned twice a few minutes apart: nothing changed, so any difference is measurement noise.
Measures both scans from the expert outlines, then asks the rule engine what RECIST would say.

Run: python repeat_scan.py <data folder of one RIDER patient>   (see DATA.md)
"""
import json
import os
import sys

from PIL import Image

import measure as M
from recist import Lesion, assess


def one(folder, ct, rt, roi, label, png):
    cts = M.load_ct(os.path.join(folder, ct))
    spacing = abs(cts[1][0] - cts[0][0])
    polys = M.load_contours(os.path.join(folder, rt))[roi]
    m = M.measure(polys, spacing)
    M.render(cts, polys, m, png, label)
    return m


def main():
    folder = sys.argv[1]
    os.makedirs("figures", exist_ok=True)
    out = {}
    for kind in ("man", "auto"):
        a = one(folder, "CT_236", "RTSTRUCT_TEST", "GTVp_test_" + kind, "Scan 1", "/tmp/_a.png")
        b = one(folder, "CT_213", "RTSTRUCT_RETEST", "GTVp_retest_" + kind, "Scan 2, minutes later", "/tmp/_b.png")
        sizes = [(round(x["long_mm"]), round(x["short_mm"])) for x in (a, b)]
        r = assess([Lesion("lung tumor", "lung", False, sizes)], 1)
        out[kind] = {"scan1_mm": round(a["long_mm"], 1), "scan2_mm": round(b["long_mm"], 1),
                     "change_pct": round(100 * (b["long_mm"] - a["long_mm"]) / a["long_mm"], 1),
                     "volume_ml": [round(a["volume_ml"], 1), round(b["volume_ml"], 1)],
                     "recist": r["overall"], "why": r["why"]}
        if kind == "man":
            im = Image.new("RGB", (1290, 640), (0, 0, 0))
            im.paste(Image.open("/tmp/_a.png"), (0, 0))
            im.paste(Image.open("/tmp/_b.png"), (650, 0))
            im.save("figures/repeat-scan.png")
    json.dump(out, open("results/repeat_scan.json", "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

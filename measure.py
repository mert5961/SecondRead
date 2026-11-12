"""Image -> measurement. Reads a CT series and an expert tumor outline (DICOM RTSTRUCT) and measures the
lesion the way RECIST 1.1 asks: the longest diameter in one axial slice (plus the short axis and volume).

Needs: pip install pydicom numpy pillow   (only this file; the rule engine stays standard library)
Run:   python measure.py <CT folder> <RTSTRUCT folder> [--png out.png] [--label TEST]
Data:  not in this repo. See DATA.md for the public source and licence.
"""
import argparse
import glob
import json
import os

import numpy as np
import pydicom


def load_ct(folder):
    """Returns slices sorted by position: list of (z_mm, dataset)."""
    out = []
    for f in glob.glob(os.path.join(folder, "**", "*.dcm"), recursive=True):
        ds = pydicom.dcmread(f, stop_before_pixels=True)
        if getattr(ds, "Modality", "") == "CT":
            out.append((float(ds.ImagePositionPatient[2]), f))
    if not out:
        raise SystemExit("no CT slices in %s" % folder)
    return sorted(out)


def load_contours(folder):
    """RTSTRUCT -> {roi name: [ (z_mm, Nx2 array of x,y in mm), ... ]}"""
    files = glob.glob(os.path.join(folder, "**", "*.dcm"), recursive=True)
    ds = pydicom.dcmread(files[0])
    names = {r.ROINumber: r.ROIName for r in ds.StructureSetROISequence}
    rois = {}
    for rc in ds.ROIContourSequence:
        polys = []
        for c in getattr(rc, "ContourSequence", []):
            pts = np.array(c.ContourData, dtype=float).reshape(-1, 3)
            polys.append((float(pts[0, 2]), pts[:, :2]))
        rois[names.get(rc.ReferencedROINumber, str(rc.ReferencedROINumber))] = polys
    return rois


def longest_diameter(xy):
    """Longest distance between two outline points, and the widest extent perpendicular to it (both mm)."""
    d = xy[:, None, :] - xy[None, :, :]
    dist = np.sqrt((d ** 2).sum(-1))
    i, j = np.unravel_index(dist.argmax(), dist.shape)
    axis = (xy[j] - xy[i]) / max(dist[i, j], 1e-9)
    perp = np.array([-axis[1], axis[0]])
    proj = xy @ perp
    return float(dist[i, j]), float(proj.max() - proj.min()), xy[i], xy[j]


def polygon_area(xy):
    x, y = xy[:, 0], xy[:, 1]
    return 0.5 * abs(float(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1))))


def measure(polys, slice_spacing_mm):
    """RECIST longest axial diameter = the largest in-slice diameter over all slices of the lesion."""
    best = None
    volume = 0.0
    for z, xy in polys:
        if len(xy) < 3:
            continue
        volume += polygon_area(xy) * slice_spacing_mm
        ld, sa, p, q = longest_diameter(xy)
        if best is None or ld > best["long_mm"]:
            best = {"long_mm": ld, "short_mm": sa, "z_mm": z, "p": p.tolist(), "q": q.tolist()}
    if best is None:
        raise SystemExit("outline has no usable slices")
    best.update(volume_ml=volume / 1000.0, slices=len({round(z, 2) for z, _ in polys}))
    return best


def render(ct, polys, m, path, label, window=(-600, 1500), crop_mm=90):
    """One axial slice (lung window) with the expert outline and the measured diameter."""
    from PIL import Image, ImageDraw
    zs = np.array([z for z, _ in ct])
    ds = pydicom.dcmread(ct[int(np.abs(zs - m["z_mm"]).argmin())][1])
    hu = ds.pixel_array.astype(float) * float(ds.RescaleSlope) + float(ds.RescaleIntercept)
    lo, hi = window[0] - window[1] / 2.0, window[0] + window[1] / 2.0
    img = np.clip((hu - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8)
    ox, oy = float(ds.ImagePositionPatient[0]), float(ds.ImagePositionPatient[1])
    sy, sx = float(ds.PixelSpacing[0]), float(ds.PixelSpacing[1])

    def px(pt):
        return ((pt[0] - ox) / sx, (pt[1] - oy) / sy)

    cx, cy = px(((m["p"][0] + m["q"][0]) / 2, (m["p"][1] + m["q"][1]) / 2))
    half = crop_mm / sx / 2
    box = [int(cx - half), int(cy - half), int(cx + half), int(cy + half)]
    scale = 640.0 / (box[2] - box[0])
    im = Image.fromarray(img).convert("RGB").crop(box).resize((640, 640), Image.LANCZOS)
    dr = ImageDraw.Draw(im)

    def t(pt):
        x, y = px(pt)
        return ((x - box[0]) * scale, (y - box[1]) * scale)

    for z, xy in polys:
        if abs(z - m["z_mm"]) < 1e-3:
            pts = [t(p) for p in xy]
            dr.line(pts + [pts[0]], fill=(57, 135, 229), width=2)
    dr.line([t(m["p"]), t(m["q"])], fill=(235, 104, 52), width=3)
    try:
        from PIL import ImageFont
        big, small = (ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", s) for s in (22, 16))
    except Exception:
        big = small = None
    dr.rectangle([0, 0, 640, 64], fill=(0, 0, 0))
    dr.text((14, 8), "%s:  %.1f mm" % (label, m["long_mm"]), fill=(240, 239, 236), font=big)
    dr.text((14, 38), "longest diameter (orange)   short axis %.1f mm   volume %.1f ml"
            % (m["short_mm"], m["volume_ml"]), fill=(195, 194, 183), font=small)
    im.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ct")
    ap.add_argument("rtstruct")
    ap.add_argument("--roi", help="ROI name (default: the largest one)")
    ap.add_argument("--png")
    ap.add_argument("--label", default="")
    a = ap.parse_args()
    ct = load_ct(a.ct)
    zs = np.array([z for z, _ in ct])
    spacing = float(np.median(np.abs(np.diff(zs))))
    rois = load_contours(a.rtstruct)
    results = {name: measure(p, spacing) for name, p in rois.items() if p}
    name = a.roi or max(results, key=lambda n: results[n]["volume_ml"])
    m = results[name]
    if a.png:
        render(ct, rois[name], m, a.png, a.label or name)
    print(json.dumps({"roi": name, "all_rois": sorted(results), "slice_spacing_mm": spacing,
                      "long_mm": round(m["long_mm"], 1), "short_mm": round(m["short_mm"], 1),
                      "volume_ml": round(m["volume_ml"], 2), "slices": m["slices"], "z_mm": m["z_mm"]}))


if __name__ == "__main__":
    main()

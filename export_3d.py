"""Build 3D surfaces for the browser viewer: the tumor from each scan's expert outline, plus the lungs of scan 1.

Needs: pydicom numpy pillow scipy scikit-image.  Run: python export_3d.py <patient folder>  -> docs/data/scene.json
"""
import json
import os
import sys

import numpy as np
import pydicom
from PIL import Image, ImageDraw
from scipy import ndimage
from skimage import measure as skm

import measure as M


def to_view(v_zyx_mm):
    """Patient mm (z, y, x) -> viewer (x, up, depth). A proper rotation, no mirroring."""
    z, y, x = v_zyx_mm[:, 0], v_zyx_mm[:, 1], v_zyx_mm[:, 2]
    return np.stack([x, z, -y], axis=1)


def mesh(mask, spacing, origin_zyx, sigma=1.0, step=1):
    vol = ndimage.gaussian_filter(mask.astype(np.float32), sigma)
    v, f, _, _ = skm.marching_cubes(vol, 0.5, spacing=spacing, step_size=step)
    return to_view(v + np.array(origin_zyx)), f


def tumor(ct, polys):
    zs = np.array([z for z, _ in ct])
    dz = float(np.median(np.abs(np.diff(zs))))
    ds = pydicom.dcmread(ct[0][1], stop_before_pixels=True)
    ox, oy = float(ds.ImagePositionPatient[0]), float(ds.ImagePositionPatient[1])
    sy, sx = float(ds.PixelSpacing[0]), float(ds.PixelSpacing[1])
    allxy = np.vstack([xy for _, xy in polys])
    c0, r0 = int((allxy[:, 0].min() - ox) / sx) - 4, int((allxy[:, 1].min() - oy) / sy) - 4
    c1, r1 = int((allxy[:, 0].max() - ox) / sx) + 5, int((allxy[:, 1].max() - oy) / sy) + 5
    zlist = sorted({round(z, 3) for z, _ in polys})
    zmin = zlist[0] - 2 * dz
    n = int(round((zlist[-1] - zlist[0]) / dz)) + 5
    mask = np.zeros((n, r1 - r0, c1 - c0), bool)
    for z, xy in polys:
        k = int(round((z - zmin) / dz))
        im = Image.new("1", (c1 - c0, r1 - r0), 0)
        pts = [((x - ox) / sx - c0, (y - oy) / sy - r0) for x, y in xy]
        ImageDraw.Draw(im).polygon(pts, fill=1)
        mask[k] ^= np.array(im, bool)   # XOR so an inner outline cuts a hole
    return mesh(mask, (dz, sy, sx), (zmin, oy + r0 * sy, ox + c0 * sx), step=2)


def lungs(ct, down=3):
    files = [f for _, f in ct][::down]
    zs = [z for z, _ in ct][::down]
    first = pydicom.dcmread(files[0])
    sy, sx = float(first.PixelSpacing[0]) * down, float(first.PixelSpacing[1]) * down
    ox, oy = float(first.ImagePositionPatient[0]), float(first.ImagePositionPatient[1])
    vol = np.stack([pydicom.dcmread(f).pixel_array[::down, ::down].astype(np.int16) for f in files])
    hu = vol * float(first.RescaleSlope) + float(first.RescaleIntercept)
    air = hu < -350
    lab, n = ndimage.label(air)
    border = set(np.unique(lab[:, 0, :])) | set(np.unique(lab[:, -1, :])) | set(np.unique(lab[:, :, 0])) | set(np.unique(lab[:, :, -1]))
    sizes = ndimage.sum(air, lab, range(1, n + 1))
    keep = [i + 1 for i in np.argsort(sizes)[::-1] if (i + 1) not in border][:2]
    m = ndimage.binary_closing(np.isin(lab, keep), iterations=2)
    return mesh(m, (abs(zs[1] - zs[0]), sy, sx), (min(zs), oy, ox), sigma=1.2, step=2)


def pack(v, f, centre):
    return {"v": np.round(v - centre, 1).ravel().tolist(), "f": f.astype(int).ravel().tolist()}


def main():
    folder = sys.argv[1]
    scans = [("scan1", "CT_236", "RTSTRUCT_TEST", "GTVp_test_man"), ("scan2", "CT_213", "RTSTRUCT_RETEST", "GTVp_retest_man")]
    scene = {}
    for key, ctd, rtd, roi in scans:
        ct = M.load_ct(os.path.join(folder, ctd))
        polys = M.load_contours(os.path.join(folder, rtd))[roi]
        m = M.measure(polys, abs(ct[1][0] - ct[0][0]))
        v, f = tumor(ct, polys)
        centre = v.mean(axis=0)          # each scan is centred on its own tumor so the two can be overlaid
        line = to_view(np.array([[m["z_mm"], m["p"][1], m["p"][0]], [m["z_mm"], m["q"][1], m["q"][0]]])) - centre
        scene[key] = {"tumor": pack(v, f, centre), "line": np.round(line, 1).ravel().tolist(),
                      "long_mm": round(m["long_mm"], 1), "short_mm": round(m["short_mm"], 1),
                      "volume_ml": round(m["volume_ml"], 1)}
        if key == "scan1":
            lv, lf = lungs(ct)
            scene["lungs"] = pack(lv, lf, centre)
        print(key, "tumor tris", len(f))
    os.makedirs("docs/data", exist_ok=True)
    json.dump(scene, open("docs/data/scene.json", "w"), separators=(",", ":"))
    print("lung tris", len(scene["lungs"]["f"]) // 3, "file MB", round(os.path.getsize("docs/data/scene.json") / 1e6, 2))


if __name__ == "__main__":
    main()

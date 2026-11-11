"""Synthetic patients -> report text + gold labels. No patient data: every case is invented.

Edge cases carry a hand-written `expected` label (checked against recist.py in test_cases.py).
Random cases get their gold label from recist.py on the structured truth.
Run: python3 make_cases.py  -> cases.json
"""
import json
import random

from recist import PRESENT, Lesion, assess

SEED = 7
LABELS = ["CR", "PR", "SD", "PD"]

# name, organ, nodal
SITES = [
    ("segment 6 liver lesion", "liver", False), ("segment 4 liver lesion", "liver", False),
    ("segment 8 liver lesion", "liver", False), ("right upper lobe nodule", "lung", False),
    ("left lower lobe mass", "lung", False), ("right lower lobe nodule", "lung", False),
    ("left adrenal mass", "adrenal", False), ("splenic lesion", "spleen", False),
    ("right renal mass", "kidney", False), ("pancreatic tail mass", "pancreas", False),
    ("left para-aortic lymph node", "retroperitoneum", True), ("subcarinal lymph node", "mediastinum", True),
    ("right hilar lymph node", "hilum", True), ("left axillary lymph node", "axilla", True),
    ("portocaval lymph node", "abdomen", True),
]
SITE = {n: (o, nod) for n, o, nod in SITES}
NON_MEASURABLE = [("sclerotic bone lesions", "bone"), ("small right pleural effusion", "pleura"),
                  ("peritoneal thickening", "peritoneum")]


def les(name, sizes, measurable=True):
    organ, nodal = SITE.get(name, (dict(NON_MEASURABLE).get(name, "other"), False))
    return {"name": name, "organ": organ, "nodal": nodal, "measurable": measurable, "sizes": sizes}


def edge_cases():
    P = PRESENT
    return [
        ("node_12mm_is_non_target", "SD", [
            les("segment 6 liver lesion", [(40, 30), (30, 22)]),
            les("left para-aortic lymph node", [(20, 12), (12, 8)])], False),
        ("node_15mm_is_target", "PR", [
            les("right upper lobe nodule", [(20, 15), (16, 12)]),
            les("right hilar lymph node", [(25, 15), (24, 8)])], False),
        ("three_liver_lesions_two_targets", "PR", [
            les("segment 6 liver lesion", [(40, 30), (30, 22)]), les("segment 4 liver lesion", [(30, 22), (22, 16)]),
            les("segment 8 liver lesion", [(25, 20), (25, 20)]), les("left lower lobe mass", [(20, 15), (10, 8)])], False),
        ("seven_lesions_five_targets", "PR", [
            les("segment 6 liver lesion", [(50, 40), (34, 28)]), les("segment 4 liver lesion", [(45, 35), (30, 24)]),
            les("left lower lobe mass", [(40, 30), (28, 20)]), les("right upper lobe nodule", [(35, 28), (24, 18)]),
            les("right renal mass", [(30, 22), (20, 15)]), les("left adrenal mass", [(28, 20), (28, 20)]),
            les("splenic lesion", [(26, 20), (26, 20)])], False),
        ("plus_19_percent_is_sd", "SD", [
            les("segment 6 liver lesion", [(60, 45), (70, 50)]), les("left lower lobe mass", [(40, 30), (49, 35)])], False),
        ("plus_20_percent_is_pd", "PD", [
            les("segment 6 liver lesion", [(60, 45), (71, 50)]), les("left lower lobe mass", [(40, 30), (49, 35)])], False),
        ("plus_20_percent_but_4mm_is_sd", "SD", [
            les("right upper lobe nodule", [(10, 8), (12, 9)]), les("segment 4 liver lesion", [(10, 8), (12, 10)])], False),
        ("plus_25_percent_and_5mm_is_pd", "PD", [
            les("right upper lobe nodule", [(10, 8), (13, 9)]), les("segment 4 liver lesion", [(10, 8), (12, 10)])], False),
        ("pd_from_nadir_not_baseline", "PD", [
            les("segment 6 liver lesion", [(60, 45), (30, 22), (37, 28)]),
            les("left lower lobe mass", [(40, 30), (20, 15), (25, 18)])], False),
        ("pr_held_after_small_regrowth", "PR", [
            les("segment 6 liver lesion", [(60, 45), (30, 22), (33, 25)]),
            les("left lower lobe mass", [(40, 30), (20, 15), (25, 18)])], False),
        ("new_lesion_with_shrinking_targets", "PD", [
            les("segment 6 liver lesion", [(60, 45), (36, 28)]), les("left lower lobe mass", [(40, 30), (24, 18)]),
            les("segment 4 liver lesion", [None, (12, 10)])], False),
        ("new_node_under_10mm_is_not_new_lesion", "PR", [
            les("segment 6 liver lesion", [(60, 45), (36, 28)]), les("left lower lobe mass", [(40, 30), (24, 18)]),
            les("left axillary lymph node", [None, (9, 7)])], False),
        ("cr_with_residual_8mm_node", "CR", [
            les("right upper lobe nodule", [(20, 15), (0, 0)]), les("right hilar lymph node", [(30, 18), (12, 8)])], False),
        ("node_10mm_blocks_cr", "PR", [
            les("right upper lobe nodule", [(20, 15), (0, 0)]), les("right hilar lymph node", [(30, 18), (14, 10)])], False),
        ("target_cr_non_target_persists", "PR", [
            les("segment 6 liver lesion", [(30, 22), (0, 0)]), les("sclerotic bone lesions", [P, P], measurable=False)], False),
        ("non_target_unequivocal_progression", "PD", [
            les("segment 6 liver lesion", [(30, 22), (30, 22)]),
            les("peritoneal thickening", [P, P], measurable=False)], True),
        ("node_long_axis_trap", "CR", [
            les("left lower lobe mass", [(20, 15), (0, 0)]), les("subcarinal lymph node", [(30, 16), (28, 9)])], False),
        ("three_nodes_two_targets", "PR", [
            les("subcarinal lymph node", [(30, 22), (20, 14)]), les("left para-aortic lymph node", [(28, 20), (18, 12)]),
            les("left axillary lymph node", [(25, 18), (25, 18)]), les("segment 6 liver lesion", [(30, 22), (22, 16)])], False),
        ("sub_centimetre_lesion_is_non_target", "PR", [
            les("left lower lobe mass", [(40, 30), (28, 20)]), les("right upper lobe nodule", [(8, 6), (9, 7)])], False),
        ("minus_29_percent_is_sd", "SD", [
            les("segment 6 liver lesion", [(60, 45), (43, 30)]), les("left lower lobe mass", [(40, 30), (28, 20)])], False),
    ]


def random_case(rng):
    n_exams = rng.choice([2, 2, 3, 4])
    names = rng.sample([s[0] for s in SITES], rng.randint(2, 6))
    trend = rng.choice(["shrink", "shrink", "stable", "grow", "rebound", "vanish"])
    lesions = []
    for name in names:
        nodal = SITE[name][1]
        short = rng.randint(8, 28) if nodal else rng.randint(6, 40)
        long_ = short + rng.randint(2, 14)
        sizes, cur = [(long_, short)], float(long_)
        for t in range(1, n_exams):
            f = {"shrink": rng.uniform(0.55, 0.9), "stable": rng.uniform(0.92, 1.1), "grow": rng.uniform(1.05, 1.4),
                 "rebound": rng.uniform(0.5, 0.8) if t == 1 else rng.uniform(1.1, 1.5),
                 "vanish": rng.uniform(0.3, 0.6) if t < n_exams - 1 else 0.0}[trend]
            cur *= f
            lg = int(round(cur))
            if lg < 3 and not nodal:
                lg = 0
            if nodal and trend == "vanish" and t == n_exams - 1:
                lg = rng.randint(8, 12)
            sh = 0 if lg == 0 else max(1, int(round(lg * short / float(long_))))
            sizes.append((lg, sh))
        lesions.append(les(name, sizes))
    if rng.random() < 0.3:
        nm = rng.choice(NON_MEASURABLE)[0]
        gone = trend == "vanish" and rng.random() < 0.6
        lesions.append(les(nm, [PRESENT] * (n_exams - 1) + [(0, 0) if gone else PRESENT], measurable=False))
    if rng.random() < 0.15:
        free = [s[0] for s in SITES if s[0] not in names and not s[2]]
        sh = rng.randint(6, 20)
        lesions.append(les(rng.choice(free), [None] * (n_exams - 1) + [(sh + rng.randint(1, 6), sh)]))
    return lesions, (rng.random() < 0.05)


def to_lesions(case_lesions):
    return [Lesion(l["name"], l["organ"], l["nodal"], [tuple(s) if isinstance(s, list) else s for s in l["sizes"]],
                   l["measurable"]) for l in case_lesions]


# ---------- report text ----------
def exam_name(t):
    return "BASELINE" if t == 0 else "FOLLOW-UP %d" % t


def fmt(size, cm):
    a, b = size
    return "%.1f x %.1f cm" % (a / 10.0, b / 10.0) if cm else "%d x %d mm" % (a, b)


def render(lesions, nontarget_pd, rng):
    """Findings only (no impression). Styles: mm or cm, shuffled order, 'unchanged', 'resolved'."""
    cm = rng.random() < 0.35
    n = len(lesions[0]["sizes"])
    out = ["CT CHEST, ABDOMEN AND PELVIS WITH CONTRAST. Serial exams for one patient, findings only."]
    for t in range(n):
        out.append("")
        out.append("%s:" % exam_name(t))
        order = list(lesions)
        rng.shuffle(order)
        for l in order:
            s, prev = l["sizes"][t], (l["sizes"][t - 1] if t else None)
            name = l["name"]
            if s is None:
                continue
            if not l["measurable"]:
                if t == 0:
                    line = "%s, not measurable." % name.capitalize()
                elif s == PRESENT:
                    line = ("Marked, unequivocal increase in %s." % name) if (nontarget_pd and t == n - 1) \
                        else "%s persist, not measurable." % name.capitalize()
                else:
                    line = "%s have resolved." % name.capitalize()
            elif prev is None and t > 0:
                line = "New %s measuring %s." % (name, fmt(s, cm))
            elif tuple(s) == (0, 0):
                line = rng.choice(["The %s has resolved.", "The %s is no longer visible."]) % name
            elif t > 0 and tuple(s) == tuple(prev) and rng.random() < 0.6:
                line = "The %s is unchanged." % name
            elif t > 0:
                line = ("The %s now measures %s." if rng.random() < 0.5 else "%s: %s.") % (name, fmt(s, cm))
                line = line[0].upper() + line[1:]
            else:
                line = "%s measuring %s." % (name.capitalize(), fmt(s, cm))
            out.append("- " + line)
    return "\n".join(out)


def build(n_random=40, seed=SEED):
    rng = random.Random(seed)
    cases = []
    for cid, expected, lesions, npd in edge_cases():
        cases.append({"id": cid, "kind": "edge", "expected": expected, "lesions": lesions, "nontarget_pd": npd})
    i = 0
    while sum(c["kind"] == "random" for c in cases) < n_random:
        lesions, npd = random_case(rng)
        t = len(lesions[0]["sizes"]) - 1
        r = assess(to_lesions(lesions), t, npd)
        if r["overall"] not in LABELS or not r["targets"]:
            continue  # keep the set to measurable disease with one of the four responses
        i += 1
        cases.append({"id": "random_%02d" % i, "kind": "random", "expected": r["overall"], "lesions": lesions,
                      "nontarget_pd": npd})
    for c in cases:
        c["exam"] = len(c["lesions"][0]["sizes"]) - 1
        c["report"] = render(c["lesions"], c["nontarget_pd"], rng)
        # the report's own impression; wrong on purpose in about 30% of cases (for the second-read check)
        c["stated"] = rng.choice([x for x in LABELS if x != c["expected"]]) if rng.random() < 0.3 else c["expected"]
    return cases


if __name__ == "__main__":
    cases = build()
    json.dump(cases, open("cases.json", "w"), indent=1)
    from collections import Counter
    print(len(cases), "cases", dict(Counter(c["expected"] for c in cases)),
          "wrong impressions:", sum(c["stated"] != c["expected"] for c in cases))

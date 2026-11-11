"""Compare three ways to get a RECIST response from a report:

A. LLM alone:            report -> LLM (with the RECIST rules in the prompt) -> response
B. LLM extracts, code decides: report -> LLM -> lesion JSON -> recist.py -> response + audit trail
C. Oracle:               structured truth -> recist.py (upper bound)

Also the "second read": flag reports whose stated impression disagrees with pipeline B.
Run: python3 run_eval.py [model ...]     (default: qwen2.5:7b-instruct)
Raw model outputs are cached in results/ so a rerun is free and every answer can be audited.
"""
import hashlib
import json
import os
import re
import sys
import time
import urllib.request
from collections import Counter

from make_cases import LABELS, to_lesions
from recist import PRESENT, Lesion, assess

OLLAMA = "http://localhost:11434/api/chat"

RULES = """RECIST 1.1 rules:
- Target lesions are chosen at baseline: non-nodal lesions with longest diameter >= 10 mm, lymph nodes with
  short axis >= 15 mm. At most 5 targets in total and at most 2 per organ (lymph nodes count as one organ),
  largest first. Everything else present at baseline is a non-target lesion, except lymph nodes with short
  axis < 10 mm, which are normal and not followed.
- Sum of diameters = longest diameter of non-nodal targets + short axis of nodal targets.
- CR: all non-nodal targets gone and every nodal target < 10 mm short axis.
- PD: sum increased >= 20% from the smallest earlier sum (nadir, baseline included) AND by >= 5 mm.
- PR: sum decreased >= 30% from baseline. SD: none of the above. Check CR, then PD, then PR.
- A new lesion means PD (a new lymph node only counts if its short axis is >= 10 mm).
- Unequivocal progression of non-target lesions means PD.
- Target CR with non-target lesions still present is PR overall."""

PROMPT_ALONE = """You are assisting with oncology imaging. Apply RECIST 1.1 to the serial CT findings below and
give the overall response at the LAST exam compared with the earlier exams.

%s

Answer with JSON only: {"response": "CR" | "PR" | "SD" | "PD", "reason": "<one sentence with the numbers>"}

FINDINGS:
%s"""

PROMPT_EXTRACT = """Extract every lesion from the serial CT findings below. Do not judge the response.

Exams are numbered 0 = BASELINE, 1 = FOLLOW-UP 1, 2 = FOLLOW-UP 2, and so on.
Answer with JSON only, in this shape:
{"lesions": [
  {"name": "<as written>", "organ": "<organ>", "is_lymph_node": false, "measurable": true,
   "sizes": [{"exam": 0, "long_mm": 40, "short_mm": 30}, {"exam": 1, "long_mm": 30, "short_mm": 22}]},
  {"name": "<as written>", "organ": "<organ>", "is_lymph_node": true, "measurable": true,
   "sizes": [{"exam": 0, "long_mm": 22, "short_mm": 16}, {"exam": 1, "long_mm": 22, "short_mm": 16}]}],
 "nontarget_unequivocal_progression": true|false}
One object per lesion: a report that mentions five lesions gives five objects. Do not skip any lesion.

Rules for the extraction:
- All sizes in millimetres (convert cm to mm). long_mm is the larger number, short_mm the smaller.
- Give one sizes entry for every exam in which the lesion exists. "Unchanged" means the same size as the exam before.
- Resolved or no longer visible: long_mm 0 and short_mm 0.
- A lesion that first appears in a follow-up has no entry for the earlier exams.
- Not measurable lesions: "measurable": false, and each sizes entry is {"exam": n, "present": true|false}.

FINDINGS:
%s"""


def ask(model, prompt):
    body = {"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False, "format": "json",
            "think": False, "options": {"temperature": 0, "seed": 7, "num_ctx": 8192}}
    req = urllib.request.Request(OLLAMA, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode())["message"]["content"]


def cached(model, case, kind, prompt):
    d = os.path.join("results", re.sub(r"[^a-zA-Z0-9.]+", "_", model))
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "%s.%s.%s.json" % (case["id"], kind, hashlib.sha1(prompt.encode()).hexdigest()[:8]))
    if os.path.exists(path):
        return json.load(open(path))["raw"]
    t0 = time.time()
    raw = ask(model, prompt)
    json.dump({"raw": raw, "seconds": round(time.time() - t0, 1)}, open(path, "w"), indent=1)
    return raw


def parse_alone(raw):
    try:
        r = str(json.loads(raw).get("response", "")).strip().upper()
        return r if r in LABELS else "INVALID"
    except Exception:
        return "INVALID"


def parse_extraction(raw, n_exams):
    """LLM JSON -> (lesions, nontarget_pd). Raises ValueError with a reason if the JSON breaks the schema."""
    try:
        d = json.loads(raw)
    except Exception:
        raise ValueError("not JSON")
    if not isinstance(d, dict) or not isinstance(d.get("lesions"), list) or not d["lesions"]:
        raise ValueError("no lesions list")
    out = []
    for i, l in enumerate(d["lesions"]):
        if not isinstance(l, dict) or not isinstance(l.get("sizes"), list):
            raise ValueError("lesion %d has no sizes" % i)
        measurable = bool(l.get("measurable", True))
        sizes = [None] * n_exams
        for s in l["sizes"]:
            e = s.get("exam") if isinstance(s, dict) else None
            if not isinstance(e, int) or not 0 <= e < n_exams:
                raise ValueError("lesion %d: bad exam index %r" % (i, e))
            if measurable:
                a, b = s.get("long_mm"), s.get("short_mm")
                if not all(isinstance(x, (int, float)) and x >= 0 for x in (a, b)):
                    raise ValueError("lesion %d exam %d: sizes are not numbers" % (i, e))
                sizes[e] = (int(round(a)), int(round(b)))
            else:
                sizes[e] = PRESENT if s.get("present", True) else (0, 0)
        out.append(Lesion(str(l.get("name", "lesion %d" % i)), str(l.get("organ", "")), bool(l.get("is_lymph_node")),
                          sizes, measurable))
    return out, bool(d.get("nontarget_unequivocal_progression", False))


def extraction_errors(case, got):
    """Compare extracted lesions with the truth. Returns a list of error tags."""
    truth = to_lesions(case["lesions"])
    by_name = {re.sub(r"^(the|new) ", "", g.lid.strip().lower()): g for g in got}
    errs = []
    for t in truth:
        g = by_name.pop(t.lid.lower(), None)
        if g is None:
            errs.append("missed_or_renamed_lesion")
            continue
        if g.nodal != t.nodal:
            errs.append("lymph_node_flag")
        if g.measurable != t.measurable:
            errs.append("measurable_flag")
        for a, b in zip(g.sizes, t.sizes):
            if a == b:
                continue
            if isinstance(a, tuple) and isinstance(b, tuple) and b[0] and a[0] in (b[0] * 10, b[0] // 10):
                errs.append("cm_mm_unit")
            elif a is None or b is None:
                errs.append("missing_or_extra_exam")
            else:
                errs.append("wrong_size")
            break
    errs += ["extra_lesion"] * len(by_name)
    return errs


def run(model, cases):
    rows = []
    for n, c in enumerate(cases):
        n_exams = c["exam"] + 1
        a = parse_alone(cached(model, c, "alone", PROMPT_ALONE % (RULES, c["report"])))
        raw = cached(model, c, "extract", PROMPT_EXTRACT % c["report"])
        try:
            lesions, npd = parse_extraction(raw, n_exams)
            r = assess(lesions, c["exam"], npd)
            b, why, errs = r["overall"], r["why"], extraction_errors(c, lesions)
        except ValueError as e:
            b, why, errs = "INVALID", [str(e)], ["schema: %s" % e]
        rows.append({"id": c["id"], "kind": c["kind"], "gold": c["expected"], "stated": c["stated"],
                     "alone": a, "extract": b, "why": why, "extraction_errors": errs})
        sys.stderr.write("\r%s %d/%d" % (model, n + 1, len(cases)))
    sys.stderr.write("\n")
    return rows


def pct(k, n):
    return "%d/%d (%.0f%%)" % (k, n, 100.0 * k / n) if n else "-"


def summarise(model, rows):
    edge = [r for r in rows if r["kind"] == "edge"]
    rnd = [r for r in rows if r["kind"] == "random"]
    out = {"model": model}
    for key in ("alone", "extract"):
        out[key] = {"all": pct(sum(r[key] == r["gold"] for r in rows), len(rows)),
                    "edge": pct(sum(r[key] == r["gold"] for r in edge), len(edge)),
                    "random": pct(sum(r[key] == r["gold"] for r in rnd), len(rnd)),
                    "failed_edge_cases": [r["id"] for r in edge if r[key] != r["gold"]],
                    "confusion": dict(Counter("%s->%s" % (r["gold"], r[key]) for r in rows if r[key] != r["gold"]))}
    out["extraction_errors"] = dict(Counter(e.split(":")[0] for r in rows for e in r["extraction_errors"]))
    out["clean_extractions"] = pct(sum(not r["extraction_errors"] for r in rows), len(rows))
    # second read: does pipeline B catch the reports whose stated impression is wrong?
    wrong = [r for r in rows if r["stated"] != r["gold"]]
    flagged = [r for r in rows if r["extract"] != r["stated"]]
    hit = [r for r in flagged if r["stated"] != r["gold"]]
    out["second_read"] = {"wrong_impressions": len(wrong), "flagged": len(flagged),
                          "recall": pct(len(hit), len(wrong)), "precision": pct(len(hit), len(flagged))}
    return out


def main():
    models = sys.argv[1:] or ["qwen2.5:7b-instruct"]
    cases = json.load(open("cases.json"))
    oracle = sum(assess(to_lesions(c["lesions"]), c["exam"], c["nontarget_pd"])["overall"] == c["expected"] for c in cases)
    summaries = []
    for m in models:
        rows = run(m, cases)
        json.dump(rows, open(os.path.join("results", re.sub(r"[^a-zA-Z0-9.]+", "_", m) + ".rows.json"), "w"), indent=1)
        summaries.append(summarise(m, rows))
    json.dump({"oracle": pct(oracle, len(cases)), "models": summaries}, open("results/summary.json", "w"), indent=1)
    print("Oracle (truth -> recist.py): %s" % pct(oracle, len(cases)))
    for s in summaries:
        print("\n== %s" % s["model"])
        print("A. LLM alone            all %s | edge %s | random %s" % (s["alone"]["all"], s["alone"]["edge"], s["alone"]["random"]))
        print("B. LLM extracts + code  all %s | edge %s | random %s" % (s["extract"]["all"], s["extract"]["edge"], s["extract"]["random"]))
        print("   clean extractions %s, errors %s" % (s["clean_extractions"], s["extraction_errors"]))
        print("   A fails edge cases: %s" % ", ".join(s["alone"]["failed_edge_cases"]))
        print("   B fails edge cases: %s" % ", ".join(s["extract"]["failed_edge_cases"]))
        print("   second read: %s" % s["second_read"])


if __name__ == "__main__":
    main()

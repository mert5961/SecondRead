"""RECIST 1.1 decision logic with an audit trail.

Source: Eisenhauer et al., "New response evaluation criteria in solid tumours: revised RECIST
guideline (version 1.1)", Eur J Cancer 45 (2009) 228-247.

Input is structured lesion measurements over time (what a measurement model would output).
All sizes are integer millimetres, so every threshold is exact integer arithmetic.
Not a medical device. Synthetic data only.
"""
from typing import Dict, List, Optional, Tuple, Union

CR, PR, SD, PD, NE = "CR", "PR", "SD", "PD", "NE"
NON_CR_NON_PD, NA = "NON_CR_NON_PD", "NA"

MIN_NON_NODAL_MM = 10      # measurable non-nodal lesion: longest diameter >= 10 mm
MIN_NODE_TARGET_MM = 15    # lymph node can be a target: short axis >= 15 mm
NODE_NORMAL_BELOW_MM = 10  # lymph node with short axis < 10 mm is normal
MAX_TARGETS = 5
MAX_PER_ORGAN = 2
NODE_ORGAN = "lymph nodes"  # assumption: lymph nodes count as one organ (max 2 nodal targets)

PRESENT = "present"         # a non-measurable lesion that is still there
Size = Union[Tuple[int, int], str, None]


class Lesion:
    """One lesion followed over time.

    sizes[t] is (long_mm, short_mm), PRESENT (non-measurable, still there), or None.
    (0, 0) means the lesion has disappeared. None at baseline (t=0) means the lesion did not
    exist yet (a new lesion later). None at a follow-up means "not reported".
    """

    def __init__(self, lid: str, organ: str, nodal: bool, sizes: List[Size], measurable: bool = True):
        self.lid, self.organ, self.nodal, self.measurable = lid, organ.strip().lower(), nodal, measurable
        self.sizes = []
        for s in sizes:
            if isinstance(s, (tuple, list)):
                a, b = int(s[0]), int(s[1])
                s = (max(a, b), min(a, b))
            self.sizes.append(s)

    def organ_key(self) -> str:
        return NODE_ORGAN if self.nodal else self.organ

    def diameter(self, t: int) -> Optional[int]:
        """RECIST diameter: short axis for lymph nodes, longest diameter otherwise."""
        s = self.sizes[t] if t < len(self.sizes) else None
        if not isinstance(s, tuple):
            return None
        return s[1] if self.nodal else s[0]

    def at_baseline(self) -> bool:
        return self.sizes[0] is not None


def is_target_candidate(l: Lesion) -> bool:
    d = l.diameter(0)
    if not l.measurable or d is None:
        return False
    return d >= (MIN_NODE_TARGET_MM if l.nodal else MIN_NON_NODAL_MM)


def select_targets(lesions: List[Lesion]) -> Tuple[List[Lesion], List[str]]:
    """Up to 5 targets, up to 2 per organ, largest first (ties broken by lesion id)."""
    why = []
    cands = sorted([l for l in lesions if is_target_candidate(l)], key=lambda l: (-l.diameter(0), l.lid))
    targets, per_organ = [], {}  # type: List[Lesion], Dict[str, int]
    for l in cands:
        k = l.organ_key()
        if len(targets) >= MAX_TARGETS:
            why.append("%s: non-target, already %d targets" % (l.lid, MAX_TARGETS))
        elif per_organ.get(k, 0) >= MAX_PER_ORGAN:
            why.append("%s: non-target, already %d targets in %s" % (l.lid, MAX_PER_ORGAN, k))
        else:
            targets.append(l)
            per_organ[k] = per_organ.get(k, 0) + 1
            why.append("%s: target, %s %d mm" % (l.lid, "short axis" if l.nodal else "longest diameter", l.diameter(0)))
    for l in lesions:
        if l.at_baseline() and l not in cands:
            if not l.measurable:
                why.append("%s: non-target, not measurable" % l.lid)
            elif l.nodal:
                why.append("%s: non-target, node short axis %s mm < %d" % (l.lid, l.diameter(0), MIN_NODE_TARGET_MM))
            else:
                why.append("%s: non-target, longest diameter %s mm < %d" % (l.lid, l.diameter(0), MIN_NON_NODAL_MM))
    return targets, why


def sum_of_diameters(targets: List[Lesion], t: int) -> Optional[int]:
    ds = [l.diameter(t) for l in targets]
    return None if any(d is None for d in ds) else sum(ds)


def _gone(l: Lesion, t: int) -> Optional[bool]:
    """True if the lesion no longer counts as disease at time t. None if not reported."""
    s = l.sizes[t] if t < len(l.sizes) else None
    if s is None:
        return None
    if s == PRESENT:
        return False
    d = l.diameter(t)
    return d < NODE_NORMAL_BELOW_MM if l.nodal else d == 0


def target_response(targets: List[Lesion], t: int) -> Tuple[str, List[str], Dict[str, Optional[int]]]:
    nums = {"baseline_sum": None, "nadir": None, "sum": None}  # type: Dict[str, Optional[int]]
    if not targets:
        return NA, ["no target lesions"], nums
    sums = [sum_of_diameters(targets, i) for i in range(t + 1)]
    if sums[0] is None or sums[t] is None:
        return NE, ["a target lesion has no measurement at baseline or at this exam"], nums
    prior = [s for s in sums[:t] if s is not None]
    base, cur, nadir = sums[0], sums[t], min(prior)
    nums.update(baseline_sum=base, nadir=nadir, sum=cur)
    if all(_gone(l, t) for l in targets):
        return CR, ["CR: all non-nodal targets gone and all nodal targets < %d mm short axis (sum %d mm)"
                    % (NODE_NORMAL_BELOW_MM, cur)], nums
    if cur * 10 >= nadir * 12 and cur - nadir >= 5:
        return PD, ["PD: sum %d mm vs nadir %d mm = %+d mm (%s), needs >= +20%% and >= +5 mm"
                    % (cur, nadir, cur - nadir, _pct(cur, nadir))], nums
    if cur * 10 <= base * 7:
        return PR, ["PR: sum %d mm vs baseline %d mm (%s), needs <= -30%%" % (cur, base, _pct(cur, base))], nums
    return SD, ["SD: sum %d mm; vs baseline %d mm (%s), vs nadir %d mm (%s, %+d mm)"
                % (cur, base, _pct(cur, base), nadir, _pct(cur, nadir), cur - nadir)], nums


def _pct(cur: int, ref: int) -> str:
    return "n/a" if ref == 0 else "%+.1f%%" % (100.0 * (cur - ref) / ref)


def nontarget_response(nontargets: List[Lesion], t: int, unequivocal_progression: bool) -> Tuple[str, List[str]]:
    if not nontargets:
        return NA, ["no non-target lesions"]
    if unequivocal_progression:
        return PD, ["non-target PD: unequivocal progression reported"]
    left = [l.lid for l in nontargets if not _gone(l, t)]
    if not left:
        return CR, ["non-target CR: all non-target lesions gone, nodes < %d mm" % NODE_NORMAL_BELOW_MM]
    return NON_CR_NON_PD, ["non-target non-CR/non-PD: still present: " + ", ".join(left)]


def new_lesions(lesions: List[Lesion], t: int) -> List[str]:
    """Lesions absent at baseline and present at any exam up to t. A new node needs short axis >= 10 mm."""
    out = []
    for l in lesions:
        if l.at_baseline():
            continue
        for i in range(1, t + 1):
            s = l.sizes[i] if i < len(l.sizes) else None
            if s == PRESENT or (isinstance(s, tuple) and
                                (l.diameter(i) >= NODE_NORMAL_BELOW_MM if l.nodal else l.diameter(i) > 0)):
                out.append(l.lid)
                break
    return out


def assess(lesions: List[Lesion], t: int, nontarget_progression: bool = False) -> Dict:
    """Overall response at exam t (RECIST 1.1 Table 1; Table 2 when there are no targets)."""
    targets, why = select_targets(lesions)
    nontargets = [l for l in lesions if l.at_baseline() and l not in targets]
    t_resp, t_why, nums = target_response(targets, t)
    n_resp, n_why = nontarget_response(nontargets, t, nontarget_progression)
    new = new_lesions(lesions, t)
    why = why + t_why + n_why
    if new:
        overall = PD
        why.append("overall PD: new lesion(s): " + ", ".join(new))
    elif t_resp == PD or n_resp == PD:
        overall = PD
        why.append("overall PD: progression of %s lesions" % ("target" if t_resp == PD else "non-target"))
    elif t_resp == NE:
        overall = NE
        why.append("overall NE: targets not all evaluated")
    elif t_resp == NA:
        overall = n_resp  # Table 2: CR, NON_CR_NON_PD (or NA if there is no disease at all)
        why.append("overall %s: non-target disease only" % overall)
    elif t_resp == CR:
        overall = CR if n_resp in (CR, NA) else PR
        why.append("overall %s: target CR, non-target %s" % (overall, n_resp))
    else:
        overall = t_resp
        why.append("overall %s: target %s, non-target %s, no new lesions" % (overall, t_resp, n_resp))
    return {"overall": overall, "target": t_resp, "nontarget": n_resp, "new_lesions": new,
            "targets": [l.lid for l in targets], "nontargets": [l.lid for l in nontargets],
            "numbers": nums, "why": why}

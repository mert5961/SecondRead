"""Hand-made cases, one per RECIST 1.1 rule. Expected answers were worked out by hand, not by the code."""
import unittest

from recist import CR, NA, NON_CR_NON_PD, PD, PR, PRESENT, SD, NE, Lesion, assess, select_targets


def L(lid, organ, sizes, nodal=False, measurable=True):
    return Lesion(lid, organ, nodal, sizes, measurable)


class TargetSelection(unittest.TestCase):
    def test_non_nodal_needs_10mm(self):
        t, _ = select_targets([L("a", "lung", [(10, 8)]), L("b", "liver", [(9, 9)])])
        self.assertEqual([x.lid for x in t], ["a"])

    def test_node_needs_15mm_short_axis(self):
        t, _ = select_targets([L("n14", "mediastinum", [(30, 14)], nodal=True),
                               L("n15", "mediastinum", [(16, 15)], nodal=True)])
        self.assertEqual([x.lid for x in t], ["n15"])

    def test_two_per_organ(self):
        t, _ = select_targets([L("l1", "liver", [(40, 30)]), L("l2", "liver", [(30, 20)]),
                               L("l3", "liver", [(25, 20)]), L("p", "lung", [(20, 15)])])
        self.assertEqual(sorted(x.lid for x in t), ["l1", "l2", "p"])

    def test_five_total(self):
        ls = [L("liv1", "liver", [(50, 40)]), L("liv2", "liver", [(45, 40)]), L("lu1", "lung", [(40, 30)]),
              L("lu2", "lung", [(35, 30)]), L("kid", "kidney", [(30, 20)]), L("adr", "adrenal", [(28, 20)]),
              L("spl", "spleen", [(26, 20)])]
        t, _ = select_targets(ls)
        self.assertEqual(sorted(x.lid for x in t), ["kid", "liv1", "liv2", "lu1", "lu2"])

    def test_nodes_count_as_one_organ(self):
        ls = [L("n1", "mediastinum", [(30, 22)], nodal=True), L("n2", "retroperitoneum", [(28, 20)], nodal=True),
              L("n3", "axilla", [(25, 18)], nodal=True), L("liv", "liver", [(30, 20)])]
        t, _ = select_targets(ls)
        self.assertEqual(sorted(x.lid for x in t), ["liv", "n1", "n2"])

    def test_not_measurable_is_never_target(self):
        t, _ = select_targets([L("bone", "bone", [PRESENT], measurable=False)])
        self.assertEqual(t, [])


class TargetResponse(unittest.TestCase):
    def two(self, *sums):
        """liver + lung targets; each exam given as (liver_mm, lung_mm)."""
        return [L("liv", "liver", [(a, a - 2) for a, _ in sums]), L("lung", "lung", [(b, b - 2) for _, b in sums])]

    def test_pr_at_minus_30(self):
        self.assertEqual(assess(self.two((60, 40), (42, 28)), 1)["overall"], PR)   # 100 -> 70

    def test_sd_at_minus_29(self):
        self.assertEqual(assess(self.two((60, 40), (43, 28)), 1)["overall"], SD)   # 100 -> 71

    def test_sd_at_plus_19(self):
        self.assertEqual(assess(self.two((60, 40), (70, 49)), 1)["overall"], SD)   # 100 -> 119

    def test_pd_at_plus_20(self):
        self.assertEqual(assess(self.two((60, 40), (71, 49)), 1)["overall"], PD)   # 100 -> 120

    def test_plus_20_percent_but_only_4mm_is_sd(self):
        self.assertEqual(assess(self.two((10, 10), (12, 12)), 1)["overall"], SD)   # 20 -> 24

    def test_plus_25_percent_and_5mm_is_pd(self):
        self.assertEqual(assess(self.two((10, 10), (13, 12)), 1)["overall"], PD)   # 20 -> 25

    def test_pd_is_measured_from_nadir(self):
        # 100 -> 50 -> 62: -38% from baseline but +24% and +12 mm from nadir
        r = assess(self.two((60, 40), (30, 20), (37, 25)), 2)
        self.assertEqual(r["overall"], PD)
        self.assertEqual(r["numbers"], {"baseline_sum": 100, "nadir": 50, "sum": 62})

    def test_pr_is_measured_from_baseline(self):
        # 100 -> 50 -> 58: +16% from nadir (not PD), -42% from baseline
        self.assertEqual(assess(self.two((60, 40), (30, 20), (33, 25)), 2)["overall"], PR)

    def test_baseline_counts_as_nadir(self):
        # 100 -> 130 -> 125: nadir is the baseline 100, so +25% is PD
        self.assertEqual(assess(self.two((60, 40), (80, 50), (75, 50)), 2)["overall"], PD)

    def test_node_uses_short_axis(self):
        # lung 20 -> 16, node short 15 -> 8 (long 25 -> 24): sum 35 -> 24 = -31% PR.
        # With the long axis it would be 45 -> 40 = SD.
        ls = [L("lung", "lung", [(20, 15), (16, 12)]), L("node", "hilum", [(25, 15), (24, 8)], nodal=True)]
        self.assertEqual(assess(ls, 1)["overall"], PR)

    def test_small_node_is_not_in_the_sum(self):
        # liver 40 -> 30 (-25% SD). Node short axis 12 is non-target; adding its long axis would give PR.
        ls = [L("liv", "liver", [(40, 30), (30, 22)]), L("node", "retroperitoneum", [(20, 12), (12, 8)], nodal=True)]
        r = assess(ls, 1)
        self.assertEqual((r["overall"], r["targets"]), (SD, ["liv"]))

    def test_cr_with_residual_small_node(self):
        ls = [L("lung", "lung", [(20, 15), (0, 0)]), L("node", "hilum", [(30, 18), (12, 8)], nodal=True)]
        r = assess(ls, 1)
        self.assertEqual((r["overall"], r["numbers"]["sum"]), (CR, 8))

    def test_node_at_10mm_is_not_cr(self):
        ls = [L("lung", "lung", [(20, 15), (0, 0)]), L("node", "hilum", [(30, 18), (14, 10)], nodal=True)]
        self.assertEqual(assess(ls, 1)["overall"], PR)   # 38 -> 10

    def test_missing_target_measurement_is_ne(self):
        ls = [L("liv", "liver", [(40, 30), None]), L("lung", "lung", [(20, 15), (20, 15)])]
        self.assertEqual(assess(ls, 1)["overall"], NE)


class Overall(unittest.TestCase):
    def test_new_lesion_beats_shrinking_targets(self):
        ls = [L("liv", "liver", [(60, 50), (36, 30)]), L("new", "lung", [None, (12, 10)])]
        self.assertEqual(assess(ls, 1)["overall"], PD)

    def test_new_node_under_10mm_is_not_a_new_lesion(self):
        ls = [L("liv", "liver", [(60, 50), (36, 30)]), L("newnode", "axilla", [None, (9, 7)], nodal=True)]
        self.assertEqual(assess(ls, 1)["overall"], PR)

    def test_new_node_at_10mm_is_a_new_lesion(self):
        ls = [L("liv", "liver", [(60, 50), (36, 30)]), L("newnode", "axilla", [None, (14, 10)], nodal=True)]
        self.assertEqual(assess(ls, 1)["overall"], PD)

    def test_target_cr_with_non_target_left_is_pr(self):
        ls = [L("liv", "liver", [(30, 20), (0, 0)]), L("bone", "bone", [PRESENT, PRESENT], measurable=False)]
        r = assess(ls, 1)
        self.assertEqual((r["target"], r["nontarget"], r["overall"]), (CR, NON_CR_NON_PD, PR))

    def test_target_cr_and_non_target_cr_is_cr(self):
        ls = [L("liv", "liver", [(30, 20), (0, 0)]), L("small", "lung", [(8, 6), (0, 0)])]
        self.assertEqual(assess(ls, 1)["overall"], CR)

    def test_non_target_progression_is_pd(self):
        ls = [L("liv", "liver", [(30, 20), (30, 20)]), L("bone", "bone", [PRESENT, PRESENT], measurable=False)]
        self.assertEqual(assess(ls, 1, nontarget_progression=True)["overall"], PD)

    def test_non_target_only_disease(self):
        ls = [L("bone", "bone", [PRESENT, PRESENT], measurable=False)]
        r = assess(ls, 1)
        self.assertEqual((r["target"], r["overall"]), (NA, NON_CR_NON_PD))

    def test_normal_baseline_node_is_not_a_lesion(self):
        # node short axis 8 mm at baseline is normal: not a target, not a non-target
        ls = [L("liv", "liver", [(30, 20), (0, 0)]), L("node", "abdomen", [(19, 8), (19, 8)], nodal=True)]
        r = assess(ls, 1)
        self.assertEqual((r["nontargets"], r["nontarget"], r["overall"]), ([], NA, CR))

    def test_normal_node_that_grows_is_flagged_for_review(self):
        ls = [L("liv", "liver", [(30, 20), (30, 20)]), L("node", "abdomen", [(19, 8), (25, 12)], nodal=True)]
        r = assess(ls, 1)
        self.assertEqual(r["overall"], SD)
        self.assertTrue(any(w.startswith("REVIEW") for w in r["why"]))

    def test_audit_trail_names_the_rule_and_numbers(self):
        ls = [L("liv", "liver", [(60, 50), (30, 20), (37, 30)])]
        why = " | ".join(assess(ls, 2)["why"])
        self.assertIn("nadir 30 mm", why)
        self.assertIn("+7 mm", why)


if __name__ == "__main__":
    unittest.main()

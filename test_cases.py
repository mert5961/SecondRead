"""The hand-written labels of the edge cases must agree with recist.py, and reports must contain every number."""
import unittest

from make_cases import build, edge_cases, to_lesions
from recist import assess


class EdgeCases(unittest.TestCase):
    def test_hand_labels_agree_with_rules(self):
        for cid, expected, lesions, npd in edge_cases():
            t = len(lesions[0]["sizes"]) - 1
            r = assess(to_lesions(lesions), t, npd)
            self.assertEqual(r["overall"], expected, "%s: %s" % (cid, r["why"]))

    def test_build_is_reproducible_and_complete(self):
        a, b = build(), build()
        self.assertEqual([c["report"] for c in a], [c["report"] for c in b])
        self.assertEqual(len(a), 60)
        self.assertTrue(all(c["report"].count("FOLLOW-UP") == c["exam"] for c in a))

    def test_every_lesion_is_named_in_its_report(self):
        for c in build():
            for l in c["lesions"]:
                self.assertIn(l["name"].lower(), c["report"].lower(), c["id"])


if __name__ == "__main__":
    unittest.main()

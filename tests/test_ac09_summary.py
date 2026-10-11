"""AC9: 集計を標準出力に表で出す。見出しの主語を下げる。

**「復元できない件数」とは書かない。** 写真が実際にどう扱われるかを決めるのは
取り込み側であって、この tool ではない。
"""

import os
import re
import shutil
import tempfile
import unittest

import support


def _mixed():
    return {
        "a/IMG_0001.jpg": b"\xff\xd8a",
        "a/IMG_0001.jpg.json": support.sidecar_bytes(),
        "a/IMG_0002.jpg": b"\xff\xd8b",
        "a/IMG_0003-edited.jpg": b"\xff\xd8c",
        "a/IMG_0003.jpg": b"\xff\xd8d",
        "a/IMG_0003.jpg.json": support.sidecar_bytes(),
        "b/IMG_0004.jpg": b"\xff\xd8e",
        "b/IMG_0004.jpg.json": support.sidecar_bytes(with_time=False),
        "b/IMG_0005.jpg": b"\xff\xd8f",
        "b/IMG_0005.jpg.json": b"not json at all",
    }


class TheSummary(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.takeout = os.path.join(self.root, "takeout")
        os.makedirs(self.takeout)
        support.write_tree(self.takeout, _mixed())
        self.result = support.run_cli([self.takeout])
        self.assertEqual(self.result.code, 0)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _count_for(self, label):
        for line in self.result.out.splitlines():
            if line.rstrip().endswith(label):
                return int(line.split()[0])
        raise AssertionError("集計に %r の行がありません:\n%s"
                             % (label, self.result.out))

    def test_it_says_matched_and_not_matched_by_this_tools_rules(self):
        self.assertIn("matched to a .json and read a capture time (matched)",
                      self.result.out)
        self.assertIn("not matched by this tool's rules", self.result.out)

    def test_it_does_not_claim_anything_is_unrecoverable(self):
        lowered = self.result.out.lower()
        for phrase in ("cannot be recovered", "unrecoverable",
                       "will lose", "restore"):
            self.assertNotIn(phrase, lowered)

    def test_the_reason_counts_add_up_to_the_not_matched_count(self):
        not_matched = self._count_for("not matched by this tool's rules")
        total_reasons = sum(
            self._count_for("  " + reason) for reason in (
                "no_sidecar", "unmatched_by_known_rules", "ambiguous_match",
                "sidecar_without_time", "unparsable_time",
                "undecodable_name"))
        self.assertEqual(not_matched, total_reasons)
        self.assertGreater(not_matched, 0, "この入力は 0 件ではない")

    def test_matched_plus_not_matched_is_the_number_of_media_files(self):
        total = self._count_for("media files looked at")
        self.assertEqual(
            total,
            self._count_for(
                "matched to a .json and read a capture time (matched)")
            + self._count_for("not matched by this tool's rules"))
        self.assertEqual(total, 6)

    def test_every_reason_is_shown_even_when_it_is_zero(self):
        """0 件でも空欄にしない。"""
        self.assertEqual(self._count_for("  undecodable_name"), 0)

    def test_the_counts_agree_with_the_csv(self):
        report = os.path.join(self.root, "plan.csv")
        self.assertEqual(
            support.run_cli([self.takeout, "--report", report]).code, 0)
        rows = support.rows_as_dicts(report)
        self.assertEqual(len(rows),
                         self._count_for("media files looked at"))
        self.assertEqual(
            sum(1 for row in rows if row["status"] == "matched"),
            self._count_for(
                "matched to a .json and read a capture time (matched)"))

    def test_the_per_file_table_is_available_on_request(self):
        listed = support.run_cli([self.takeout, "--list"])
        self.assertEqual(listed.code, 0)
        self.assertIn("media_key", listed.out)
        self.assertIn("a/IMG_0001.jpg", listed.out)
        self.assertNotIn("a/IMG_0001.jpg", self.result.out,
                         "既定では 1 枚ごとの行を出さない")

    def test_it_is_a_table_of_counts(self):
        self.assertIn("Takeout audit summary", self.result.out)
        self.assertTrue(re.search(r"^-+\s+-+$", self.result.out,
                                  re.MULTILINE))


if __name__ == "__main__":
    unittest.main()

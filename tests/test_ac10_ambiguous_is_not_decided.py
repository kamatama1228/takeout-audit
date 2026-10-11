"""AC10: 候補が 2 件以上あるときは、どれかを選ばない。

**黙って 1 つに決めない。** 候補は `candidates` 列にすべて書く。行は増やさない。
"""

import os
import shutil
import tempfile
import unittest

import support


class WhenTwoCandidatesAreEquallyGood(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.takeout = os.path.join(self.root, "takeout")
        os.makedirs(self.takeout)
        self.report = os.path.join(self.root, "plan.csv")
        support.write_tree(self.takeout, {
            "c/A_long_photo_name_0001.jpg": b"\xff\xd8photo",
            "c/A_long_photo_name.json": support.sidecar_bytes(),
            "c/A_long_photo_na.json": support.sidecar_bytes(),
        })
        self.assertEqual(
            support.run_cli([self.takeout, "--report", self.report]).code, 0)
        self.row = support.row_for(self.report,
                                   "c/A_long_photo_name_0001.jpg")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_the_row_says_ambiguous_match(self):
        self.assertEqual(self.row["reason"], "ambiguous_match")
        self.assertEqual(self.row["status"], "not_matched")

    def test_no_sidecar_is_picked(self):
        self.assertEqual(self.row["json_path"], "")
        self.assertEqual(self.row["rule"], "")
        self.assertEqual(self.row["taken_time_utc"], "")

    def test_both_candidates_are_listed(self):
        self.assertEqual(self.row["candidates"].split("|"),
                         ["c/A_long_photo_na.json",
                          "c/A_long_photo_name.json"])

    def test_the_row_count_is_still_one_per_media_file(self):
        self.assertEqual(len(support.rows_as_dicts(self.report)), 1)


class WhenOneCandidateIsClearlyBetter(unittest.TestCase):
    """順位の違う規則に当たるときは、決めてよい。**規則は公開してある。**"""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.takeout = os.path.join(self.root, "takeout")
        os.makedirs(self.takeout)
        self.report = os.path.join(self.root, "plan.csv")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_an_exact_name_wins_over_a_cut_short_one(self):
        support.write_tree(self.takeout, {
            "d/IMG_00012345.jpg": b"\xff\xd8photo",
            "d/IMG_00012345.jpg.json": support.sidecar_bytes(),
            "d/IMG_00012345.j.json": support.sidecar_bytes(),
        })
        self.assertEqual(
            support.run_cli([self.takeout, "--report", self.report]).code, 0)
        row = support.row_for(self.report, "d/IMG_00012345.jpg")
        self.assertEqual(row["rule"], "R1")
        self.assertEqual(row["status"], "matched")
        self.assertEqual(len(row["candidates"].split("|")), 2,
                         "選ばなかった候補も、そのまま列に出る")


class WhenThereAreVeryManyCandidates(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.takeout = os.path.join(self.root, "takeout")
        os.makedirs(self.takeout)
        self.report = os.path.join(self.root, "plan.csv")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_only_the_first_eight_are_written_and_the_rest_are_counted(self):
        files = {"many/IMG_12345678.jpg": b"\xff\xd8photo"}
        for index in range(11):
            files["many/IMG_12345678y%02d.json" % index] = \
                support.sidecar_bytes()
        support.write_tree(self.takeout, files)
        self.assertEqual(
            support.run_cli([self.takeout, "--report", self.report]).code, 0)
        row = support.row_for(self.report, "many/IMG_12345678.jpg")
        parts = row["candidates"].split("|")
        self.assertEqual(len(parts), 9)
        self.assertEqual(parts[-1], "+3 more")
        self.assertEqual(parts[:8],
                         sorted(parts[:8], key=lambda p: p.encode("utf-8")))
        self.assertEqual(row["reason"], "unmatched_by_known_rules")


if __name__ == "__main__":
    unittest.main()

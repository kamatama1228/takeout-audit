"""AC14: 検証していないことを、利用者に見える場所に出す。

`--help` の末尾、集計の表の末尾、README の冒頭近く。**この 1 行を弱めない。**
会社は実物の Takeout を 1 件も持っていない。
"""

import os
import shutil
import tempfile
import unittest

import support
from takeout_audit import UNVERIFIED_NOTICE, cli

README = os.path.join(support.PRODUCT_ROOT, "README.md")


class TheNoticeIsWhereTheUserLooks(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.takeout = os.path.join(self.root, "takeout")
        os.makedirs(self.takeout)
        support.write_tree(self.takeout, support.takeout_files())

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_the_notice_says_both_halves(self):
        """「検証していない」と「ライブラリの振る舞いではない」の両方を言う。"""
        self.assertIn("have not been verified against a real Google Takeout "
                      "export", UNVERIFIED_NOTICE)
        self.assertIn("not what your photo library will do",
                      UNVERIFIED_NOTICE)

    def test_it_is_at_the_end_of_the_help(self):
        help_text = cli.build_parser().format_help()
        self.assertIn(UNVERIFIED_NOTICE, help_text)
        self.assertTrue(help_text.rstrip().endswith(UNVERIFIED_NOTICE),
                        "`--help` の末尾に無い")

    def test_it_is_at_the_end_of_the_summary(self):
        result = support.run_cli([self.takeout])
        self.assertEqual(result.code, 0)
        self.assertTrue(result.out.rstrip().endswith(UNVERIFIED_NOTICE),
                        "集計の末尾に無い")

    def test_it_is_still_there_when_a_report_is_written(self):
        report = os.path.join(self.root, "plan.csv")
        result = support.run_cli([self.takeout, "--report", report])
        self.assertEqual(result.code, 0)
        self.assertIn(UNVERIFIED_NOTICE, result.out)

    def test_it_is_near_the_top_of_the_readme(self):
        """README では行が折り返されるため、語の並びとして比べる。"""
        with open(README, encoding="utf-8") as handle:
            readme = handle.read()
        flat = support.squeeze(readme)
        notice = support.squeeze(UNVERIFIED_NOTICE)
        self.assertIn(notice, flat.replace("**", ""))
        position = flat.replace("**", "").index(notice)
        self.assertLess(position, len(support.squeeze(readme[:1500])),
                        "README の冒頭近くに無い")

    def test_the_readme_explains_the_six_reasons(self):
        with open(README, encoding="utf-8") as handle:
            readme = handle.read()
        for reason in ("no_sidecar", "unmatched_by_known_rules",
                       "ambiguous_match", "sidecar_without_time",
                       "unparsable_time", "undecodable_name"):
            self.assertIn(reason, readme)

    def test_the_readme_asks_not_to_paste_the_csv_as_is(self):
        """CSV には利用者の file 名と日時が並ぶ。そのまま貼らせない。"""
        with open(README, encoding="utf-8") as handle:
            flat = support.squeeze(handle.read()).replace("**", "")
        self.assertIn("Please do not paste your CSV into an issue as-is.",
                      flat)
        self.assertIn("It contains your file names and timestamps.", flat)

    def test_the_readme_does_not_claim_what_it_has_not_measured(self):
        with open(README, encoding="utf-8") as handle:
            readme = handle.read().lower()
        for phrase in ("the only", "the first", "better than", "fastest",
                       "exiftool", "coming soon", "draft"):
            self.assertNotIn(phrase, readme)


if __name__ == "__main__":
    unittest.main()

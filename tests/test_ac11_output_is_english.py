"""AC11: 利用者が受け取る面に出る文字列は、すべて英語である。

対象は、標準出力・標準エラーの全文（`--help`、集計、中止の message、警告）と、
CSV の見出し行、および `reason` / `rule` / `status` の値。
"""

import os
import re
import shutil
import tempfile
import unittest

import support
from takeout_audit import cli

#: 日本語（ひらがな・カタカナ・漢字・全角句読点）
JAPANESE = re.compile(r"[　-〿぀-ヿ㐀-䶿"
                      r"一-鿿＀-ﾟ]")


class OutputIsEnglish(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.takeout = os.path.join(self.root, "takeout")
        os.makedirs(self.takeout)
        support.write_tree(self.takeout, {
            "a/IMG_0001.jpg": b"\xff\xd8a",
            "a/IMG_0001.jpg.json": support.sidecar_bytes(),
            "a/IMG_0002.jpg": b"\xff\xd8b",
            "a/IMG_0003-edited.jpg": b"\xff\xd8c",
            "a/IMG_0003.jpg": b"\xff\xd8d",
            "a/IMG_0003.jpg.json": b"not json",
        })

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _assert_english(self, text, what):
        found = JAPANESE.findall(text)
        self.assertEqual(found, [], "%s に日本語が出ている: %r" % (what, found))

    def test_the_help_is_english(self):
        self._assert_english(cli.build_parser().format_help(), "--help")

    def test_the_summary_is_english(self):
        result = support.run_cli([self.takeout, "--list"])
        self._assert_english(result.text, "集計と 1 枚ごとの表")

    def test_the_abort_message_is_english(self):
        result = support.run_cli([self.takeout, "--report",
                                  os.path.join(self.takeout, "x.csv")])
        self.assertEqual(result.code, 2)
        self._assert_english(result.text, "中止の message")

    def test_the_warning_about_an_unreadable_input_is_english(self):
        broken = os.path.join(self.root, "half.zip")
        with open(broken, "wb") as handle:
            handle.write(b"PK\x03\x04 and then nothing useful")
        result = support.run_cli([self.takeout, broken])
        self._assert_english(result.text, "警告")

    def test_the_csv_is_english(self):
        report = os.path.join(self.root, "plan.csv")
        self.assertEqual(
            support.run_cli([self.takeout, "--report", report]).code, 0)
        header, rows = support.read_csv(report)
        self._assert_english(",".join(header), "CSV の見出し")
        for row in rows:
            cells = dict(zip(header, row))
            for column in ("rule", "status", "reason"):
                self._assert_english(cells[column], "CSV の %s" % column)

    def test_the_detector_itself_works(self):
        """空振りしていないことを確かめる。"""
        self.assertTrue(JAPANESE.findall("対応づけ"))
        self.assertFalse(JAPANESE.findall("no_sidecar / R3+R4"))


if __name__ == "__main__":
    unittest.main()

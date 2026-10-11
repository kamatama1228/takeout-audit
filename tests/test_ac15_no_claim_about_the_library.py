"""AC15: 出力と CSV は、取り込み側のライブラリの挙動を主張しない。

標準出力・標準エラーの全文と CSV の byte 列を小文字にしたとき、禁じた語が
1 つも現れないこと。**この tool は、利用者の写真がどうなるかを知らない。**
"""

import os
import shutil
import tempfile
import unittest

import support

FORBIDDEN = ("lose", "lost", "losing", "broken", "corrupt", "damaged",
             "destroy")


def _every_kind_of_outcome():
    """6 つの `reason` と、対応づいた件が全部出る入力。"""
    return {
        "a/IMG_0001.jpg": b"\xff\xd8a",
        "a/IMG_0001.jpg.json": support.sidecar_bytes(),
        "a/IMG_0002.jpg": b"\xff\xd8b",
        "a/IMG_0001-edited.jpg": b"\xff\xd8c",
        "b/A_long_photo_name_0001.jpg": b"\xff\xd8d",
        "b/A_long_photo_name.json": support.sidecar_bytes(),
        "b/A_long_photo_na.json": support.sidecar_bytes(),
        "c/IMG_0004.jpg": b"\xff\xd8e",
        "c/IMG_0004.jpg.json": support.sidecar_bytes(with_time=False),
        "c/IMG_0005.jpg": b"\xff\xd8f",
        "c/IMG_0005.jpg.json": b"not json",
    }


class NoWordAboutWhatTheLibraryWillDo(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.takeout = os.path.join(self.root, "takeout")
        os.makedirs(self.takeout)
        support.write_tree(self.takeout, _every_kind_of_outcome())
        self.report = os.path.join(self.root, "plan.csv")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _assert_clean(self, text, what):
        lowered = text.lower()
        for word in FORBIDDEN:
            self.assertNotIn(word, lowered, "%s に %r が出ている" % (what, word))

    def test_the_whole_output_is_clean(self):
        result = support.run_cli([self.takeout, "--list",
                                  "--report", self.report])
        self.assertEqual(result.code, 0)
        self._assert_clean(result.text, "標準出力と標準エラー")

    def test_the_csv_bytes_are_clean(self):
        self.assertEqual(
            support.run_cli([self.takeout, "--report", self.report]).code, 0)
        with open(self.report, "rb") as handle:
            raw = handle.read()
        self._assert_clean(raw.decode("utf-8"), "CSV")

    def test_the_help_is_clean(self):
        from takeout_audit import cli

        self._assert_clean(cli.build_parser().format_help(), "--help")

    def test_the_messages_for_trouble_are_clean(self):
        """壊れた入力についての message でも、禁じた語を使わない。"""
        damaged = os.path.join(self.root, "half.zip")
        with open(damaged, "wb") as handle:
            handle.write(b"PK\x03\x04 then nothing useful")
        result = support.run_cli([self.takeout, damaged])
        self.assertEqual(result.code, 0)
        self._assert_clean(result.text, "壊れた入力についての報告")

        stopped = support.run_cli([self.takeout, "--report",
                                   os.path.join(self.takeout, "x.csv")])
        self.assertEqual(stopped.code, 2)
        self._assert_clean(stopped.text, "中止の message")

    def test_the_readme_is_clean_too(self):
        path = os.path.join(support.PRODUCT_ROOT, "README.md")
        with open(path, encoding="utf-8") as handle:
            self._assert_clean(handle.read(), "README")

    def test_the_check_itself_works(self):
        self.assertRaises(AssertionError, self._assert_clean,
                          "your photos will lose their dates", "試し")


if __name__ == "__main__":
    unittest.main()

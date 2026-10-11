"""AC5: 対応づけの規則を、少なくとも 4 つ実装する。

- **R1** 完全一致
- **R2** `.json` 名の末尾切り詰め
- **R3** `(n)` の位置違い
- **R4** `supplemental-metadata` 等の挿入語

**この 4 規則と、会社が決めた定数は、実物の Takeout で検証されていない。**
ここで確かめているのは「会社が決めた規則どおりに動くこと」だけであり、
「規則が実物と合っていること」ではない。
"""

import os
import shutil
import tempfile
import unittest

import support


class EachRule(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.takeout = os.path.join(self.root, "takeout")
        os.makedirs(self.takeout)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _audit(self, media_name, json_name, folder="f"):
        """1 枚と 1 件の `.json` だけを置いて、その 1 行を返す。"""
        support.write_tree(self.takeout, {
            "%s/%s" % (folder, media_name): b"\xff\xd8photo",
            "%s/%s" % (folder, json_name): support.sidecar_bytes(),
        })
        report = os.path.join(self.root, "%s.csv" % folder)
        result = support.run_cli([self.takeout, "--report", report])
        self.assertEqual(result.code, 0)
        return support.row_for(report, "%s/%s" % (folder, media_name))

    def test_r1_exact_name(self):
        row = self._audit("IMG_0001.jpg", "IMG_0001.jpg.json", "r1")
        self.assertEqual(row["rule"], "R1")
        self.assertEqual(row["status"], "matched")
        self.assertEqual(row["taken_time_utc"], support.EPOCH_UTC)

    def test_r2_the_json_name_is_cut_short(self):
        row = self._audit("A_very_long_photo_name_0001.jpg",
                          "A_very_long_photo_na.json", "r2")
        self.assertEqual(row["rule"], "R2")
        self.assertEqual(row["status"], "matched")

    def test_r3_the_number_sits_elsewhere(self):
        row = self._audit("IMG_1234(1).jpg", "IMG_1234.jpg(1).json", "r3")
        self.assertEqual(row["rule"], "R3")
        self.assertEqual(row["status"], "matched")

    def test_r4_an_inserted_word(self):
        row = self._audit("IMG_5678.jpg",
                          "IMG_5678.jpg.supplemental-metadata.json", "r4")
        self.assertEqual(row["rule"], "R4")
        self.assertEqual(row["status"], "matched")

    def test_the_rules_combine(self):
        """実物では、挿入語・連番・切り詰めが重なる。"""
        row = self._audit("IMG_7777(2).jpg",
                          "IMG_7777.jpg.supplemental-metadata(2).json", "c1")
        self.assertEqual(row["rule"], "R3+R4")
        self.assertEqual(row["status"], "matched")

        row = self._audit("IMG_8888.jpg", "IMG_8888.jpg.supplem.json", "c2")
        self.assertEqual(row["rule"], "R4+R2")
        self.assertEqual(row["status"], "matched")

    def test_an_unrelated_sidecar_is_not_matched(self):
        """似ていない名前を結び付けない。"""
        row = self._audit("IMG_0001.jpg", "VID_9999.mp4.json", "x1")
        self.assertEqual(row["status"], "not_matched")
        self.assertEqual(row["reason"], "no_sidecar")

    def test_case_is_not_ignored(self):
        """大文字小文字を区別する（別の写真どうしを結び付けないため）。"""
        row = self._audit("IMG_0001.jpg", "img_0001.jpg.json", "x2")
        self.assertEqual(row["status"], "not_matched")

    def test_a_sidecar_in_another_folder_is_not_used(self):
        """候補の探索は、同じ folder の中だけで行う。"""
        support.write_tree(self.takeout, {
            "one/IMG_0001.jpg": b"\xff\xd8photo",
            "two/IMG_0001.jpg.json": support.sidecar_bytes(),
        })
        report = os.path.join(self.root, "folders.csv")
        self.assertEqual(
            support.run_cli([self.takeout, "--report", report]).code, 0)
        row = support.row_for(report, "one/IMG_0001.jpg")
        self.assertEqual(row["reason"], "no_sidecar")

    def test_names_are_compared_after_nfc_normalisation(self):
        """NFD の名前と NFC の名前を、取り違えずに結び付ける。

        macOS 由来の名前は NFD、`.json` 側が NFC ということが起こり得る。放置
        すると、どちらも「対応づかない」側に倒れる。
        """
        name = "café_0001.jpg"          # NFD（e + 結合アクセント）
        json_name = "café_0001.jpg.json"  # NFC
        support.write_tree(self.takeout, {
            "nfc/%s" % name: b"\xff\xd8photo",
            "nfc/%s" % json_name: support.sidecar_bytes(),
        })
        report = os.path.join(self.root, "nfc.csv")
        self.assertEqual(
            support.run_cli([self.takeout, "--report", report]).code, 0)
        rows = [row for row in support.rows_as_dicts(report)
                if row["media_key"].startswith("nfc/")]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "matched")
        self.assertEqual(rows[0]["rule"], "R1")
        self.assertEqual(rows[0]["media_key"], "nfc/café_0001.jpg",
                         "media_key は NFC に正規化されている")


if __name__ == "__main__":
    unittest.main()

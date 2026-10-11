"""AC4: 同じ Takeout なら、zip 版と directory 版で結果が完全に一致する。

比べるのは `media_key`・`rule`・`status`・`reason`・`taken_time_utc`・
`candidates` の 6 列である。`media_path` と `json_path` は、zip 入力と directory
入力で必ず違うため、比較の対象にしない。
"""

import os
import shutil
import tempfile
import unittest

import support

COMPARED = ("media_key", "rule", "status", "reason", "taken_time_utc",
            "candidates")


def _mixed_takeout():
    """素直な対応づけだけでなく、失敗のしかたも混ぜた Takeout。"""
    album = support.ALBUM
    files = {
        "%s/IMG_0001.jpg" % album: b"\xff\xd8a",
        "%s/IMG_0001.jpg.json" % album: support.sidecar_bytes(),
        "%s/IMG_0002(1).jpg" % album: b"\xff\xd8b",
        "%s/IMG_0002.jpg(1).json" % album: support.sidecar_bytes(),
        "%s/IMG_0003.jpg" % album: b"\xff\xd8c",
        "%s/IMG_0003.jpg.supplemental-metadata.json" % album:
            support.sidecar_bytes(),
        "%s/IMG_0004-edited.jpg" % album: b"\xff\xd8d",
        "%s/IMG_0005.jpg" % album: b"\xff\xd8e",
        "%s/A_very_long_photo_name_0006.jpg" % album: b"\xff\xd8f",
        "%s/A_very_long_photo_na.json" % album: support.sidecar_bytes(),
        "Takeout/Google Photos/Photos from 2022/IMG_9999.mp4": b"video",
        "Takeout/Google Photos/Photos from 2022/IMG_9999.mp4.json":
            support.sidecar_bytes(),
    }
    return files


class ZipAndDirectoryAgree(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.files = _mixed_takeout()

        self.directory = os.path.join(self.root, "extracted")
        os.makedirs(self.directory)
        support.write_tree(self.directory, self.files)

        self.zip_path = os.path.join(self.root, "takeout-001.zip")
        support.write_zip(self.zip_path, self.files)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _rows(self, source):
        report = os.path.join(self.root, "report-%s.csv" % id(source))
        result = support.run_cli([source, "--report", report])
        self.assertEqual(result.code, 0)
        return support.rows_as_dicts(report)

    def test_the_six_compared_columns_are_identical(self):
        from_directory = self._rows(self.directory)
        from_zip = self._rows(self.zip_path)
        self.assertTrue(from_directory, "行が 1 件も無い")
        self.assertEqual(
            [tuple(row[column] for column in COMPARED)
             for row in from_directory],
            [tuple(row[column] for column in COMPARED) for row in from_zip])

    def test_the_display_columns_do_differ(self):
        """比較から外した 2 列が、本当に違うことを確かめる（空振り防止）。"""
        from_directory = self._rows(self.directory)
        from_zip = self._rows(self.zip_path)
        self.assertNotEqual(from_directory[0]["media_path"],
                            from_zip[0]["media_path"])
        self.assertIn(".zip::", from_zip[0]["media_path"])

    def test_several_zips_agree_with_the_directory_too(self):
        """分割された zip でも、展開済み directory と同じ結果になる。"""
        first, second = {}, {}
        for index, (name, data) in enumerate(sorted(self.files.items())):
            (first if index % 2 == 0 else second)[name] = data
        first_path = os.path.join(self.root, "part-001.zip")
        second_path = os.path.join(self.root, "part-002.zip")
        support.write_zip(first_path, first)
        support.write_zip(second_path, second)

        report = os.path.join(self.root, "split.csv")
        result = support.run_cli([first_path, second_path,
                                  "--report", report])
        self.assertEqual(result.code, 0)
        split_rows = support.rows_as_dicts(report)
        self.assertEqual(
            [tuple(row[column] for column in COMPARED)
             for row in split_rows],
            [tuple(row[column] for column in COMPARED)
             for row in self._rows(self.directory)])


if __name__ == "__main__":
    unittest.main()

"""AC3: zip を入力にできる。複数の zip にまたがって対応づける。

Takeout は複数の zip に分割されることがあり、写真と `.json` が別の zip に入る。
これは、この製品が解こうとしている失敗のしかたの 1 つである。
"""

import os
import shutil
import tempfile
import unittest

import support


class ZipInput(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.report = os.path.join(self.root, "plan.csv")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_a_single_zip_is_matched(self):
        path = os.path.join(self.root, "takeout-001.zip")
        support.write_zip(path, support.takeout_files())
        result = support.run_cli([path, "--report", self.report])
        self.assertEqual(result.code, 0)
        row = support.row_for(self.report,
                              "%s/IMG_0001.jpg" % support.ALBUM)
        self.assertEqual(row["status"], "matched")
        self.assertEqual(row["taken_time_utc"], support.EPOCH_UTC)

    def test_a_photo_and_its_sidecar_in_different_zips(self):
        first = os.path.join(self.root, "takeout-001.zip")
        second = os.path.join(self.root, "takeout-002.zip")
        support.write_zip(first, {
            "%s/IMG_0001.jpg" % support.ALBUM: b"\xff\xd8photo"})
        support.write_zip(second, {
            "%s/IMG_0001.jpg.json" % support.ALBUM: support.sidecar_bytes()})

        result = support.run_cli([first, second, "--report", self.report])
        self.assertEqual(result.code, 0)
        rows = support.rows_as_dicts(self.report)
        self.assertEqual(len(rows), 1, "media は 1 件だけのはずである")
        self.assertEqual(rows[0]["status"], "matched")
        self.assertEqual(rows[0]["rule"], "R1")
        self.assertIn("takeout-002.zip", rows[0]["json_path"])

    def test_a_photo_alone_in_one_zip_is_not_matched(self):
        path = os.path.join(self.root, "takeout-001.zip")
        support.write_zip(path, {
            "%s/IMG_0001.jpg" % support.ALBUM: b"\xff\xd8photo"})
        result = support.run_cli([path, "--report", self.report])
        self.assertEqual(result.code, 0)
        rows = support.rows_as_dicts(self.report)
        self.assertEqual(rows[0]["status"], "not_matched")
        self.assertEqual(rows[0]["reason"], "no_sidecar")

    def test_folder_entries_in_the_zip_are_not_counted_as_media(self):
        path = os.path.join(self.root, "takeout-001.zip")
        files = {"%s/" % support.ALBUM: b""}
        files.update(support.takeout_files())
        support.write_zip(path, files)
        result = support.run_cli([path, "--report", self.report])
        self.assertEqual(result.code, 0)
        self.assertEqual(len(support.rows_as_dicts(self.report)), 1)


if __name__ == "__main__":
    unittest.main()

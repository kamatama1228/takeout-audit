"""AC6: 1 枚ごとに 1 行。候補が何件あっても行を増やさない。列は 8 つで固定。"""

import os
import shutil
import tempfile
import unittest

import support

EXPECTED_COLUMNS = ["media_path", "media_key", "json_path", "rule",
                    "taken_time_utc", "status", "reason", "candidates"]


class TheCsvShape(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.takeout = os.path.join(self.root, "takeout")
        os.makedirs(self.takeout)
        self.report = os.path.join(self.root, "plan.csv")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_the_columns_are_exactly_these_eight_in_this_order(self):
        support.write_tree(self.takeout, support.takeout_files())
        self.assertEqual(
            support.run_cli([self.takeout, "--report", self.report]).code, 0)
        header, _ = support.read_csv(self.report)
        self.assertEqual(header, EXPECTED_COLUMNS)

    def test_one_row_per_media_file(self):
        photos = ("IMG_0001.jpg", "IMG_0002.jpg", "IMG_0003.jpg")
        support.write_tree(self.takeout, support.takeout_files(photos=photos))
        self.assertEqual(
            support.run_cli([self.takeout, "--report", self.report]).code, 0)
        rows = support.rows_as_dicts(self.report)
        self.assertEqual(len(rows), len(photos))
        self.assertEqual(
            sorted(row["media_key"] for row in rows),
            sorted("%s/%s" % (support.ALBUM, name) for name in photos))

    def test_many_candidates_do_not_add_rows(self):
        files = {"many/IMG_12345678.jpg": b"\xff\xd8photo"}
        for index in range(12):
            files["many/IMG_12345678x%02d.json" % index] = \
                support.sidecar_bytes()
        support.write_tree(self.takeout, files)
        self.assertEqual(
            support.run_cli([self.takeout, "--report", self.report]).code, 0)
        rows = support.rows_as_dicts(self.report)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]["candidates"].split("|")), 9,
                         "候補 8 件と `+N more` の 9 つに収まる")
        self.assertTrue(rows[0]["candidates"].endswith("|+4 more"))

    def test_sidecars_are_not_rows_of_their_own(self):
        """`.json` は media ではない。行にしない。"""
        support.write_tree(self.takeout, support.takeout_files())
        self.assertEqual(
            support.run_cli([self.takeout, "--report", self.report]).code, 0)
        for row in support.rows_as_dicts(self.report):
            self.assertFalse(row["media_key"].endswith(".json"))

    def test_videos_get_a_row_too(self):
        """この tool は media の中身を読まないため、写真と動画を区別しない。"""
        support.write_tree(self.takeout, {
            "v/VID_0001.mp4": b"video",
            "v/VID_0001.mp4.json": support.sidecar_bytes(),
        })
        self.assertEqual(
            support.run_cli([self.takeout, "--report", self.report]).code, 0)
        row = support.row_for(self.report, "v/VID_0001.mp4")
        self.assertEqual(row["status"], "matched")

    def test_the_takeout_index_page_is_not_counted_as_a_photo(self):
        """Takeout が書き出す目録は写真ではない。件数に混ぜない。"""
        support.write_tree(self.takeout, {
            "Takeout/archive_browser.html": b"<html></html>",
            "%s/IMG_0001.jpg" % support.ALBUM: b"\xff\xd8photo",
            "%s/IMG_0001.jpg.json" % support.ALBUM: support.sidecar_bytes(),
        })
        self.assertEqual(
            support.run_cli([self.takeout, "--report", self.report]).code, 0)
        rows = support.rows_as_dicts(self.report)
        self.assertEqual([row["media_key"] for row in rows],
                         ["%s/IMG_0001.jpg" % support.ALBUM])


if __name__ == "__main__":
    unittest.main()

"""AC8: 同じ入力には、いつも同じ CSV を出す（行の順序も含めて）。

並べ替えの鍵は `media_key` を UTF-8 で encode した byte 列の昇順、同値のときは
`media_path` の byte 列の昇順である。**zip の entry 順にも、directory の走査順
にも依存してはいけない。**
"""

import os
import shutil
import tempfile
import unittest

import support

NAMES = ("IMG_0002.jpg", "IMG_0001.jpg", "Z_last.jpg", "a_lower.jpg",
         "café.jpg", "あ.jpg", "IMG_0010.jpg")


class SameInputSameBytes(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.takeout = os.path.join(self.root, "takeout")
        os.makedirs(self.takeout)
        support.write_tree(self.takeout, support.takeout_files(photos=NAMES))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _csv_bytes(self, source, name):
        report = os.path.join(self.root, name)
        self.assertEqual(support.run_cli([source, "--report", report]).code, 0)
        with open(report, "rb") as handle:
            return handle.read()

    def test_two_runs_produce_the_same_bytes(self):
        first = self._csv_bytes(self.takeout, "one.csv")
        second = self._csv_bytes(self.takeout, "two.csv")
        self.assertEqual(first, second)

    def _stable_rows(self, source, name):
        """入力の置き場所で必ず変わる 2 列を外した行。"""
        report = os.path.join(self.root, name)
        self.assertEqual(support.run_cli([source, "--report", report]).code, 0)
        return [tuple(row[column] for column in
                      ("media_key", "rule", "taken_time_utc", "status",
                       "reason", "candidates"))
                for row in support.rows_as_dicts(report)]

    def test_the_order_does_not_depend_on_the_zip_entry_order(self):
        files = support.takeout_files(photos=NAMES)
        forward = os.path.join(self.root, "forward.zip")
        backward = os.path.join(self.root, "backward.zip")
        support.write_zip(forward, dict(sorted(files.items())))
        support.write_zip(backward,
                          dict(sorted(files.items(), reverse=True)))
        self.assertEqual(self._stable_rows(forward, "f.csv"),
                         self._stable_rows(backward, "b.csv"))

    def test_the_same_zip_twice_produces_the_same_bytes(self):
        path = os.path.join(self.root, "same.zip")
        support.write_zip(path, support.takeout_files(photos=NAMES))
        self.assertEqual(self._csv_bytes(path, "z1.csv"),
                         self._csv_bytes(path, "z2.csv"))

    def test_the_rows_are_sorted_by_the_media_key_bytes(self):
        report = os.path.join(self.root, "sorted.csv")
        self.assertEqual(
            support.run_cli([self.takeout, "--report", report]).code, 0)
        keys = [row["media_key"] for row in support.rows_as_dicts(report)]
        self.assertEqual(keys, sorted(keys, key=lambda k: k.encode("utf-8")))
        self.assertEqual(len(keys), len(NAMES))

    def test_the_order_does_not_depend_on_the_order_of_the_inputs(self):
        files = support.takeout_files(photos=NAMES)
        left, right = {}, {}
        for index, (name, data) in enumerate(sorted(files.items())):
            (left if index % 2 == 0 else right)[name] = data
        first = os.path.join(self.root, "part-001.zip")
        second = os.path.join(self.root, "part-002.zip")
        support.write_zip(first, left)
        support.write_zip(second, right)

        one = os.path.join(self.root, "order-one.csv")
        two = os.path.join(self.root, "order-two.csv")
        self.assertEqual(
            support.run_cli([first, second, "--report", one]).code, 0)
        self.assertEqual(
            support.run_cli([second, first, "--report", two]).code, 0)
        rows_one = [row["media_key"] for row in support.rows_as_dicts(one)]
        rows_two = [row["media_key"] for row in support.rows_as_dicts(two)]
        self.assertEqual(rows_one, rows_two)


if __name__ == "__main__":
    unittest.main()

"""AC2: `--report` の出力先が入力の内側を指すなら、1 件も処理せずに中止する。

「内側」は、両方の path を実 path に解決してから判定する。directory 入力では
その配下、zip 入力では zip file そのもの（zip が置かれた directory は制限しない）。
"""

import os
import shutil
import tempfile
import unittest

import support


class DirectoryInput(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.takeout = os.path.join(self.root, "takeout")
        os.makedirs(self.takeout)
        support.write_tree(self.takeout, support.takeout_files())

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _assert_stopped(self, report):
        before = support.file_list(self.root)
        result = support.run_cli([self.takeout, "--report", report])
        self.assertEqual(result.code, 2)
        self.assertIn("Stopped before looking at anything", result.out)
        self.assertIn("inside the input", result.out)
        # 集計を出していない＝1 件も処理していない。
        self.assertNotIn("Takeout audit summary", result.out)
        self.assertEqual(support.file_list(self.root), before)

    def test_directly_inside(self):
        self._assert_stopped(os.path.join(self.takeout, "plan.csv"))

    def test_deeper_inside(self):
        self._assert_stopped(os.path.join(self.takeout, support.ALBUM,
                                          "plan.csv"))

    def test_the_input_directory_itself(self):
        self._assert_stopped(self.takeout)

    def test_a_path_that_walks_back_in(self):
        self._assert_stopped(os.path.join(self.root, "takeout", "..",
                                          "takeout", "plan.csv"))

    def test_through_a_symlink(self):
        link = os.path.join(self.root, "link")
        try:
            os.symlink(self.takeout, link)
        except (OSError, NotImplementedError):
            self.skipTest("symlink を作れない file system である")
        self._assert_stopped(os.path.join(link, "plan.csv"))

    def test_a_sibling_path_is_allowed(self):
        report = os.path.join(self.root, "plan.csv")
        result = support.run_cli([self.takeout, "--report", report])
        self.assertEqual(result.code, 0)
        self.assertTrue(os.path.exists(report))

    def test_a_name_that_merely_starts_the_same_is_allowed(self):
        """`takeout` と `takeout-reports` を取り違えない。"""
        other = os.path.join(self.root, "takeout-reports")
        os.makedirs(other)
        report = os.path.join(other, "plan.csv")
        result = support.run_cli([self.takeout, "--report", report])
        self.assertEqual(result.code, 0)
        self.assertTrue(os.path.exists(report))


class ZipInput(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.zip_path = os.path.join(self.root, "takeout-001.zip")
        support.write_zip(self.zip_path, support.takeout_files())

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_writing_over_the_zip_itself_is_stopped(self):
        before = support.snapshot(self.root)
        result = support.run_cli([self.zip_path, "--report", self.zip_path])
        self.assertEqual(result.code, 2)
        self.assertIn("inside the input", result.out)
        self.assertEqual(support.snapshot(self.root), before)

    def test_the_folder_that_holds_the_zip_is_not_restricted(self):
        """`~/Downloads` に zip を置いた人が、同じ folder に出せること。"""
        report = os.path.join(self.root, "plan.csv")
        result = support.run_cli([self.zip_path, "--report", report])
        self.assertEqual(result.code, 0)
        self.assertTrue(os.path.exists(report))


if __name__ == "__main__":
    unittest.main()

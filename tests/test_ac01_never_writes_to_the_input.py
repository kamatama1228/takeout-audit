"""AC1: 入力に 1 byte も書き込まず、zip の media entry を 1 件も展開しない。

測る面は、入力 file の byte 列そのもの（SHA256・大きさ・mtime_ns）と、出力先
以外に file が 1 件も作られないことである。
"""

import os
import shutil
import tempfile
import unittest
import zipfile

import support


class ReadOnlyOnDirectoryInput(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.takeout = os.path.join(self.root, "takeout")
        os.makedirs(self.takeout)
        support.write_tree(self.takeout, support.takeout_files(
            photos=("IMG_0001.jpg", "IMG_0002.jpg", "IMG_0003-edited.jpg")))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_every_input_file_is_identical_afterwards(self):
        before = support.snapshot(self.takeout)
        result = support.run_cli([self.takeout])
        self.assertEqual(result.code, 0)
        self.assertEqual(support.snapshot(self.takeout), before)

    def test_no_file_is_created_anywhere_except_the_report(self):
        report = os.path.join(self.root, "plan.csv")
        before = support.file_list(self.root)
        result = support.run_cli([self.takeout, "--report", report])
        self.assertEqual(result.code, 0)
        created = support.file_list(self.root) - before
        self.assertEqual(created, {"plan.csv"})

    def test_without_report_not_a_single_file_is_created(self):
        before = support.file_list(self.root)
        support.run_cli([self.takeout])
        self.assertEqual(support.file_list(self.root), before)


class ReadOnlyOnZipInput(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.zip_path = os.path.join(self.root, "takeout-001.zip")
        support.write_zip(self.zip_path, support.takeout_files(
            photos=("IMG_0001.jpg", "IMG_0002.jpg")))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_the_zip_is_identical_afterwards(self):
        before = support.snapshot(self.root)
        result = support.run_cli([self.zip_path])
        self.assertEqual(result.code, 0)
        self.assertEqual(support.snapshot(self.root), before)

    def test_no_temporary_file_is_left_behind(self):
        before = support.file_list(self.root)
        report = os.path.join(self.root, "plan.csv")
        support.run_cli([self.zip_path, "--report", report])
        self.assertEqual(support.file_list(self.root) - before, {"plan.csv"})


class TheMediaEntriesAreNeverExtracted(unittest.TestCase):
    """**zip から読んでよいのは、entry 名の一覧と `.json` の中身だけである。**

    `ZipFile.open` を見張り、どの entry が開かれたかを記録する。media の entry が
    1 件でも開かれたら、それは展開であり、失格である。
    """

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.zip_path = os.path.join(self.root, "takeout-001.zip")
        files = support.takeout_files(photos=("IMG_0001.jpg", "IMG_0002.jpg"))
        # media entry を、他より明らかに大きくしておく。
        key = "%s/IMG_0001.jpg" % support.ALBUM
        files[key] = b"\xff\xd8" + b"0" * 200000
        support.write_zip(self.zip_path, files)
        self.opened = []
        self._original_open = zipfile.ZipFile.open

        def recording_open(archive, name, *args, **kwargs):
            self.opened.append(name.filename if hasattr(name, "filename")
                               else name)
            return self._original_open(archive, name, *args, **kwargs)

        zipfile.ZipFile.open = recording_open

    def tearDown(self):
        zipfile.ZipFile.open = self._original_open
        shutil.rmtree(self.root, ignore_errors=True)

    def test_only_json_entries_are_opened(self):
        result = support.run_cli([self.zip_path])
        self.assertEqual(result.code, 0)
        self.assertTrue(self.opened, "`.json` すら読んでいない")
        for name in self.opened:
            self.assertTrue(name.lower().endswith(".json"),
                            "media entry を開いている: %r" % name)

    def test_the_source_code_never_calls_extract(self):
        """静的にも確かめる。`extract` / `extractall` を 1 か所も使わない。"""
        package = os.path.join(support.PRODUCT_ROOT, "takeout_audit")
        for filename in sorted(os.listdir(package)):
            if not filename.endswith(".py"):
                continue
            with open(os.path.join(package, filename), encoding="utf-8") as f:
                body = f.read()
            self.assertNotIn("extractall", body, filename)
            self.assertNotIn(".extract(", body, filename)
            self.assertNotIn("mkdtemp", body, filename)


if __name__ == "__main__":
    unittest.main()

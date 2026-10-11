"""AC13: 入力が壊れている場合に、落ちずに報告する。

測る面は、実行して得た出力の全文（終了 code と message）である。
"""

import os
import shutil
import tempfile
import unittest

import support


class DamagedInput(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.takeout = os.path.join(self.root, "takeout")
        os.makedirs(self.takeout)
        support.write_tree(self.takeout, support.takeout_files())
        self.report = os.path.join(self.root, "plan.csv")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _write(self, name, data):
        path = os.path.join(self.root, name)
        with open(path, "wb") as handle:
            handle.write(data)
        return path

    def test_a_zip_that_cannot_be_read_is_reported_and_skipped(self):
        damaged = self._write("half.zip", b"PK\x03\x04 then nothing useful")
        result = support.run_cli([self.takeout, damaged,
                                  "--report", self.report])
        self.assertEqual(result.code, 0)
        self.assertIn("Skipped an input", result.err)
        self.assertIn("could not be read", result.text)
        self.assertIn("are not part of the counts above", result.out)
        # 読めた入力の分は、ふつうに出ている。
        self.assertEqual(len(support.rows_as_dicts(self.report)), 1)

    def test_when_no_input_can_be_read_it_stops_with_code_two(self):
        damaged = self._write("half.zip", b"PK\x03\x04 then nothing useful")
        result = support.run_cli([damaged, "--report", self.report])
        self.assertEqual(result.code, 2)
        self.assertIn("none of the given inputs could be read", result.out)
        self.assertFalse(os.path.exists(self.report))

    def test_a_multi_part_archive_is_reported_not_guessed(self):
        part = self._write("takeout.z01", b"\x50\x4b\x07\x08 not a whole zip")
        result = support.run_cli([part])
        self.assertEqual(result.code, 2)
        self.assertIn("multi-part archive", result.text)

    def test_a_path_that_does_not_exist(self):
        result = support.run_cli([os.path.join(self.root, "nowhere")])
        self.assertEqual(result.code, 2)
        self.assertIn("does not exist", result.text)

    def test_a_json_that_is_not_json_does_not_stop_the_run(self):
        support.write_tree(self.takeout, {
            "x/IMG_0009.jpg": b"\xff\xd8photo",
            "x/IMG_0009.jpg.json": b"\x00\x01\x02 not text at all",
        })
        result = support.run_cli([self.takeout, "--report", self.report])
        self.assertEqual(result.code, 0)
        self.assertEqual(
            support.row_for(self.report, "x/IMG_0009.jpg")["reason"],
            "unparsable_time")

    def test_an_empty_json_does_not_stop_the_run(self):
        support.write_tree(self.takeout, {
            "y/IMG_0010.jpg": b"\xff\xd8photo",
            "y/IMG_0010.jpg.json": b"",
        })
        result = support.run_cli([self.takeout, "--report", self.report])
        self.assertEqual(result.code, 0)
        self.assertEqual(
            support.row_for(self.report, "y/IMG_0010.jpg")["reason"],
            "unparsable_time")

    def test_a_sidecar_entry_that_cannot_be_opened_is_not_fatal(self):
        """`.json` entry を読めないとき（暗号化など）も、落ちずに報告する。"""
        import zipfile

        path = os.path.join(self.root, "secret.zip")
        support.write_zip(path, {
            "z/IMG_0011.jpg": b"\xff\xd8photo",
            "z/IMG_0011.jpg.json": support.sidecar_bytes(),
        })
        original_open = zipfile.ZipFile.open

        def refuse(archive, name, *args, **kwargs):
            raise RuntimeError("that entry is encrypted")

        zipfile.ZipFile.open = refuse
        try:
            result = support.run_cli([path, "--report", self.report])
        finally:
            zipfile.ZipFile.open = original_open
        self.assertEqual(result.code, 0)
        self.assertEqual(
            support.row_for(self.report, "z/IMG_0011.jpg")["reason"],
            "unparsable_time")

    # ------------------------------------------- 文字 code が不正な file 名
    #
    # **QA の差し戻し。** zip の側だけで試していたため、展開済み Takeout で
    # 落ちることに気づかなかった。zip の entry 名は cp437 として読まれるので、
    # この状態にならない。**出口は 3 つある**（並べ替え・CSV・画面）。
    # **1 か所だけ直すと、残りで落ちる。**

    def _write_undecodable_photo(self):
        """展開済み Takeout に、UTF-8 として読めない名前の写真を 1 枚足す。"""
        directory = os.path.join(self.takeout, *support.ALBUM.split("/"))
        path = os.path.join(os.fsencode(directory), b"IMG_\xff\xfe02.jpg")
        with open(path, "wb") as handle:
            handle.write(b"\xff\xd8photo")
        return os.fsdecode(path)

    def test_an_undecodable_name_on_disk_does_not_stop_the_run(self):
        """**出口 1・2**: 並べ替えと CSV。他の写真をまとめて失わない。"""
        self._write_undecodable_photo()
        result = support.run_module([self.takeout, "--report", self.report])

        self.assertEqual(result.code, 0, result.text)
        self.assertNotIn("Traceback", result.text)
        self.assertTrue(os.path.exists(self.report),
                        "CSV が 1 行も書かれていない:\n%s" % result.text)

        rows = support.rows_as_dicts(self.report)
        self.assertEqual(len(rows), 2, rows)
        # 読めた写真は、ふつうに対応づく。読めない名前のほうだけが理由になる。
        self.assertEqual(
            support.row_for(self.report,
                            "%s/IMG_0001.jpg" % support.ALBUM)["status"],
            "matched")
        self.assertIn("undecodable_name",
                      [row["reason"] for row in rows])

    def test_an_undecodable_name_is_shown_in_the_per_file_table(self):
        """**出口 3**: `--list` の画面表示。"""
        self._write_undecodable_photo()
        result = support.run_module([self.takeout, "--list"])

        self.assertEqual(result.code, 0, result.text)
        self.assertNotIn("Traceback", result.text)
        self.assertIn("undecodable_name", result.out)

    def test_the_undecodable_reason_is_counted_in_the_summary(self):
        """**理由が 1 度も表示されない**、ということが起きていないことの確認。"""
        self._write_undecodable_photo()
        result = support.run_module([self.takeout])
        self.assertEqual(result.code, 0, result.text)
        counted = [line for line in result.out.splitlines()
                   if line.strip().endswith("undecodable_name")]
        self.assertEqual(len(counted), 1, result.out)
        self.assertTrue(counted[0].strip().startswith("1"), counted)

    def test_a_row_with_an_undecodable_name_can_always_be_written(self):
        """CSV の書き出しそのものが、入口を通っていない行でも落ちないこと。

        **入口（`sources`）だけを直して終わりにしないための test である。**
        """
        from takeout_audit import audit, report

        name = support.undecodable_filename()
        row = audit.Row("/takeout/" + name, name)
        row.reason = audit.REASON_UNDECODABLE_NAME
        path = os.path.join(self.root, "undecodable.csv")

        report.write_csv(path, [row])

        written = support.rows_as_dicts(path)
        self.assertEqual(len(written), 1)
        self.assertEqual(written[0]["reason"], "undecodable_name")
        # 置き換えは決定的で、元の byte が読み取れる形で残る。
        self.assertEqual(written[0]["media_key"], "IMG_\\xff\\xfe02.jpg")

    def test_the_replacement_of_undecodable_bytes_is_deterministic(self):
        """同じ名前が必ず同じ文字列になる（並び順が走査順に依存しない）。"""
        from takeout_audit import names

        name = support.undecodable_filename()
        self.assertEqual(names.escape_undecodable(name),
                         names.escape_undecodable(name))
        # すでに置き換えた文字列を、もう一度通しても変わらない。
        once = names.escape_undecodable(name)
        self.assertEqual(names.escape_undecodable(once), once)
        # 置き換えた後は、必ず UTF-8 に encode できる。
        once.encode("utf-8")
        # 読める名前には触らない。
        self.assertEqual(names.escape_undecodable("写真 IMG_0001.jpg"),
                         "写真 IMG_0001.jpg")

    def test_an_undecodable_directory_name_does_not_stop_the_run(self):
        """folder の名前の側が読めない場合も、同じように報告する。"""
        parent = os.fsencode(self.takeout)
        directory = os.path.join(parent, b"Album \xff\xfe")
        os.makedirs(directory)
        with open(os.path.join(directory, b"IMG_0100.jpg"), "wb") as handle:
            handle.write(b"\xff\xd8photo")

        result = support.run_module([self.takeout, "--report", self.report])

        self.assertEqual(result.code, 0, result.text)
        self.assertNotIn("Traceback", result.text)
        reasons = [row["reason"] for row in support.rows_as_dicts(self.report)]
        self.assertIn("undecodable_name", reasons)

    def test_an_empty_input_is_not_an_error(self):
        empty = os.path.join(self.root, "empty")
        os.makedirs(empty)
        result = support.run_cli([empty])
        self.assertEqual(result.code, 0)
        self.assertIn("Takeout audit summary", result.out)


if __name__ == "__main__":
    unittest.main()

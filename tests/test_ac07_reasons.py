"""AC7: 対応づかなかった件には、必ず `reason` が付く。6 つを区別する。

とくに `no_sidecar`（本当に sidecar が無い）と `unmatched_by_known_rules`
（候補はあるが、この tool の規則では結び付かなかった）を混ぜないこと。**混ぜると、
tool の規則の不足が、利用者の問題として報告される。**
"""

import os
import shutil
import tempfile
import unittest

import support


class EachReason(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.takeout = os.path.join(self.root, "takeout")
        os.makedirs(self.takeout)
        self.report = os.path.join(self.root, "plan.csv")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _run(self, files):
        support.write_tree(self.takeout, files)
        result = support.run_cli([self.takeout, "--report", self.report])
        self.assertEqual(result.code, 0)
        return result

    def test_no_sidecar_when_nothing_could_be_a_candidate(self):
        self._run({"a/IMG_0001.jpg": b"\xff\xd8photo"})
        row = support.row_for(self.report, "a/IMG_0001.jpg")
        self.assertEqual(row["reason"], "no_sidecar")
        self.assertEqual(row["candidates"], "")
        self.assertEqual(row["json_path"], "")
        self.assertEqual(row["rule"], "")

    def test_unmatched_by_known_rules_when_a_candidate_exists(self):
        """`-edited` の写真は、元の写真の `.json` が候補に挙がる。

        この tool の規則では結び付かない。**それを `no_sidecar` と呼ばない。**
        候補があることは `candidates` 列に出る。
        """
        self._run({
            "b/IMG_0001.jpg": b"\xff\xd8photo",
            "b/IMG_0001.jpg.json": support.sidecar_bytes(),
            "b/IMG_0001-edited.jpg": b"\xff\xd8edited",
        })
        row = support.row_for(self.report, "b/IMG_0001-edited.jpg")
        self.assertEqual(row["reason"], "unmatched_by_known_rules")
        self.assertEqual(row["candidates"], "b/IMG_0001.jpg.json")
        self.assertEqual(row["rule"], "")
        # 元の写真のほうは、ふつうに対応づく。
        self.assertEqual(
            support.row_for(self.report, "b/IMG_0001.jpg")["status"],
            "matched")

    def test_ambiguous_match_when_two_candidates_are_equally_good(self):
        """切り詰めが重なると、どちらとも決められないことがある。"""
        self._run({
            "c/A_long_photo_name_0001.jpg": b"\xff\xd8photo",
            "c/A_long_photo_name.json": support.sidecar_bytes(),
            "c/A_long_photo_na.json": support.sidecar_bytes(),
        })
        row = support.row_for(self.report, "c/A_long_photo_name_0001.jpg")
        self.assertEqual(row["reason"], "ambiguous_match")
        self.assertEqual(row["json_path"], "", "黙って 1 つに決めていない")
        self.assertEqual(row["candidates"],
                         "c/A_long_photo_na.json|c/A_long_photo_name.json")

    def test_sidecar_without_time(self):
        self._run({
            "d/IMG_0001.jpg": b"\xff\xd8photo",
            "d/IMG_0001.jpg.json": support.sidecar_bytes(with_time=False),
        })
        row = support.row_for(self.report, "d/IMG_0001.jpg")
        self.assertEqual(row["reason"], "sidecar_without_time")
        self.assertEqual(row["rule"], "R1", "対応づけ自体は成立している")
        self.assertNotEqual(row["json_path"], "")
        self.assertEqual(row["taken_time_utc"], "")

    def test_unparsable_time_when_the_json_is_not_json(self):
        self._run({
            "e/IMG_0001.jpg": b"\xff\xd8photo",
            "e/IMG_0001.jpg.json": b"{this is not json",
        })
        row = support.row_for(self.report, "e/IMG_0001.jpg")
        self.assertEqual(row["reason"], "unparsable_time")

    def test_unparsable_time_when_the_timestamp_is_not_a_number(self):
        self._run({
            "f/IMG_0001.jpg": b"\xff\xd8photo",
            "f/IMG_0001.jpg.json":
                b'{"photoTakenTime": {"timestamp": "yesterday"}}',
        })
        row = support.row_for(self.report, "f/IMG_0001.jpg")
        self.assertEqual(row["reason"], "unparsable_time")

    def test_undecodable_name_is_not_mixed_into_no_sidecar(self):
        """zip の entry 名の文字 code を確定できない件を、別に数える。"""
        zip_path = os.path.join(self.root, "takeout-001.zip")
        support.write_zip(zip_path, {
            "g/été_0001.jpg": b"\xff\xd8photo",
        }, utf8_flag=False)
        result = support.run_cli([zip_path, "--report", self.report])
        self.assertEqual(result.code, 0)
        rows = support.rows_as_dicts(self.report)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["reason"], "undecodable_name")

    def test_every_not_matched_row_has_a_reason(self):
        self._run({
            "h/IMG_0001.jpg": b"\xff\xd8photo",
            "h/IMG_0002.jpg": b"\xff\xd8photo",
            "h/IMG_0002.jpg.json": support.sidecar_bytes(),
        })
        for row in support.rows_as_dicts(self.report):
            if row["status"] == "not_matched":
                self.assertNotEqual(row["reason"], "")
            else:
                self.assertEqual(row["status"], "matched")
                self.assertEqual(row["reason"], "")


if __name__ == "__main__":
    unittest.main()

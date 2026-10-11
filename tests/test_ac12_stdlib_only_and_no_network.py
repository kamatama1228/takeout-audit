"""AC12: network に 1 件も接続せず、外部 package を 1 つも使わない。"""

import ast
import os
import shutil
import socket
import sys
import tempfile
import unittest

import support

PACKAGE = os.path.join(support.PRODUCT_ROOT, "takeout_audit")


def _imported_modules():
    found = set()
    for filename in sorted(os.listdir(PACKAGE)):
        if not filename.endswith(".py"):
            continue
        with open(os.path.join(PACKAGE, filename), encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), filename)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    found.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                found.add((node.module or "").split(".")[0])
    return found


class OnlyTheStandardLibrary(unittest.TestCase):

    def test_every_import_is_stdlib_or_this_package(self):
        allowed = set(sys.stdlib_module_names) | {"takeout_audit"}
        outside = sorted(_imported_modules() - allowed)
        self.assertEqual(outside, [], "外部 package を import している")

    def test_the_scan_is_not_empty(self):
        self.assertIn("zipfile", _imported_modules())


class NoNetwork(unittest.TestCase):
    """socket を塞いだまま、最後まで動くこと。"""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.takeout = os.path.join(self.root, "takeout")
        os.makedirs(self.takeout)
        support.write_tree(self.takeout, support.takeout_files())
        self.zip_path = os.path.join(self.root, "takeout-001.zip")
        support.write_zip(self.zip_path, support.takeout_files())

        self._originals = (socket.socket, socket.create_connection,
                           socket.getaddrinfo)

        def refuse(*args, **kwargs):
            raise AssertionError("network につなごうとした")

        socket.socket = refuse
        socket.create_connection = refuse
        socket.getaddrinfo = refuse

    def tearDown(self):
        (socket.socket, socket.create_connection,
         socket.getaddrinfo) = self._originals
        shutil.rmtree(self.root, ignore_errors=True)

    def test_a_directory_input_needs_no_network(self):
        report = os.path.join(self.root, "dir.csv")
        self.assertEqual(
            support.run_cli([self.takeout, "--report", report]).code, 0)

    def test_a_zip_input_needs_no_network(self):
        report = os.path.join(self.root, "zip.csv")
        self.assertEqual(
            support.run_cli([self.zip_path, "--report", report]).code, 0)


if __name__ == "__main__":
    unittest.main()

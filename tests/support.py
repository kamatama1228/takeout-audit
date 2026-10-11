"""test 用の道具。Takeout 風の入力を組み立て、CLI を呼び、file の状態を記録する。

実行方法:

    python3 -m unittest discover -s products/prod-002/tests -v

`discover` は `tests/` を sys.path に入れる。product の root（`takeout_audit`
package のある directory）は入らないため、この module の import 時に足す。
"""

import hashlib
import io
import json
import os
import sys
import unicodedata
import zipfile

PRODUCT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PRODUCT_ROOT not in sys.path:
    sys.path.insert(0, PRODUCT_ROOT)

from takeout_audit import cli  # noqa: E402

#: 例に使う epoch と、それを UTC で表したもの。
EPOCH = 1683173696
EPOCH_UTC = "2023-05-04T04:14:56Z"

#: Takeout の典型的な folder（写真と `.json` が同じ folder に並ぶ）
ALBUM = "Takeout/Google Photos/Photos from 2023"


def sidecar_bytes(epoch=EPOCH, title="x", with_time=True):
    """Takeout 風の `.json` の中身。"""
    document = {"title": title,
                "description": "",
                "imageViews": "0"}
    if with_time:
        document["photoTakenTime"] = {"timestamp": str(epoch),
                                      "formatted": "May 4, 2023"}
    return json.dumps(document).encode("utf-8")


# ------------------------------------------------- 展開済み directory を作る

def write_tree(root, files):
    """`{相対 path: bytes}` から directory を作る。"""
    for relative, data in files.items():
        path = os.path.join(root, *relative.split("/"))
        parent = os.path.dirname(path)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent)
        with open(path, "wb") as handle:
            handle.write(data)
    return root


# ------------------------------------------------------------- zip を作る

def write_zip(path, files, utf8_flag=True):
    """`{entry 名: bytes}` から zip を作る。

    `utf8_flag=False` にすると、UTF-8 の flag を落とした entry 名になる
    （文字 code を確定できない名前の再現）。
    """
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            info = zipfile.ZipInfo(name)
            info.compress_type = zipfile.ZIP_DEFLATED
            if not utf8_flag:
                info.flag_bits &= ~0x800
            archive.writestr(info, data)
    if not utf8_flag:
        _clear_utf8_flags(path)
    return path


def _clear_utf8_flags(path):
    """書き出した zip から UTF-8 の flag を落とす（central directory と local）。

    `zipfile` は非 ASCII の名前に必ず flag を立てるため、後から落とす。
    """
    with open(path, "rb") as handle:
        raw = bytearray(handle.read())
    # UTF-8 の flag は bit 11（0x0800）であり、2 byte の flag 欄の上位 byte に
    # 入っている。
    for signature, offset in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
        start = 0
        while True:
            index = raw.find(signature, start)
            if index < 0:
                break
            position = index + offset + 1
            raw[position] = raw[position] & ~0x08
            start = index + 4
    with open(path, "wb") as handle:
        handle.write(bytes(raw))


def takeout_files(photos=("IMG_0001.jpg",), album=ALBUM):
    """写真と、それぞれの `.json` を 1 対 1 で並べた素直な Takeout。"""
    files = {}
    for name in photos:
        files["%s/%s" % (album, name)] = b"\xff\xd8not-a-real-photo"
        files["%s/%s.json" % (album, name)] = sidecar_bytes()
    return files


# ---------------------------------------------------------------- 検証の道具

def sha256(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def snapshot(root):
    """directory 配下の全 file の SHA256・大きさ・mtime_ns。

    **「1 byte も書き込まない」を確かめるための正本である。**
    """
    state = {}
    for current, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for filename in sorted(filenames):
            path = os.path.join(current, filename)
            stat = os.stat(path)
            state[os.path.relpath(path, root)] = (
                sha256(path), stat.st_size, stat.st_mtime_ns)
    return state


def file_list(root):
    """directory 配下の相対 path の集合（新しい file が増えていないかの確認）。"""
    found = set()
    for current, _, filenames in os.walk(root):
        for filename in filenames:
            found.add(os.path.relpath(os.path.join(current, filename), root))
    return found


class Result(object):
    def __init__(self, code, out, err):
        self.code = code
        self.out = out
        self.err = err

    @property
    def text(self):
        """利用者が受け取る文字列の全文（標準出力＋標準エラー）。"""
        return self.out + self.err


def run_cli(argv):
    """CLI を同じ process の中で呼び、終了 code と標準出力・標準エラーを返す。"""
    out = io.StringIO()
    err = io.StringIO()
    code = cli.main(argv, out=out, err=err)
    return Result(code, out.getvalue(), err.getvalue())


def run_module(argv):
    """`python3 -m takeout_audit <argv>` を**別の process として**動かす。

    **同じ process の中で呼ぶ `run_cli` では見えないものがある。** 標準出力の
    文字 code、process の終了 code、traceback がそのまま画面に出ること——
    利用者が実際に受け取る面は、この形でしか測れない。

    QA の差し戻しで分かったことである。`run_cli` は `io.StringIO` に書くため、
    UTF-8 に encode できない文字列でも通ってしまう。**落ちる経路を、Builder の側で
    先に見つけるために、この helper を使う。**
    """
    import subprocess

    environment = dict(os.environ)
    environment["PYTHONPATH"] = PRODUCT_ROOT
    environment["PYTHONIOENCODING"] = "utf-8"
    completed = subprocess.run(
        [sys.executable, "-m", "takeout_audit"] + list(argv),
        env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=120)
    return Result(completed.returncode,
                  completed.stdout.decode("utf-8", "replace"),
                  completed.stderr.decode("utf-8", "replace"))


def undecodable_filename(raw=b"IMG_\xff\xfe02.jpg"):
    """UTF-8 として読めない byte を含む file 名を、str として返す。

    `os.fsdecode` は、読めなかった byte を lone surrogate（`U+DC80`〜`U+DCFF`）
    に移す。**この文字列は UTF-8 に encode できない。**
    """
    return os.fsdecode(raw)


def read_csv(path):
    """CSV を `(header, [row...])` で返す。"""
    import csv

    with open(path, "r", encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    return rows[0], rows[1:]


def rows_as_dicts(path):
    header, rows = read_csv(path)
    return [dict(zip(header, row)) for row in rows]


def row_for(path, media_key):
    for row in rows_as_dicts(path):
        if row["media_key"] == media_key:
            return row
    raise AssertionError("CSV に %s の行がありません" % media_key)


def nfd(text):
    return unicodedata.normalize("NFD", text)


def squeeze(text):
    """改行と引用の `> ` をならす。

    README では、同じ 1 文が行の幅で折り返され、引用の印が付く。語の並びとして
    同じであることを確かめたい場面で使う。
    """
    lines = [line.lstrip("> ").rstrip() for line in text.splitlines()]
    return " ".join(" ".join(lines).split())

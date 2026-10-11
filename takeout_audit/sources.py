"""入力の読み方。展開済みの directory と、zip の両方を同じ形で扱う。

**zip から読んでよいのは、(a) entry 名の一覧と、(b) `.json` entry の中身だけで
ある。** media の entry は 1 件も展開しない。一時 directory も作らない。

理由は 2 つある。この tool は media file の中身を 1 byte も読まない。そして
Takeout は数十〜数百 GB になり得る。取り込む前に確かめるための道具が、利用者の
disk を埋めてはならない。
"""

import os
import zipfile

from takeout_audit import names

#: `.json` として読み込む上限。これを超えるものは読まずに「読めない」と報告する。
#: sidecar は数 KB である。桁違いに大きいものを memory に載せる理由がない。
MAX_SIDECAR_BYTES = 4 * 1024 * 1024

KIND_MEDIA = "media"
KIND_JSON = "json"


class SourceError(Exception):
    """入力そのものを開けなかった。1 件の入力を諦め、他の入力は続ける。"""


class Entry(object):
    """入力の中の file 1 件。

    - `key` … `media_key`。入力の root からの相対 path。`/` 区切り、NFC 正規化済み。
      対応づけと並べ替えは、すべてこの値に対して行う。
    - `display` … 表示用。入力に現れたままの表記。zip 入力と directory 入力で
      必ず違うため、比較には使わない。
    - `undecodable` … file 名の文字 code を確定できなかった。

    **`key` と `display` は、必ず UTF-8 に encode できる文字列である。**
    decode できなかった byte は `names.escape_undecodable` で置き換えてある。
    元の名前そのものは `_locator` にだけ残し、file を読むときにそれを使う。
    """

    __slots__ = ("key", "display", "kind", "undecodable", "_locator")

    def __init__(self, key, display, kind, undecodable=False, locator=None):
        self.key = key
        self.display = display
        self.kind = kind
        self.undecodable = undecodable
        self._locator = locator


class Source(object):
    """入力 1 件（directory 1 つ、または zip 1 つ）。"""

    def entries(self):
        raise NotImplementedError

    def read_sidecar(self, entry):
        """`.json` の中身を bytes で返す。読めなければ `None` を返す。"""
        raise NotImplementedError

    def close(self):
        pass


class DirectorySource(Source):
    """展開済みの Takeout。"""

    def __init__(self, root):
        self.root = root

    def entries(self):
        found = []
        for current, dirnames, filenames in os.walk(self.root):
            dirnames.sort()
            for filename in sorted(filenames):
                path = os.path.join(current, filename)
                relative = os.path.relpath(path, self.root)
                key = names.normalize(
                    names.escape_undecodable(relative.replace(os.sep, "/")))
                kind = (KIND_JSON if names.is_json_name(filename)
                        else KIND_MEDIA)
                found.append(Entry(key, names.escape_undecodable(path), kind,
                                   undecodable=_has_surrogates(relative),
                                   locator=path))
        return found

    def read_sidecar(self, entry):
        try:
            if os.path.getsize(entry._locator) > MAX_SIDECAR_BYTES:
                return None
            with open(entry._locator, "rb") as handle:
                return handle.read()
        except OSError:
            return None


class ZipSource(Source):
    """zip のままの Takeout。**media entry は 1 件も展開しない。**"""

    def __init__(self, path):
        self.path = path
        try:
            self._zip = zipfile.ZipFile(path, "r")
        except (zipfile.BadZipFile, OSError, NotImplementedError) as error:
            raise SourceError(
                "%s could not be read as a zip archive (%s)"
                % (path, error.__class__.__name__))

    def entries(self):
        found = []
        try:
            infos = self._zip.infolist()
        except (zipfile.BadZipFile, OSError) as error:
            raise SourceError(
                "%s could not be read as a zip archive (%s)"
                % (self.path, error.__class__.__name__))
        for info in infos:
            if info.is_dir():
                continue
            raw_name = names.escape_undecodable(info.filename)
            key = names.normalize(raw_name.replace("\\", "/"))
            kind = (KIND_JSON if names.is_json_name(raw_name)
                    else KIND_MEDIA)
            found.append(Entry(key, "%s::%s" % (self.path, raw_name), kind,
                               undecodable=_zip_name_is_uncertain(info),
                               locator=info))
        return found

    def read_sidecar(self, entry):
        info = entry._locator
        if info.file_size > MAX_SIDECAR_BYTES:
            return None
        try:
            with self._zip.open(info, "r") as handle:
                return handle.read(MAX_SIDECAR_BYTES + 1)
        except (zipfile.BadZipFile, OSError, RuntimeError, EOFError,
                NotImplementedError, ValueError):
            # 壊れた entry、暗号化された entry、未対応の圧縮方式。
            # どれも「読めなかった」として報告し、落ちない。
            return None

    def close(self):
        try:
            self._zip.close()
        except OSError:
            pass


def open_source(path):
    """path を見て、directory 入力か zip 入力かを決める。"""
    if os.path.isdir(path):
        return DirectorySource(path)
    if not os.path.exists(path):
        raise SourceError("%s does not exist" % path)
    if not zipfile.is_zipfile(path):
        raise SourceError(
            "%s is neither a directory nor a zip archive "
            "(a multi-part archive such as .z01 cannot be read)" % path)
    return ZipSource(path)


def _zip_name_is_uncertain(info):
    """zip の entry 名の文字 code を確定できないか。

    UTF-8 の flag が立っていない entry 名は、規格のうえでは cp437 である。実際には
    作成した環境の文字 code であることが多く、ASCII の範囲を出た名前は、読み方を
    確定できない。この件を「sidecar が無い」に混ぜない。
    """
    if info.flag_bits & 0x800:
        return False
    return not info.filename.isascii()


def _has_surrogates(text):
    """file system から読んだ名前に、decode できなかった byte が残っているか。"""
    return any(0xDC80 <= ord(char) <= 0xDCFF for char in text)

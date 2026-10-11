"""名前の正規化、候補の絞り込み、対応づけの 4 規則。

**この module が、この tool の主張のすべてである。** ここにある規則表が実物の
Takeout を覆えていないとき、結果は必ず「対応づかない」側に倒れる。つまり、
tool が知らないことが、利用者の問題として報告される。そのため、

- 会社が決めた定数は、すべてこの module の先頭 1 か所に集めてある。
- どの規則で結び付いたかは、必ず `rule` として外に出す。
- 候補が複数残ったときは、黙って 1 つに決めない。

比較は、すべて NFC に正規化した後の名前に対して行う。**大文字小文字は区別する**
（区別すると、別の写真どうしを結び付けずに済む）。
"""

import re
import unicodedata

# ---------------------------------------------------------------- 定数
# **下の値は、会社が決めたものであり、実物の Takeout で検証していない。**

#: 候補とみなす共通接頭辞の最小の長さ（§「候補の定義」）。
#: 大きくすると「規則の不足」が「sidecar が無い」に流れ、小さくするとその逆になる。
MIN_COMMON_PREFIX = 8

#: 切り詰められた `.json` 名（R2）として受け入れる最小の長さ。
#: 短い接頭辞での一致を認めると、無関係な file どうしが結び付く。
MIN_TRUNCATED_LENGTH = 8

#: `.json` 名に挿入されることがある語（R4）。
INSERT_WORDS = ("supplemental-metadata",)

#: sidecar の拡張子。
JSON_SUFFIX = ".json"

# `IMG_1234(1).jpg` のように、拡張子の前に連番が付いた形
_NUMBERED = re.compile(r"^(?P<stem>.*)\((?P<n>\d+)\)(?P<ext>\.[^.]*)$", re.DOTALL)


def normalize(text):
    """NFC に正規化する。

    macOS 由来の名前は NFD、`.json` 側が NFC、ということが起こり得る。放置すると
    どちらも「対応づかない」側に倒れる。
    """
    return unicodedata.normalize("NFC", text)


def escape_undecodable(text):
    """decode できなかった byte を、書き出せる文字列に置き換える。

    **file system から読んだ名前は、UTF-8 として読めない byte をそのまま含み得る**
    （Linux の file 名は byte 列であり、別の文字 code の環境で展開された Takeout
    では実際に起こる）。Python はこの byte を lone surrogate（`U+DC80`〜`U+DCFF`）
    として持つが、**その文字列は UTF-8 に encode できない。** 並べ替えも、CSV への
    書き出しも、画面への表示も、そのままでは例外になる。

    そこで、この tool の中を通る名前は、入口（`sources`）と出口（`report`）の
    両方でこの関数を通す。**出口だけを直すと並べ替えで落ち、入口だけを直すと
    別経路で作られた行で落ちる。** 置き換えは決定的で、同じ名前は必ず同じ文字列に
    なるため、並び順は入力の走査順に依存しない。

    - `U+DC80`〜`U+DCFF` … 元の byte を `\\xff` の形で書く。
    - その他の lone surrogate … `\\ud800` の形で書く。
    - それ以外 … そのまま。

    置き換えた名前は、その時点で `undecodable_name` として報告される行にしか
    現れない。対応づけの対象にはならない。
    """
    if not any(0xD800 <= ord(char) <= 0xDFFF for char in text):
        return text
    out = []
    for char in text:
        code = ord(char)
        if 0xDC80 <= code <= 0xDCFF:
            out.append("\\x%02x" % (code - 0xDC00))
        elif 0xD800 <= code <= 0xDFFF:
            out.append("\\u%04x" % code)
        else:
            out.append(char)
    return "".join(out)


def is_json_name(name):
    """sidecar の名前か。拡張子の大文字小文字は区別しない。"""
    return name.lower().endswith(JSON_SUFFIX)


def dirname(key):
    """`media_key`（`/` 区切りの相対 path）の directory 部分。"""
    index = key.rfind("/")
    return key[:index] if index >= 0 else ""


def basename(key):
    index = key.rfind("/")
    return key[index + 1:] if index >= 0 else key


def stem(filename):
    """最後の拡張子を落とした部分。拡張子が無ければそのまま。"""
    index = filename.rfind(".")
    return filename[:index] if index > 0 else filename


def json_base(filename):
    """`<name>.json` から `<name>` を取り出す。"""
    return filename[:-len(JSON_SUFFIX)]


def is_candidate(media_filename, json_basename):
    """候補かどうか（絞り込みだけを行う。対応づけの判断はしない）。

    media の file 名から拡張子を除いたものを `m`、`.json` を除いた sidecar の
    file 名を `j` として、

    1. `j` が `m` の接頭辞である、または `m` が `j` の接頭辞である
    2. `m` と `j` の共通接頭辞が `MIN_COMMON_PREFIX` 文字以上ある

    のどちらかを満たすものを候補とする。
    """
    m = stem(media_filename)
    j = json_basename
    if not m or not j:
        return False
    if j.startswith(m) or m.startswith(j):
        return True
    return _common_prefix_length(m, j) >= MIN_COMMON_PREFIX


def _common_prefix_length(left, right):
    length = 0
    for a, b in zip(left, right):
        if a != b:
            break
        length += 1
    return length


def expected_json_bases(media_filename):
    """この tool が「対応する」とみなす `.json` 名（`.json` を除いた形）。

    返すのは `(rule, expected)` の列である。`rule` は、どの変換を使ったかを
    そのまま表す。

    - **R1** 完全一致 … `IMG_1234.jpg` → `IMG_1234.jpg`
    - **R3** `(n)` の位置違い … `IMG_1234(1).jpg` → `IMG_1234.jpg(1)`
    - **R4** 挿入語 … `IMG_1234.jpg` → `IMG_1234.jpg.supplemental-metadata`
    - R3 と R4 は重なり得る（`IMG_1234.jpg.supplemental-metadata(1)`）。
      そのときの `rule` は `R3+R4` になる。

    **R2（末尾の切り詰め）は、ここでは作らない。** 切り詰めは、上のどの形に対しても
    起こり得る「後ろを削る」変換であるため、`match_rule` の側で扱う。
    """
    forms = [("R1", media_filename, "")]
    matched = _NUMBERED.match(media_filename)
    if matched:
        forms.append(("R3",
                      matched.group("stem") + matched.group("ext"),
                      "(%s)" % matched.group("n")))

    expected = []
    for rule, base, suffix in forms:
        expected.append((rule, base + suffix))
        for word in INSERT_WORDS:
            combined = "R4" if rule == "R1" else rule + "+R4"
            expected.append((combined, base + "." + word + suffix))
    return expected


def match_rule(media_filename, json_basename):
    """この 2 つが対応づくなら `rule` を、つかないなら `None` を返す。

    切り詰め（R2）は、どの形に対しても起こり得るため、ここで一度に扱う。
    `IMG_1234.jpg.supplemental-metadata` が `IMG_1234.jpg.suppl` に切り詰め
    られていれば `R4+R2` になる。
    """
    for rule, expected in expected_json_bases(media_filename):
        if json_basename == expected:
            return rule
        if (len(json_basename) >= MIN_TRUNCATED_LENGTH
                and len(json_basename) < len(expected)
                and expected.startswith(json_basename)):
            return "R2" if rule == "R1" else rule + "+R2"
    return None


def rule_rank(rule):
    """規則の優先順位。小さいほど「素直な」対応づけである。

    同じ順位の候補が 2 件以上残ったときは、どれかに決めない（`ambiguous_match`）。
    順位は、使った変換の数と種類だけで決まる。file の並び順には依存しない。
    """
    parts = rule.split("+")
    return (1 if "R2" in parts else 0,
            1 if "R3" in parts else 0,
            1 if "R4" in parts else 0)

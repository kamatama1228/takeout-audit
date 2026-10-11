"""takeout-audit — Google Photos Takeout の「取り込み前」監査 CLI。

写真を取り込む前に、「この tool の規則では `.json` に対応づけられなかった写真が
何件あり、それぞれ何が理由か」を、1 枚ごとの行と集計で出す。

設計上、最も重要な前提は 2 つある。

1. **入力を 1 byte も書き換えない。** zip は entry 名の一覧と `.json` entry の
   中身だけを読み、media entry は 1 件も展開しない。media file の中身は読まない。
2. **この tool が言えるのは「この tool の規則で、こうなった」までである。**
   対応づけの規則は、実物の Takeout で検証されていない。利用者のライブラリが
   どう振る舞うかを、この tool は知らない。その旨を `--help` と集計と README に
   出す。

標準 library だけで動く。外部 package は 1 つも import しない。
network には 1 回も接続しない。
"""

__version__ = "0.1.0"
TOOL_NAME = "takeout-audit"

# 利用者が受け取る面（`--help` の末尾・集計の末尾・README の冒頭）に必ず出す 1 行。
# **この文を弱めてはいけない。** この tool の規則は、実物の Takeout で検証されて
# いない。
UNVERIFIED_NOTICE = (
    "This tool's matching rules have not been verified against a real Google "
    "Takeout export. Results describe what this tool could match - not what "
    "your photo library will do."
)

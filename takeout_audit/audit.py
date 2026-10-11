"""1 枚ごとの判定。**この tool の結論は、すべてここで決まる。**

判定の順序は 1 つだけである。

1. file 名の文字 code を確定できない → `undecodable_name`
2. 候補の `.json` が 1 件も無い → `no_sidecar`
3. 候補はあるが、どの規則にも当たらない → `unmatched_by_known_rules`
4. 同じ順位の規則で 2 件以上に当たる → `ambiguous_match`（**黙って 1 つに
   決めない**）
5. 1 件に決まった → `.json` を読む。撮影日時が無ければ `sidecar_without_time`、
   読めなければ `unparsable_time`、読めれば `matched`

**`no_sidecar` と `unmatched_by_known_rules` を割ることに意味がある。** 前者は
Takeout にもともと sidecar が無いこと、後者は **この tool の規則が足りない
かもしれないこと** を指す。混ぜると、tool の不足が利用者の問題として報告される。
"""

from takeout_audit import names, sidecar, sources

STATUS_MATCHED = "matched"
STATUS_NOT_MATCHED = "not_matched"

REASON_NO_SIDECAR = "no_sidecar"
REASON_UNMATCHED = "unmatched_by_known_rules"
REASON_AMBIGUOUS = "ambiguous_match"
REASON_NO_TIME = "sidecar_without_time"
REASON_UNPARSABLE_TIME = "unparsable_time"
REASON_UNDECODABLE_NAME = "undecodable_name"

#: 集計と CSV に出す `reason` の順序（件数が 0 でも、この順で必ず出す）。
REASONS = (
    REASON_NO_SIDECAR,
    REASON_UNMATCHED,
    REASON_AMBIGUOUS,
    REASON_NO_TIME,
    REASON_UNPARSABLE_TIME,
    REASON_UNDECODABLE_NAME,
)

#: `candidates` 列に並べる候補の上限。超えた分は `|+N more` と書く。
MAX_LISTED_CANDIDATES = 8

#: media として数えない file。**Takeout が書き出す目録であり、写真ではない。**
#: ここに入れた分だけ「対応づかなかった件数」が小さくなる。会社が決めた一覧で
#: あり、実物の Takeout で検証していない。
NON_MEDIA_BASENAMES = ("archive_browser.html",)


class Row(object):
    """CSV の 1 行。**1 枚につき 1 行。候補が何件あっても増やさない。**"""

    __slots__ = ("media_path", "media_key", "json_path", "rule",
                 "taken_time_utc", "status", "reason", "candidates")

    def __init__(self, media_path, media_key):
        self.media_path = media_path
        self.media_key = media_key
        self.json_path = ""
        self.rule = ""
        self.taken_time_utc = ""
        self.status = STATUS_NOT_MATCHED
        self.reason = ""
        self.candidates = ""

    def as_list(self):
        return [self.media_path, self.media_key, self.json_path, self.rule,
                self.taken_time_utc, self.status, self.reason,
                self.candidates]


def _sort_key(row):
    """並べ替えの鍵。zip の entry 順にも、directory の走査順にも依存しない。

    **decode できなかった byte を含む名前でも、ここで落ちてはならない。** 落ちると、
    その Takeout の他の数万件もまとめて失われる。`escape_undecodable` は、surrogate
    が無ければ何もしない（`sources` が入口で通した後は、ここでは何も起きない）。
    """
    return (names.escape_undecodable(row.media_key).encode("utf-8"),
            names.escape_undecodable(row.media_path).encode("utf-8"))


def is_media(entry):
    if entry.kind != sources.KIND_MEDIA:
        return False
    return names.basename(entry.key).lower() not in NON_MEDIA_BASENAMES


def audit(opened_sources):
    """開いた入力の列から、`Row` の列を作る。並び順は決定的である。"""
    media = []
    sidecars_by_dir = {}

    for source in opened_sources:
        for entry in source.entries():
            if entry.kind == sources.KIND_JSON:
                sidecars_by_dir.setdefault(
                    names.dirname(entry.key), []).append((source, entry))
            elif is_media(entry):
                media.append((source, entry))

    rows = [_judge(entry, sidecars_by_dir) for _, entry in media]
    rows.sort(key=_sort_key)
    return rows


def _judge(entry, sidecars_by_dir):
    row = Row(entry.display, entry.key)
    if entry.undecodable:
        row.reason = REASON_UNDECODABLE_NAME
        return row

    filename = names.basename(entry.key)
    candidates = _candidates(filename, sidecars_by_dir.get(
        names.dirname(entry.key), ()))
    row.candidates = _format_candidates(candidates)

    if not candidates:
        row.reason = REASON_NO_SIDECAR
        return row

    matches = []
    for source, json_entry, json_basename in candidates:
        rule = names.match_rule(filename, json_basename)
        if rule is not None:
            matches.append((names.rule_rank(rule), rule, source, json_entry))
    if not matches:
        row.reason = REASON_UNMATCHED
        return row

    best = min(rank for rank, _, _, _ in matches)
    winners = [item for item in matches if item[0] == best]
    if len(winners) > 1:
        row.reason = REASON_AMBIGUOUS
        return row

    _, rule, source, json_entry = winners[0]
    row.rule = rule
    row.json_path = json_entry.display
    state, taken = sidecar.read_taken_time(source.read_sidecar(json_entry))
    if state == sidecar.OK:
        row.status = STATUS_MATCHED
        row.taken_time_utc = taken
    elif state == sidecar.NO_TIME:
        row.reason = REASON_NO_TIME
    else:
        row.reason = REASON_UNPARSABLE_TIME
    return row


def _candidates(media_filename, same_directory):
    """同じ directory にある `.json` のうち、候補になるものだけを返す。

    **探索は、同じ directory の中だけで行う。** Takeout が写真と `.json` を同じ
    folder に置くという前提に依る。これは実物で検証していない。
    """
    found = []
    for source, json_entry in same_directory:
        if json_entry.undecodable:
            continue
        json_basename = names.json_base(names.basename(json_entry.key))
        if names.is_candidate(media_filename, json_basename):
            found.append((source, json_entry, json_basename))
    found.sort(key=lambda item: item[1].key.encode("utf-8"))
    return found


def _format_candidates(candidates):
    """候補を `media_key` と同じ形で、`|` で区切って並べる。"""
    keys = [json_entry.key for _, json_entry, _ in candidates]
    if len(keys) <= MAX_LISTED_CANDIDATES:
        return "|".join(keys)
    shown = keys[:MAX_LISTED_CANDIDATES]
    return "|".join(shown) + "|+%d more" % (len(keys) - MAX_LISTED_CANDIDATES)

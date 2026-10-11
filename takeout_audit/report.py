"""出力。CSV と、標準出力の集計。

**利用者が受け取る面に出る文字列は、すべて英語である。**

集計の見出しは「この tool の規則では対応づかなかった件数」である。「復元できない
件数」でも「日付を失う件数」でもない。写真が実際にどう扱われるかを決めるのは、
利用者が最後に使う取り込み側であって、この tool ではない。
"""

import csv

from takeout_audit import UNVERIFIED_NOTICE, audit, names

#: CSV の列。**順序も名前も固定である。**
CSV_COLUMNS = [
    "media_path",
    "media_key",
    "json_path",
    "rule",
    "taken_time_utc",
    "status",
    "reason",
    "candidates",
]

_LIST_HEADERS = ["media_key", "rule", "taken_time_utc", "status", "reason"]

MATCHED_LABEL = "matched to a .json and read a capture time (matched)"
NOT_MATCHED_LABEL = "not matched by this tool's rules"


def _writable(cell):
    """CSV にも画面にも出せる形にする。

    **出口でもう一度 `escape_undecodable` を通す。** 入口（`sources`）で通した分は
    ここでは何も変わらないが、**CSV の書き出しは、入口を通っていない `Row` に対して
    も落ちてはならない。** 落ちれば CSV が 1 行も書かれず、その Takeout の他の
    数万件もまとめて失われる。
    """
    return names.escape_undecodable(cell)


def write_csv(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(CSV_COLUMNS)
        for row in rows:
            writer.writerow([_writable(cell) for cell in row.as_list()])


def _table(rows):
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    lines = []
    for index, row in enumerate(rows):
        lines.append("  ".join(cell.ljust(widths[i])
                               for i, cell in enumerate(row)).rstrip())
        if index == 0:
            lines.append("  ".join("-" * width for width in widths))
    return lines


def render_list(rows):
    """1 枚ごとの表。`--list` のときだけ出す（既定は CSV に書く）。"""
    table = [_LIST_HEADERS]
    for row in rows:
        table.append([_writable(row.media_key), row.rule or "-",
                      row.taken_time_utc or "-", row.status,
                      row.reason or "-"])
    return "\n".join(_table(table))


def counts(rows):
    """`(全件, matched, not matched, reason ごとの件数)` を返す。"""
    matched = sum(1 for row in rows if row.status == audit.STATUS_MATCHED)
    by_reason = dict((reason, 0) for reason in audit.REASONS)
    for row in rows:
        if row.reason:
            by_reason[row.reason] = by_reason.get(row.reason, 0) + 1
    return len(rows), matched, len(rows) - matched, by_reason


def render_summary(rows):
    """集計の表。**末尾に、検証していないことを必ず書く。**"""
    total, matched, not_matched, by_reason = counts(rows)
    table = [["count", "what it means"],
             [str(total), "media files looked at"],
             [str(matched), MATCHED_LABEL],
             [str(not_matched), NOT_MATCHED_LABEL]]
    for reason in audit.REASONS:
        table.append([str(by_reason[reason]), "  " + reason])

    by_rule = {}
    for row in rows:
        if row.status == audit.STATUS_MATCHED:
            by_rule[row.rule] = by_rule.get(row.rule, 0) + 1
    for rule in sorted(by_rule):
        table.append([str(by_rule[rule]), "  matched by rule " + rule])

    lines = ["Takeout audit summary"]
    lines.extend(_table(table))
    lines.append("")
    lines.append(UNVERIFIED_NOTICE)
    return "\n".join(lines)

"""takeout-audit の command line。

終了 code:

- `0` … 最後まで動いた（1 件ごとの「対応づかなかった」は、ここに含む）
- `2` … 何も処理せずに中止した（安全のための中止・引数の誤り・読める入力が無い）

**入力に対して、この tool は読み取りしか行わない。** 書き出すのは `--report` で
指定した CSV だけである。
"""

import argparse
import os
import sys

from takeout_audit import TOOL_NAME, UNVERIFIED_NOTICE, __version__
from takeout_audit import audit, report, sources

EXIT_OK = 0
EXIT_ABORTED = 2

DESCRIPTION = (
    "Look at a Google Photos Takeout before you import it, and report how "
    "many photos and videos this tool could match to their .json sidecar, "
    "and why the rest could not be matched. Nothing in the input is written "
    "to, and zip archives are never extracted."
)

EPILOG = (
    "An input may be a directory of an already extracted Takeout, or one or "
    "more .zip files of a Takeout that is still packed. Several zip files "
    "may be given at once, because a photo and its .json sidecar can end up "
    "in different parts of the same export.\n\n"
    "Each media file gets exactly one row, whatever the number of candidate "
    "sidecars. When two candidates are equally good, this tool does not pick "
    "one: the row says ambiguous_match and the candidates column lists them.\n\n"
    + UNVERIFIED_NOTICE
)


def build_parser():
    parser = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description=DESCRIPTION,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "inputs", nargs="+", metavar="INPUT",
        help="a directory of an extracted Takeout, or .zip files of one")
    parser.add_argument(
        "--report", metavar="PATH",
        help="write one row per media file to this CSV file. "
             "The path may not be inside the input")
    parser.add_argument(
        "--list", action="store_true", dest="list_rows",
        help="also print one row per media file to the screen")
    parser.add_argument(
        "--version", action="version",
        version="%s %s" % (TOOL_NAME, __version__))
    return parser


def report_path_is_inside_input(report_path, input_paths):
    """`--report` の出力先が入力の内側を指すか。

    判定は、両方を実 path に解決してから行う（symlink・相対 path・`..` を
    解決する）。大文字小文字を区別しない file system でも判定が割れないよう、
    比較は `normcase` を通す。

    - directory 入力 … 解決後の出力先が、その directory の配下にあるなら内側。
    - zip 入力 … 解決後の出力先が、その zip file そのものなら内側。zip が置かれた
      directory は制限しない（zip の中には書き込めないため、隣に出しても入力は
      1 byte も変わらない）。
    """
    target = os.path.normcase(os.path.realpath(report_path))
    for raw in input_paths:
        resolved = os.path.normcase(os.path.realpath(raw))
        if os.path.isdir(raw):
            if target == resolved or target.startswith(resolved + os.sep):
                return raw
        elif target == resolved:
            return raw
    return None


def main(argv=None, out=None, err=None):
    out = out if out is not None else sys.stdout
    err = err if err is not None else sys.stderr
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.report:
        inside = report_path_is_inside_input(args.report, args.inputs)
        if inside is not None:
            print("Stopped before looking at anything: the --report path "
                  "(%s) is inside the input (%s). Nothing was read and "
                  "nothing was written. Please choose a path outside the "
                  "input." % (args.report, inside), file=out)
            return EXIT_ABORTED

    opened = []
    unreadable = []
    try:
        for raw in args.inputs:
            try:
                opened.append(sources.open_source(raw))
            except sources.SourceError as error:
                unreadable.append(str(error))
                print("Skipped an input: %s" % error, file=err)

        if not opened:
            print("Stopped: none of the given inputs could be read. "
                  "Nothing was written.", file=out)
            return EXIT_ABORTED

        rows = audit.audit(opened)

        if args.report:
            report.write_csv(args.report, rows)
        if args.list_rows and rows:
            print(report.render_list(rows), file=out)
        print(report.render_summary(rows), file=out)
        if unreadable:
            print("", file=out)
            print("%d of the given inputs could not be read and are not "
                  "part of the counts above." % len(unreadable), file=out)
        if args.report:
            print("", file=out)
            print("One row per media file was written to %s" % args.report,
                  file=out)
        return EXIT_OK
    finally:
        for source in opened:
            source.close()

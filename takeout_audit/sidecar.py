"""`.json` から撮影日時を取り出す。

この tool が読むのは **撮影日時だけ**である。位置・アルバム・人物・説明文には
触れない。
"""

import datetime
import json

#: 撮影日時が入っている場所。`.json` の中で、この path だけを読む。
TAKEN_TIME_PATH = ("photoTakenTime", "timestamp")

OK = "ok"
NO_TIME = "no_time"
UNPARSABLE = "unparsable"


def read_taken_time(raw):
    """`(状態, UTC の文字列)` を返す。

    - `(OK, "2023-05-04T03:34:56Z")` … 読めた
    - `(NO_TIME, "")` … JSON としては読めたが、撮影日時の項目が無い
    - `(UNPARSABLE, "")` … JSON として読めない、または日時として読めない
    """
    if raw is None:
        return UNPARSABLE, ""
    try:
        document = json.loads(raw.decode("utf-8-sig"))
    except (ValueError, UnicodeDecodeError):
        return UNPARSABLE, ""
    if not isinstance(document, dict):
        return NO_TIME, ""

    value = document
    for key in TAKEN_TIME_PATH:
        if not isinstance(value, dict) or key not in value:
            return NO_TIME, ""
        value = value[key]

    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return UNPARSABLE, ""
    try:
        epoch = int(value)
    except ValueError:
        return UNPARSABLE, ""
    try:
        moment = datetime.datetime.fromtimestamp(
            epoch, datetime.timezone.utc)
    except (OverflowError, OSError, ValueError):
        return UNPARSABLE, ""
    return OK, moment.strftime("%Y-%m-%dT%H:%M:%SZ")

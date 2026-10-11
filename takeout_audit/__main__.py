"""`python3 -m takeout_audit` の入口。"""

import sys

from takeout_audit import cli

if __name__ == "__main__":
    sys.exit(cli.main())

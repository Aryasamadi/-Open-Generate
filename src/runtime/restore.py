"""
نقطه ورود og-restore — پل بین console script و deploy/restore.sh،
به همان دلیلی که src/runtime/backup.py وجود دارد.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    script = Path(__file__).parent.parent.parent / "deploy" / "restore.sh"
    if not script.exists():
        print(f"❌ اسکریپت restore یافت نشد: {script}", file=sys.stderr)
        sys.exit(1)

    if len(sys.argv) < 2:
        print("استفاده: og-restore <path-to-backup-file>", file=sys.stderr)
        sys.exit(1)

    result = subprocess.run(["bash", str(script), *sys.argv[1:]])
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()

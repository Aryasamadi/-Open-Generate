"""
نقطه ورود og-backup.

منطق واقعی backup (pg_dump، رمزنگاری، checksum، آپلود offsite) در
deploy/backup.sh پیاده‌سازی شده، چون مستقیماً با `docker compose exec`
کار می‌کند و تکرار همان منطق در پایتون فقط نگهداری را سخت‌تر می‌کرد.
این فایل صرفاً پل بین console script نصب‌شده با pip (`og-backup`) و
همان اسکریپت است، تا pyproject.toml با واقعیت پروژه هماهنگ باشد.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    script = Path(__file__).parent.parent.parent / "deploy" / "backup.sh"
    if not script.exists():
        print(f"❌ اسکریپت backup یافت نشد: {script}", file=sys.stderr)
        sys.exit(1)

    result = subprocess.run(["bash", str(script), *sys.argv[1:]])
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()

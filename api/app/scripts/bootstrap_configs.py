from __future__ import annotations

import json
from pathlib import Path

from app.core.database import SessionLocal
from app.models import SysConfig

CONFIG_PATH = Path("/app/deploy/sys_configs.production.json")


def main() -> None:
    records = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    with SessionLocal.begin() as db:
        for record in records:
            item = db.get(SysConfig, record["key"])
            if item is None:
                item = SysConfig(key=record["key"])
                db.add(item)
            item.value = record["value"]
            item.value_type = record.get("value_type", "json")
            item.description = record.get("description")
            item.is_secret = bool(record.get("is_secret", False))
    print(f"Production sys_configs applied: {len(records)}")


if __name__ == "__main__":
    main()

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from .config import QUEUE_PATH


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_queue(path: Path = QUEUE_PATH) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_queue(items: list[dict], path: Path = QUEUE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")


def make_application_id(park: str, url: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", park.lower()).strip("-")[:16]
    # Prefer numeric job ids from known park URL shapes.
    for pattern in (
        r"/job-details/(\d+)",
        r"/company-jobs/details/\d+/(\d+)",
        r"job_id=(\d+)",
        r"/(\d+)/?$",
    ):
        match = re.search(pattern, url)
        if match:
            return f"{slug}-{match.group(1)}"
    tail = re.sub(r"[^a-zA-Z0-9]+", "-", urlparse(url).path)[-36:].strip("-")
    return f"{slug}-{tail or 'job'}"


def upsert_items(items: list[dict], path: Path = QUEUE_PATH) -> list[dict]:
    existing_list = load_queue(path)
    existing_by_id = {item["id"]: item for item in existing_list}
    existing_by_url = {item["url"]: item for item in existing_list if "url" in item}

    for item in items:
        prev = existing_by_id.get(item["id"]) or existing_by_url.get(item.get("url", ""))
        if prev:
            target_id = prev["id"]
            merged = {**item, "id": target_id}
            if prev.get("status") in {"approved", "sent", "rejected"}:
                for k in ("status", "approved_at", "sent_at", "rejected_at"):
                    if k in prev:
                        merged[k] = prev[k]
            existing_by_id[target_id] = merged
        else:
            existing_by_id[item["id"]] = item

    merged_list = list(existing_by_id.values())
    save_queue(merged_list, path)
    return merged_list


def get_item(app_id: str, path: Path = QUEUE_PATH) -> dict | None:
    for item in load_queue(path):
        if item["id"] == app_id:
            return item
    return None


def set_status(app_ids: list[str], status: str, path: Path = QUEUE_PATH) -> list[dict]:
    items = load_queue(path)
    wanted = set(app_ids)
    updated = []
    stamp_key = {
        "approved": "approved_at",
        "rejected": "rejected_at",
        "sent": "sent_at",
        "pending": "pending_at",
    }[status]
    for item in items:
        if item["id"] in wanted:
            item["status"] = status
            item[stamp_key] = _now()
            updated.append(item)
    save_queue(items, path)
    return updated


def by_status(status: str, path: Path = QUEUE_PATH) -> list[dict]:
    return [item for item in load_queue(path) if item.get("status") == status]

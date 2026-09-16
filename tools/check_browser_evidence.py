"""保守判定脱敏浏览器证据；错误页、资源失败与完整加载分别报告。"""
from __future__ import annotations


def assess(page: dict, events: list[dict], allowed_hosts: set[str], *, foreground: bool, require_media: bool = False) -> dict:
    """只消费主机、DOM 状态与网络元数据，不保存网址、正文或账号。"""
    errors = [e for e in events if (e.get("failed") or e.get("error")) and not e.get("canceled")]
    document_failed = any(e.get("type") == "Document" for e in errors)
    invalid_page = page.get("errorPage") or page.get("host") not in allowed_hosts
    if invalid_page or document_failed:
        state = "failed"
    elif not foreground or page.get("ready") != "complete" or not page.get("textLength", 0):
        state = "incomplete"
    elif errors:
        state = "partial"
    elif require_media and not any(
        v.get("readyState", 0) >= 3 and v.get("currentTime", 0) > 0
        and not v.get("paused", True) and not v.get("error") for v in page.get("video", [])
    ):
        state = "media_unconfirmed"
    else:
        state = "passed"
    return {"state": state, "passed": state == "passed", "document_failed": document_failed,
            "resource_errors": sum(e.get("type") != "Document" for e in errors)}

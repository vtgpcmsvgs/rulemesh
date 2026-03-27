#!/usr/bin/env python3
"""发送 RuleMesh upstream webhook 消息。"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import sync_upstream_rules  # noqa: E402


def github_run_url() -> str | None:
    server = os.environ.get("GITHUB_SERVER_URL")
    repo = os.environ.get("GITHUB_REPOSITORY")
    run_id = os.environ.get("GITHUB_RUN_ID")
    if server and repo and run_id:
        return f"{server}/{repo}/actions/runs/{run_id}"
    return None


def build_workflow_failure_message(step_results: str) -> str:
    workflow = os.environ.get("GITHUB_WORKFLOW", "unknown")
    job_name = os.environ.get("GITHUB_JOB", "unknown")
    event_name = os.environ.get("GITHUB_EVENT_NAME", "unknown")
    repository = os.environ.get("GITHUB_REPOSITORY", "unknown")
    run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "unknown")
    sha = os.environ.get("GITHUB_SHA", "")[:12]
    ref_name = os.environ.get("GITHUB_REF_NAME", "unknown")
    now_text = dt.datetime.now().astimezone().isoformat(timespec="seconds")

    lines = [
        "RuleMesh upstream 工作流失败",
        f"时间: {now_text}",
        f"仓库: {repository}",
        f"工作流: {workflow}",
        f"任务: {job_name}",
        f"事件: {event_name}",
        f"分支: {ref_name}",
        f"尝试次数: {run_attempt}",
    ]
    if sha:
        lines.append(f"提交: {sha}")

    run_url = github_run_url()
    if run_url:
        lines.append(f"运行链接: {run_url}")

    if step_results.strip():
        lines.append(f"步骤结果: {step_results.strip()}")

    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="发送 RuleMesh upstream webhook 消息")
    subparsers = parser.add_subparsers(dest="command", required=True)

    failure_parser = subparsers.add_parser("workflow-failure", help="发送工作流失败消息")
    failure_parser.add_argument(
        "--step-results",
        default="",
        help="工作流步骤结果摘要",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = sync_upstream_rules.resolve_feishu_webhook_config()
    if config is None:
        raise RuntimeError("Feishu webhook is not configured.")

    message = build_workflow_failure_message(args.step_results)
    sync_upstream_rules.send_feishu_webhook_message(config, message)
    print(f"[INFO] webhook message sent: {args.command}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

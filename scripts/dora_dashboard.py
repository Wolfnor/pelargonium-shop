#!/usr/bin/env python3
"""Build a small DORA dashboard from real GitHub repository history."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt


def github_get(path: str):
    repository = os.environ.get("GITHUB_REPOSITORY", "Wolfnor/pelargonium-shop")
    token = os.environ.get("GITHUB_TOKEN", "")
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "pelargonium-shop-dora",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def collect_metrics() -> dict:
    commits = github_get("/commits?per_page=100")
    deployments = github_get("/deployments?per_page=100")

    commit_dates = [
        parse_time(item["commit"]["committer"]["date"])
        for item in commits
        if item.get("commit", {}).get("committer", {}).get("date")
    ]
    observation_days = max(
        1,
        (datetime.now(timezone.utc) - min(commit_dates)).days if commit_dates else 1,
    )

    lead_times = []
    failed_deployments = 0
    recovery_times = []

    for deployment in deployments:
        sha = deployment.get("sha")
        created_at = deployment.get("created_at")
        if sha and created_at:
            commit = github_get(f"/commits/{sha}")
            committed_at = commit.get("commit", {}).get("committer", {}).get("date")
            if committed_at:
                lead_times.append(
                    (parse_time(created_at) - parse_time(committed_at)).total_seconds() / 3600
                )

        statuses = github_get(f"/deployments/{deployment['id']}/statuses?per_page=100")
        states = [status.get("state") for status in statuses]
        if any(state in {"failure", "error"} for state in states):
            failed_deployments += 1
            failure_times = [
                parse_time(status["created_at"])
                for status in statuses
                if status.get("state") in {"failure", "error"} and status.get("created_at")
            ]
            success_times = [
                parse_time(status["created_at"])
                for status in statuses
                if status.get("state") == "success" and status.get("created_at")
            ]
            if failure_times and success_times:
                failure = min(failure_times)
                later_successes = [value for value in success_times if value >= failure]
                if later_successes:
                    recovery_times.append(
                        (min(later_successes) - failure).total_seconds() / 3600
                    )

    deployment_count = len(deployments)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "observation_days": observation_days,
        "commit_count": len(commits),
        "deployment_frequency_per_month": round(
            deployment_count / observation_days * 30, 2
        ),
        "lead_time_hours": round(statistics.median(lead_times), 2)
        if lead_times
        else None,
        "change_failure_rate_percent": round(
            failed_deployments / deployment_count * 100, 1
        )
        if deployment_count
        else None,
        "mean_time_to_restore_hours": round(statistics.mean(recovery_times), 2)
        if recovery_times
        else None,
        "deployment_count": deployment_count,
        "failed_deployment_count": failed_deployments,
        "note": (
            "The repository has no deployment history, so lead time, change failure "
            "rate and recovery time cannot yet be classified."
            if not deployment_count
            else "Metrics are calculated from the available GitHub deployment history."
        ),
    }


def render_dashboard(metrics: dict, output: Path) -> None:
    labels = [
        "Deployment\nfrequency",
        "Lead time\nfor changes",
        "Change failure\nrate",
        "Mean time\nto restore",
    ]
    raw_values = [
        metrics["deployment_frequency_per_month"],
        metrics["lead_time_hours"],
        metrics["change_failure_rate_percent"],
        metrics["mean_time_to_restore_hours"],
    ]
    display_values = [
        f"{raw_values[0]} / month",
        f"{raw_values[1]} h" if raw_values[1] is not None else "No data",
        f"{raw_values[2]}%" if raw_values[2] is not None else "No data",
        f"{raw_values[3]} h" if raw_values[3] is not None else "No data",
    ]
    chart_values = [value if value is not None else 0 for value in raw_values]

    fig, ax = plt.subplots(figsize=(10, 4.8))
    colors = ["#73528f", "#9f86c0", "#be95c4", "#e0b1cb"]
    bars = ax.bar(labels, chart_values, color=colors, width=0.62)
    ax.set_title("Pelargonium Shop DORA baseline")
    ax.set_ylabel("Observed value")
    ax.grid(axis="y", alpha=0.2)
    for bar, label in zip(bars, display_values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max(chart_values + [1]) * 0.03,
            label,
            ha="center",
            va="bottom",
            fontweight="bold",
        )
    ax.text(
        0.01,
        -0.27,
        f"Real GitHub data: {metrics['commit_count']} commits, "
        f"{metrics['deployment_count']} deployments, "
        f"{metrics['observation_days']} observation days. "
        "Missing values mean that the repository has no corresponding events yet.",
        transform=ax.transAxes,
        fontsize=9,
    )
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="dist/dora_dashboard.png")
    parser.add_argument("--json", default="dist/dora_metrics.json")
    args = parser.parse_args()

    metrics = collect_metrics()
    json_path = Path(args.json)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    render_dashboard(metrics, Path(args.output))
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

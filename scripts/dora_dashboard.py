#!/usr/bin/env python3
"""Build a DORA dashboard from GitHub history and recorded manual releases."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch


DEFAULT_MANUAL_RELEASES = Path("docs/dora-manual-releases.json")


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


def load_manual_releases(path: Path) -> dict:
    if not path.exists():
        return {"manual_deployments": []}
    return json.loads(path.read_text(encoding="utf-8"))


def collect_metrics(manual_path: Path = DEFAULT_MANUAL_RELEASES) -> dict:
    commits = github_get("/commits?per_page=100")
    deployments = github_get("/deployments?per_page=100")
    manual_data = load_manual_releases(manual_path)
    manual_deployments = manual_data.get("manual_deployments", [])

    commit_dates = [
        parse_time(item["commit"]["committer"]["date"])
        for item in commits
        if item.get("commit", {}).get("committer", {}).get("date")
    ]

    window = manual_data.get("observation_window", {})
    if window.get("start") and window.get("end"):
        observation_days = max(
            1,
            (parse_time(window["end"]) - parse_time(window["start"])).days,
        )
    else:
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
                    (parse_time(created_at) - parse_time(committed_at)).total_seconds()
                    / 3600
                )

        statuses = github_get(
            f"/deployments/{deployment['id']}/statuses?per_page=100"
        )
        states = [status.get("state") for status in statuses]
        if any(state in {"failure", "error"} for state in states):
            failed_deployments += 1
            failure_times = [
                parse_time(status["created_at"])
                for status in statuses
                if status.get("state") in {"failure", "error"}
                and status.get("created_at")
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

    for deployment in manual_deployments:
        status = deployment.get("status", "").lower()
        if status in {"failure", "error"} or deployment.get("failed") is True:
            failed_deployments += 1

        started_at = deployment.get("started_at")
        deployed_at = deployment.get("deployed_at")
        if started_at and deployed_at and status == "success":
            lead_times.append(
                (parse_time(deployed_at) - parse_time(started_at)).total_seconds()
                / 3600
            )

        failed_at = deployment.get("failed_at")
        recovered_at = deployment.get("recovered_at")
        if failed_at and recovered_at:
            recovery_times.append(
                (parse_time(recovered_at) - parse_time(failed_at)).total_seconds()
                / 3600
            )

    github_deployment_count = len(deployments)
    manual_deployment_count = len(manual_deployments)
    deployment_count = github_deployment_count + manual_deployment_count

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
        "github_deployment_count": github_deployment_count,
        "manual_deployment_count": manual_deployment_count,
        "failed_deployment_count": failed_deployments,
        "source_note": (
            "GitHub API history combined with the versioned manual release log."
        ),
        "note": (
            "MTTR is not applicable because no production incidents and recoveries "
            "have been recorded."
            if not recovery_times
            else "All four metrics are calculated from recorded release events."
        ),
    }


def format_duration(hours: float | None) -> str:
    if hours is None:
        return "N/A"
    if hours >= 24:
        days = hours / 24
        return f"{days:.0f} days" if days.is_integer() else f"{days:.1f} days"
    return f"{hours:.1f} h"


def render_dashboard(metrics: dict, output: Path) -> None:
    release_count = metrics["deployment_count"]
    failed_count = metrics["failed_deployment_count"]
    cards = [
        (
            "Deployment Frequency",
            f"{metrics['deployment_frequency_per_month']} / month",
            f"{release_count} recorded release in\n{metrics['observation_days']} observation days",
        ),
        (
            "Lead Time for Changes",
            format_duration(metrics["lead_time_hours"]),
            f"Median across {release_count}\nrecorded release",
        ),
        (
            "Change Failure Rate",
            f"{metrics['change_failure_rate_percent']}%",
            f"{failed_count} failed releases out of\n{release_count} recorded release",
        ),
        (
            "Mean Time to Restore",
            format_duration(metrics["mean_time_to_restore_hours"]),
            "No production incidents\nor recovery events recorded",
        ),
    ]

    fig, ax = plt.subplots(figsize=(11, 4.4), dpi=220)
    fig.patch.set_facecolor("white")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4)
    ax.axis("off")

    positions = [(0.35, 2.15), (5.15, 2.15), (0.35, 0.15), (5.15, 0.15)]
    for (title, value, note), (x, y) in zip(cards, positions):
        box = FancyBboxPatch(
            (x, y),
            4.5,
            1.55,
            boxstyle="round,pad=0.04,rounding_size=0.12",
            linewidth=1.2,
            edgecolor="#6B4C7A",
            facecolor="#F4EFF7",
        )
        ax.add_patch(box)
        ax.text(
            x + 0.22,
            y + 1.22,
            title,
            fontsize=11,
            fontweight="bold",
            color="#4F365B",
            va="center",
        )
        ax.text(
            x + 0.22,
            y + 0.78,
            value,
            fontsize=17,
            fontweight="bold",
            color="#231A27",
            va="center",
        )
        ax.text(
            x + 2.55,
            y + 0.70,
            note,
            fontsize=8.8,
            color="#4A4A4A",
            va="center",
        )

    ax.text(
        0.35,
        3.88,
        "Pelargonium Shop DORA baseline",
        fontsize=14,
        fontweight="bold",
        color="#231A27",
    )
    ax.text(
        9.65,
        3.88,
        "GitHub history + manual Tilda release log",
        fontsize=8.8,
        color="#666666",
        ha="right",
    )
    ax.text(
        0.35,
        0.01,
        (
            f"Real data: {metrics['commit_count']} commits, "
            f"{metrics['github_deployment_count']} GitHub deployments, "
            f"{metrics['manual_deployment_count']} manual Tilda release."
        ),
        fontsize=8.4,
        color="#666666",
    )

    plt.tight_layout(pad=0.4)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="dist/dora_dashboard.png")
    parser.add_argument("--json", default="dist/dora_metrics.json")
    parser.add_argument(
        "--manual-releases",
        default=str(DEFAULT_MANUAL_RELEASES),
        help="Versioned JSON log for manual releases that are not in GitHub Deployments.",
    )
    args = parser.parse_args()

    metrics = collect_metrics(Path(args.manual_releases))
    json_path = Path(args.json)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    render_dashboard(metrics, Path(args.output))
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

"""
Shared utilities for all agents.
"""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------- #
# Logging
# ---------------------------------------------------------------------- #

def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )


# ---------------------------------------------------------------------- #
# Jira status constants
# ---------------------------------------------------------------------- #

class JiraStatus:
    BACKLOG               = "BACKLOG"
    READY_FOR_ARCH        = "READY_FOR_ARCH"
    IN_ARCH               = "IN_ARCH"
    READY_FOR_BACKEND     = "READY_FOR_BACKEND"
    IN_BACKEND            = "IN_BACKEND"
    READY_FOR_FRONTEND    = "READY_FOR_FRONTEND"
    IN_FRONTEND           = "IN_FRONTEND"
    READY_FOR_SECURITY    = "READY_FOR_SECURITY"
    IN_SECURITY           = "IN_SECURITY"
    READY_FOR_QA          = "READY_FOR_QA"
    IN_QA                 = "IN_QA"
    READY_FOR_ARCH_REVIEW = "READY_FOR_ARCH_REVIEW"
    IN_ARCH_REVIEW        = "IN_ARCH_REVIEW"
    APPROVED              = "APPROVED"
    NEEDS_REVISION        = "NEEDS_REVISION"
    HLP_IN_PROGRESS       = "IN_PROGRESS"
    HLP_COMPLETE          = "DONE"


# ---------------------------------------------------------------------- #
# Agent output
# ---------------------------------------------------------------------- #

OUTPUT_FILE = "agent_output.json"


@dataclass
class AgentOutput:
    status: str                          # "complete" | "failed" | "approve" | "reject" | "skip"
    comment: str                         # Posted to Jira
    next_jira_status: Optional[str] = None
    findings: list = None                # Security / QA findings
    documents_created: list = None       # Paths of docs written

    def __post_init__(self):
        if self.findings is None:
            self.findings = []
        if self.documents_created is None:
            self.documents_created = []


def read_agent_output(repo_dir: Path) -> Optional[AgentOutput]:
    path = repo_dir / OUTPUT_FILE
    if not path.exists():
        log.warning(f"{OUTPUT_FILE} not found in {repo_dir}")
        return None
    with open(path) as f:
        data = json.load(f)
    return AgentOutput(**data)


def write_agent_output(repo_dir: Path, output: AgentOutput) -> None:
    path = repo_dir / OUTPUT_FILE
    with open(path, "w") as f:
        json.dump(asdict(output), f, indent=2)


# ---------------------------------------------------------------------- #
# Git helpers
# ---------------------------------------------------------------------- #

def run_git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    cmd = ["git"] + args
    log.info(f"git {' '.join(args)} (cwd={cwd})")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(f"git {args[0]} failed:\n{result.stderr}")
    return result


def clone_repo(clone_url: str, branch: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        # If already cloned, fetch and checkout
        run_git(["fetch", "origin"], cwd=dest)
        run_git(["checkout", branch], cwd=dest)
        run_git(["pull", "origin", branch], cwd=dest)
    else:
        run_git(["clone", "--branch", branch, clone_url, str(dest)], cwd=dest.parent)
    log.info(f"Repo ready at {dest} on branch {branch}")


def commit_and_push(repo_dir: Path, branch: str, message: str) -> bool:
    """Stage all changes, commit, and push. Returns True if anything was committed."""
    status = run_git(["status", "--porcelain"], cwd=repo_dir, check=False)
    if not status.stdout.strip():
        log.info("No changes to commit.")
        return False
    run_git(["add", "-A"], cwd=repo_dir)
    run_git(["commit", "-m", message], cwd=repo_dir)
    run_git(["push", "origin", branch], cwd=repo_dir)
    log.info(f"Pushed changes to origin/{branch}")
    return True


# ---------------------------------------------------------------------- #
# Claude CLI runner
# ---------------------------------------------------------------------- #

def run_claude(prompt: str, repo_dir: Path, timeout: int = 1800) -> str:
    """
    Invoke the Claude Code CLI non-interactively with full tool access.
    Returns combined stdout. The agent should write agent_output.json to
    repo_dir before exiting.
    """
    env = {**os.environ, "ANTHROPIC_API_KEY": os.environ["ANTHROPIC_API_KEY"]}
    result = subprocess.run(
        ["claude", "--dangerously-skip-permissions", "-p", prompt],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )
    if result.stdout:
        log.info(f"Claude stdout:\n{result.stdout[:2000]}")
    if result.stderr:
        log.warning(f"Claude stderr:\n{result.stderr[:1000]}")
    if result.returncode != 0:
        log.error(f"Claude exited with code {result.returncode}")
    return result.stdout


# ---------------------------------------------------------------------- #
# Issue context builder
# ---------------------------------------------------------------------- #

def build_issue_context(issue: dict) -> str:
    """Format a Jira issue dict into a human-readable context block."""
    fields = issue.get("fields", {})
    key = issue.get("key", "")
    summary = fields.get("summary", "")
    issue_type = fields.get("issuetype", {}).get("name", "")
    priority = fields.get("priority", {}).get("name", "")
    description_raw = fields.get("description", {})

    # Extract plain text from Atlassian Document Format
    description = _extract_adf_text(description_raw)

    labels = ", ".join(fields.get("labels", [])) or "none"
    comments = []
    comment_list = fields.get("comment", {}).get("comments", [])
    for c in comment_list[-5:]:  # last 5 comments
        author = c.get("author", {}).get("displayName", "unknown")
        body_text = _extract_adf_text(c.get("body", {}))
        comments.append(f"  [{author}]: {body_text}")

    context = f"""
=== JIRA ISSUE CONTEXT ===
Key:         {key}
Type:        {issue_type}
Priority:    {priority}
Summary:     {summary}
Labels:      {labels}

Description:
{description}

Recent Comments:
{chr(10).join(comments) if comments else '  (none)'}
=========================
""".strip()
    return context


def _extract_adf_text(adf: dict | None) -> str:
    """Recursively extract plain text from Atlassian Document Format."""
    if not adf or not isinstance(adf, dict):
        return ""
    if adf.get("type") == "text":
        return adf.get("text", "")
    parts = []
    for child in adf.get("content", []):
        parts.append(_extract_adf_text(child))
    return "\n".join(p for p in parts if p)

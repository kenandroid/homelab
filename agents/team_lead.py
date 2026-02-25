"""
Team Lead Agent — runs daily.
Picks up HLP stories from BACKLOG, creates feature branches,
and kicks off the pipeline by transitioning to READY_FOR_ARCH
(or READY_FOR_BACKEND for simple bugs).
"""

import logging
import os
import re
import sys
from pathlib import Path

from jira_client import JiraClient
from gitea_client import GiteaClient
from utils import JiraStatus, configure_logging

log = logging.getLogger(__name__)

HLP_PROJECT = os.environ.get("HLP_PROJECT_KEY", "HLP")

# Custom field IDs — set these after creating fields in Jira
# e.g. JIRA_FIELD_TARGET_PROJECT_KEY=customfield_10200
TARGET_PROJECT_FIELD = os.environ.get("JIRA_FIELD_TARGET_PROJECT_KEY", "")
REPO_NAME_FIELD = os.environ.get("JIRA_FIELD_REPO_NAME", "")

# Fallback: map Jira project key -> Gitea repo name
PROJECT_REPO_MAP: dict[str, str] = {}  # populated from env: PROJECT_REPO_MAP_XYZ=myrepo


def _load_project_repo_map() -> dict[str, str]:
    mapping = {}
    for key, value in os.environ.items():
        if key.startswith("PROJECT_REPO_MAP_"):
            project_key = key[len("PROJECT_REPO_MAP_"):]
            mapping[project_key] = value
    return mapping


def _slugify(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).lower().strip("-")
    return slug[:max_len]


def _is_simple_bug(issue: dict) -> bool:
    """
    Simple bug = Bug issue type with no 'complex' or 'design' label
    and a short description.
    """
    fields = issue.get("fields", {})
    issue_type = fields.get("issuetype", {}).get("name", "").lower()
    if issue_type != "bug":
        return False
    labels = [l.lower() for l in fields.get("labels", [])]
    if "complex" in labels or "design-required" in labels:
        return False
    return True


class TeamLeadAgent:
    def __init__(self):
        configure_logging()
        self.jira = JiraClient()
        self.gitea = GiteaClient()
        self.project_repo_map = _load_project_repo_map()

    def run(self) -> None:
        log.info(f"Team Lead polling {HLP_PROJECT} for BACKLOG stories")
        issues = self.jira.search_issues(
            jql=f'project = "{HLP_PROJECT}" AND status = "BACKLOG" ORDER BY created ASC',
            max_results=1,
        )
        if not issues:
            log.info("No backlog stories found. Done.")
            return

        issue = issues[0]
        issue_key = issue["key"]
        fields = issue["fields"]
        summary = fields.get("summary", "")
        log.info(f"Processing {issue_key}: {summary}")

        # Read target project key from custom field
        target_project = ""
        if TARGET_PROJECT_FIELD:
            target_project = (fields.get(TARGET_PROJECT_FIELD) or "").strip()
        if not target_project:
            # Try labels: label "project:XYZ"
            for label in fields.get("labels", []):
                if label.lower().startswith("project:"):
                    target_project = label.split(":")[1].strip()
                    break
        if not target_project:
            self.jira.add_comment(
                issue_key,
                "[TEAM LEAD] Cannot find target project key. "
                "Please set the 'Target Project Key' custom field or add a label 'project:PROJECTKEY'.",
            )
            log.error(f"No target project key found for {issue_key}")
            return

        # Resolve Gitea repo name
        repo_name = ""
        if REPO_NAME_FIELD:
            repo_name = (fields.get(REPO_NAME_FIELD) or "").strip()
        if not repo_name:
            repo_name = self.project_repo_map.get(target_project, "")
        if not repo_name:
            self.jira.add_comment(
                issue_key,
                f"[TEAM LEAD] Cannot find Gitea repo for project '{target_project}'. "
                f"Set env var PROJECT_REPO_MAP_{target_project}=<repo-name> on the runner.",
            )
            log.error(f"No repo mapping for project {target_project}")
            return

        # Create feature branch
        branch_name = f"feature/{issue_key}-{_slugify(summary)}"
        default_branch = self.gitea.get_default_branch(repo_name)
        self.gitea.create_branch(repo_name, branch_name, from_branch=default_branch)

        # Annotate all sub-project BACKLOG issues with repo + branch labels
        sub_issues = self.jira.search_issues(
            jql=f'project = "{target_project}" AND status = "BACKLOG" ORDER BY created ASC',
            max_results=50,
        )
        for sub in sub_issues:
            self.jira.add_label(sub["key"], f"repo:{repo_name}")
            self.jira.add_label(sub["key"], f"branch:{branch_name}")
            self.jira.add_label(sub["key"], f"hlp:{issue_key}")

        # Determine pipeline entry point
        is_bug = _is_simple_bug(issue)
        first_status = JiraStatus.READY_FOR_BACKEND if is_bug else JiraStatus.READY_FOR_ARCH

        # Transition HLP story to IN_PROGRESS
        self.jira.transition_issue(issue_key, JiraStatus.HLP_IN_PROGRESS)

        # Transition the primary sub-project issue (first one) to kick off pipeline
        # The solutions architect (or backend) picks up from there
        if sub_issues:
            primary = sub_issues[0]["key"]
            self.jira.transition_issue(primary, first_status)
            self.jira.add_comment(
                primary,
                f"[TEAM LEAD] Feature branch created: `{branch_name}` in repo `{repo_name}`.\n"
                f"HLP story: {issue_key}\n"
                f"Pipeline starting at: {first_status}",
            )
        else:
            # No sub-tickets: create a placeholder and transition it
            new_issue = self.jira.create_issue(
                project_key=target_project,
                summary=summary,
                description=(
                    f"Auto-created by Team Lead from HLP story {issue_key}.\n\n"
                    + _extract_description(issue)
                ),
                issue_type="Story",
                extra_fields={
                    "labels": [f"repo:{repo_name}", f"branch:{branch_name}", f"hlp:{issue_key}"],
                },
            )
            new_key = new_issue["key"]
            self.jira.transition_issue(new_key, first_status)
            self.jira.add_comment(
                issue_key,
                f"[TEAM LEAD] Created tracking ticket {new_key} in project {target_project}.\n"
                f"Feature branch: `{branch_name}` in repo `{repo_name}`.",
            )

        log.info(
            f"Team Lead complete. Branch={branch_name}, "
            f"Repo={repo_name}, Pipeline starts at {first_status}"
        )


def _extract_description(issue: dict) -> str:
    from utils import _extract_adf_text
    return _extract_adf_text(issue.get("fields", {}).get("description", {}))


if __name__ == "__main__":
    TeamLeadAgent().run()

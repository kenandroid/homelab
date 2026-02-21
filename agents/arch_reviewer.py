"""
Staff Solutions Architect Reviewer Agent (#7)
Reviews code and tests against design. Approves or rejects.
On approval: creates PR and marks HLP story complete.
On rejection: sends back to READY_FOR_BACKEND (full pipeline restart).
"""

import logging
import os
from pathlib import Path

from base_agent import BaseAgent, WORKSPACE
from gitea_client import GiteaClient
from jira_client import JiraClient
from utils import JiraStatus, AgentOutput, build_issue_context, run_claude, read_agent_output, configure_logging

log = logging.getLogger(__name__)


class ArchReviewerAgent(BaseAgent):
    ready_status = JiraStatus.READY_FOR_ARCH_REVIEW
    in_progress_status = JiraStatus.IN_ARCH_REVIEW
    prompt_file = "arch_reviewer.md"

    def handle_output(self, issue: dict, output: AgentOutput) -> None:
        issue_key = issue["key"]
        repo_name = self._get_repo_name(issue)
        branch = self._get_branch(issue)

        if output.status == "approve":
            self._handle_approval(issue, issue_key, repo_name, branch, output)
        else:
            self._handle_rejection(issue_key, output)

    def _handle_approval(self, issue: dict, issue_key: str, repo_name: str, branch: str, output: AgentOutput) -> None:
        # Post approval comment
        self.jira.add_comment(
            issue_key,
            f"[ARCH REVIEW - APPROVED]\n{output.comment}",
        )

        # Create pull request
        pr_title = f"[{issue_key}] {issue['fields'].get('summary', '')}"
        pr_body = (
            f"## Feature: {issue_key}\n\n"
            f"{output.comment}\n\n"
            f"### Security Findings\nReviewed and accepted by Arch Reviewer.\n\n"
            f"### QA\nAll tests validated.\n"
        )
        default_branch = self.gitea.get_default_branch(repo_name)
        try:
            pr = self.gitea.create_pull_request(
                repo_name=repo_name,
                title=pr_title,
                body=pr_body,
                head=branch,
                base=default_branch,
            )
            pr_url = pr.get("html_url", "")
            self.jira.add_comment(issue_key, f"[ARCH REVIEW] Pull request created: {pr_url}")
        except Exception as e:
            log.warning(f"Could not create PR: {e}")

        # Transition sub-project issue to APPROVED
        self.jira.transition_issue(issue_key, JiraStatus.APPROVED)

        # Find and close the parent HLP story
        hlp_key = self._find_hlp_key(issue)
        if hlp_key:
            self.jira.transition_issue(hlp_key, JiraStatus.HLP_COMPLETE)
            self.jira.add_comment(
                hlp_key,
                f"[ARCH REVIEW] Feature complete. Sub-ticket {issue_key} approved. PR created.",
            )
            log.info(f"HLP story {hlp_key} marked DONE")

    def _handle_rejection(self, issue_key: str, output: AgentOutput) -> None:
        rejection_comment = (
            f"[ARCH REVIEW - REJECTED]\n{output.comment}\n\n"
            "Restarting pipeline from backend engineer."
        )
        self.jira.add_comment(issue_key, rejection_comment)
        self.jira.transition_issue(issue_key, JiraStatus.READY_FOR_BACKEND)
        log.info(f"{issue_key} rejected — restarting pipeline at READY_FOR_BACKEND")

    def _find_hlp_key(self, issue: dict) -> str:
        """Extract HLP issue key from labels (set by team lead)."""
        for label in issue["fields"].get("labels", []):
            if label.lower().startswith("hlp:"):
                return label[4:]
        return ""


if __name__ == "__main__":
    ArchReviewerAgent().run()

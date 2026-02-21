"""
Base class for all agents that poll Jira and invoke Claude Code.
"""

import logging
import os
from pathlib import Path

from jira_client import JiraClient
from gitea_client import GiteaClient
from utils import (
    JiraStatus, AgentOutput, build_issue_context,
    clone_repo, commit_and_push, run_claude,
    read_agent_output, configure_logging,
)

log = logging.getLogger(__name__)

WORKSPACE = Path(os.environ.get("AGENT_WORKSPACE", "/tmp/agent-workspace"))


class BaseAgent:
    """
    Subclass this and implement `ready_status`, `in_progress_status`,
    `prompt_file`, and optionally `handle_output`.
    """

    ready_status: str = NotImplemented       # Jira status this agent watches for
    in_progress_status: str = NotImplemented # Jira status set while working
    prompt_file: str = NotImplemented        # Filename under agents/prompts/

    def __init__(self):
        configure_logging()
        self.jira = JiraClient()
        self.gitea = GiteaClient()
        self.prompts_dir = Path(__file__).parent / "prompts"

    # ------------------------------------------------------------------ #
    # Main entry point
    # ------------------------------------------------------------------ #

    def run(self) -> None:
        log.info(f"{self.__class__.__name__} polling for status={self.ready_status}")
        issues = self._find_ready_issues()
        if not issues:
            log.info("No issues ready. Exiting.")
            return

        issue = issues[0]  # one at a time
        issue_key = issue["key"]
        log.info(f"Picked up {issue_key}: {issue['fields'].get('summary', '')}")

        # Mark as in-progress immediately to prevent double-pickup
        self.jira.transition_issue(issue_key, self.in_progress_status)

        try:
            repo_dir = self._prepare_workspace(issue)
            output = self._invoke_claude(issue, repo_dir)
            self._finalize(issue, repo_dir, output)
        except Exception as e:
            log.exception(f"Agent failed on {issue_key}: {e}")
            self.jira.add_comment(
                issue_key,
                f"[AGENT ERROR] {self.__class__.__name__} encountered an error: {e}\n"
                "Manual intervention required.",
            )
            # Leave in in_progress status — ops team can investigate

    # ------------------------------------------------------------------ #
    # Overridable methods
    # ------------------------------------------------------------------ #

    def _find_ready_issues(self) -> list[dict]:
        """Return Jira issues this agent should handle."""
        jql = (
            f'status = "{self.ready_status}" '
            f'ORDER BY created ASC'
        )
        return self.jira.search_issues(jql, max_results=1)

    def _get_repo_name(self, issue: dict) -> str:
        """Derive the Gitea repo name from the issue. Override if needed."""
        # Stored in label "repo:<name>" or env fallback
        for label in issue["fields"].get("labels", []):
            if label.startswith("repo:"):
                return label[len("repo:"):]
        return os.environ.get("DEFAULT_REPO", "")

    def _get_branch(self, issue: dict) -> str:
        """Derive the feature branch name from the issue."""
        for label in issue["fields"].get("labels", []):
            if label.startswith("branch:"):
                return label[len("branch:"):]
        return ""

    def _build_prompt(self, issue: dict, repo_dir: Path) -> str:
        """Build the full prompt for Claude Code. Subclasses may override."""
        template = (self.prompts_dir / self.prompt_file).read_text()
        context = build_issue_context(issue)
        branch = self._get_branch(issue)
        return f"{template}\n\n{context}\n\nFeature branch: {branch}\nRepo dir: {repo_dir}\n"

    def handle_output(self, issue: dict, output: AgentOutput) -> None:
        """
        Default post-Claude handler: post comment + transition to next status.
        Subclasses override for custom logic (e.g., arch reviewer approve/reject).
        """
        issue_key = issue["key"]
        if output.comment:
            self.jira.add_comment(issue_key, output.comment)
        if output.next_jira_status:
            self.jira.transition_issue(issue_key, output.next_jira_status)
        else:
            log.warning(f"No next_jira_status in agent_output for {issue_key}")

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _prepare_workspace(self, issue: dict) -> Path:
        repo_name = self._get_repo_name(issue)
        branch = self._get_branch(issue)
        if not repo_name or not branch:
            raise ValueError(
                f"Issue {issue['key']} is missing repo or branch labels. "
                f"Labels: {issue['fields'].get('labels', [])}"
            )
        clone_url = self.gitea.clone_url(repo_name)
        dest = WORKSPACE / repo_name
        clone_repo(clone_url, branch, dest)
        return dest

    def _invoke_claude(self, issue: dict, repo_dir: Path) -> AgentOutput:
        prompt = self._build_prompt(issue, repo_dir)
        run_claude(prompt, repo_dir)
        output = read_agent_output(repo_dir)
        if output is None:
            raise RuntimeError(
                f"Claude did not write {repo_dir}/agent_output.json"
            )
        return output

    def _finalize(self, issue: dict, repo_dir: Path, output: AgentOutput) -> None:
        issue_key = issue["key"]
        branch = self._get_branch(issue)

        # Commit any files Claude changed
        commit_and_push(
            repo_dir,
            branch,
            f"[{self.__class__.__name__}] {issue_key}: {output.comment[:72]}",
        )

        self.handle_output(issue, output)
        log.info(f"Done with {issue_key}. Status -> {output.next_jira_status}")

"""
Solutions Architect Agent (#2)
Picks up READY_FOR_ARCH issues, creates architecture and workflow docs,
then hands off to backend. Simple bugs skip straight through.
"""

import logging
from pathlib import Path

from base_agent import BaseAgent
from utils import JiraStatus, AgentOutput

log = logging.getLogger(__name__)


class SolutionsArchitectAgent(BaseAgent):
    ready_status = JiraStatus.READY_FOR_ARCH
    in_progress_status = JiraStatus.IN_ARCH
    prompt_file = "solutions_architect.md"

    def _build_prompt(self, issue: dict, repo_dir: Path) -> str:
        template = (self.prompts_dir / self.prompt_file).read_text()
        from utils import build_issue_context
        context = build_issue_context(issue)
        branch = self._get_branch(issue)
        issue_type = issue["fields"].get("issuetype", {}).get("name", "").lower()
        labels = [l.lower() for l in issue["fields"].get("labels", [])]
        is_complex_bug = issue_type == "bug" and ("complex" in labels or "design-required" in labels)
        needs_design = issue_type != "bug" or is_complex_bug
        return (
            f"{template}\n\n"
            f"{context}\n\n"
            f"Feature branch: {branch}\n"
            f"Repo dir: {repo_dir}\n"
            f"NEEDS_DESIGN_DOCS: {'yes' if needs_design else 'no'}\n"
        )

    def handle_output(self, issue: dict, output: AgentOutput) -> None:
        issue_key = issue["key"]
        if output.comment:
            self.jira.add_comment(issue_key, output.comment)
        next_status = output.next_jira_status or JiraStatus.READY_FOR_BACKEND
        self.jira.transition_issue(issue_key, next_status)


if __name__ == "__main__":
    SolutionsArchitectAgent().run()

"""
Principal Security Engineer Agent
Reviews all code on the feature branch for security flaws.
Documents findings in Jira and agent_output.json.
"""

import logging
from base_agent import BaseAgent
from utils import JiraStatus, AgentOutput

log = logging.getLogger(__name__)


class SecurityEngineerAgent(BaseAgent):
    ready_status = JiraStatus.READY_FOR_SECURITY
    in_progress_status = JiraStatus.IN_SECURITY
    prompt_file = "security_engineer.md"

    def handle_output(self, issue: dict, output: AgentOutput) -> None:
        issue_key = issue["key"]

        # Always post findings as a comment even if empty
        findings_text = "\n".join(f"- {f}" for f in output.findings) if output.findings else "No findings."
        self.jira.add_comment(
            issue_key,
            f"[SECURITY REVIEW]\n{output.comment}\n\nFindings:\n{findings_text}",
        )

        next_status = output.next_jira_status or JiraStatus.READY_FOR_QA
        self.jira.transition_issue(issue_key, next_status)


if __name__ == "__main__":
    SecurityEngineerAgent().run()

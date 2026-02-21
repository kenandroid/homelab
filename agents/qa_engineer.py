"""
Principal QA Engineer Agent
Validates tests exist and pass. Creates skeletons for missing tests.
Documents failures with insight.
"""

import logging
from base_agent import BaseAgent
from utils import JiraStatus, AgentOutput

log = logging.getLogger(__name__)


class QAEngineerAgent(BaseAgent):
    ready_status = JiraStatus.READY_FOR_QA
    in_progress_status = JiraStatus.IN_QA
    prompt_file = "qa_engineer.md"

    def handle_output(self, issue: dict, output: AgentOutput) -> None:
        issue_key = issue["key"]

        findings_text = "\n".join(f"- {f}" for f in output.findings) if output.findings else "All tests passed."
        self.jira.add_comment(
            issue_key,
            f"[QA REVIEW]\n{output.comment}\n\nTest Results:\n{findings_text}",
        )

        next_status = output.next_jira_status or JiraStatus.READY_FOR_ARCH_REVIEW
        self.jira.transition_issue(issue_key, next_status)


if __name__ == "__main__":
    QAEngineerAgent().run()

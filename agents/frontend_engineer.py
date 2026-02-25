"""
Principal Frontend Engineer Agent
Picks up READY_FOR_FRONTEND issues, writes UI code and unit tests.
"""

import logging
from base_agent import BaseAgent
from utils import JiraStatus

log = logging.getLogger(__name__)


class FrontendEngineerAgent(BaseAgent):
    ready_status = JiraStatus.READY_FOR_FRONTEND
    in_progress_status = JiraStatus.IN_FRONTEND
    prompt_file = "frontend_engineer.md"


if __name__ == "__main__":
    FrontendEngineerAgent().run()

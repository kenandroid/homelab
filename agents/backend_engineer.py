"""
Principal Backend Engineer Agent
Picks up READY_FOR_BACKEND issues, writes Python backend code and unit tests.
"""

import logging
from base_agent import BaseAgent
from utils import JiraStatus

log = logging.getLogger(__name__)


class BackendEngineerAgent(BaseAgent):
    ready_status = JiraStatus.READY_FOR_BACKEND
    in_progress_status = JiraStatus.IN_BACKEND
    prompt_file = "backend_engineer.md"


if __name__ == "__main__":
    BackendEngineerAgent().run()

"""
Gitea REST API client.
Requires env vars: GITEA_BASE_URL, GITEA_TOKEN, GITEA_ORG
"""

import os
import logging
import requests
from typing import Optional

log = logging.getLogger(__name__)


class GiteaClient:
    def __init__(self):
        self.base_url = os.environ["GITEA_BASE_URL"].rstrip("/")
        self.token = os.environ["GITEA_TOKEN"]
        self.org = os.environ["GITEA_ORG"]
        self.headers = {
            "Authorization": f"token {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _get(self, path: str, params: dict = None) -> dict | list:
        url = f"{self.base_url}/api/v1{path}"
        resp = requests.get(url, headers=self.headers, params=params)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, body: dict) -> dict:
        url = f"{self.base_url}/api/v1{path}"
        resp = requests.post(url, headers=self.headers, json=body)
        resp.raise_for_status()
        return resp.json() if resp.text else {}

    def _delete(self, path: str) -> None:
        url = f"{self.base_url}/api/v1{path}"
        resp = requests.delete(url, headers=self.headers)
        resp.raise_for_status()

    # ------------------------------------------------------------------ #
    # Repositories
    # ------------------------------------------------------------------ #

    def get_repo(self, repo_name: str) -> dict:
        return self._get(f"/repos/{self.org}/{repo_name}")

    def list_org_repos(self) -> list[dict]:
        return self._get(f"/orgs/{self.org}/repos")

    # ------------------------------------------------------------------ #
    # Branches
    # ------------------------------------------------------------------ #

    def branch_exists(self, repo_name: str, branch: str) -> bool:
        try:
            self._get(f"/repos/{self.org}/{repo_name}/branches/{branch}")
            return True
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                return False
            raise

    def create_branch(self, repo_name: str, branch: str, from_branch: str = "main") -> dict:
        if self.branch_exists(repo_name, branch):
            log.info(f"Branch {branch} already exists in {repo_name}")
            return {}
        body = {"new_branch_name": branch, "old_branch_name": from_branch}
        result = self._post(f"/repos/{self.org}/{repo_name}/branches", body)
        log.info(f"Created branch {branch} in {repo_name} from {from_branch}")
        return result

    def get_default_branch(self, repo_name: str) -> str:
        repo = self.get_repo(repo_name)
        return repo.get("default_branch", "main")

    # ------------------------------------------------------------------ #
    # Pull Requests
    # ------------------------------------------------------------------ #

    def create_pull_request(
        self,
        repo_name: str,
        title: str,
        body: str,
        head: str,
        base: str = "main",
    ) -> dict:
        payload = {
            "title": title,
            "body": body,
            "head": head,
            "base": base,
        }
        result = self._post(f"/repos/{self.org}/{repo_name}/pulls", payload)
        log.info(f"Created PR #{result.get('number')} in {repo_name}: {title}")
        return result

    def merge_pull_request(self, repo_name: str, pr_index: int, merge_style: str = "squash") -> None:
        self._post(
            f"/repos/{self.org}/{repo_name}/pulls/{pr_index}/merge",
            {"Do": merge_style, "delete_branch_after_merge": True},
        )
        log.info(f"Merged PR #{pr_index} in {repo_name}")

    # ------------------------------------------------------------------ #
    # Clone URL helper
    # ------------------------------------------------------------------ #

    def clone_url(self, repo_name: str) -> str:
        """Return an authenticated clone URL for use in CI."""
        # Strip protocol and reconstruct with token
        base = self.base_url.replace("https://", "").replace("http://", "")
        protocol = "https" if self.base_url.startswith("https") else "http"
        return f"{protocol}://{self.org}:{self.token}@{base}/{self.org}/{repo_name}.git"

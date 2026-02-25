"""
Jira Cloud REST API v3 client.
Requires env vars: JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN
"""

import os
import logging
import requests
from requests.auth import HTTPBasicAuth
from typing import Optional

log = logging.getLogger(__name__)


class JiraClient:
    def __init__(self):
        self.base_url = os.environ["JIRA_BASE_URL"].rstrip("/")
        self.auth = HTTPBasicAuth(
            os.environ["JIRA_EMAIL"],
            os.environ["JIRA_API_TOKEN"],
        )
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _get(self, path: str, params: dict = None) -> dict:
        url = f"{self.base_url}/rest/api/3{path}"
        resp = requests.get(url, auth=self.auth, headers=self.headers, params=params)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, body: dict) -> dict:
        url = f"{self.base_url}/rest/api/3{path}"
        resp = requests.post(url, auth=self.auth, headers=self.headers, json=body)
        resp.raise_for_status()
        return resp.json() if resp.text else {}

    def _put(self, path: str, body: dict) -> None:
        url = f"{self.base_url}/rest/api/3{path}"
        resp = requests.put(url, auth=self.auth, headers=self.headers, json=body)
        resp.raise_for_status()

    # ------------------------------------------------------------------ #
    # Issues
    # ------------------------------------------------------------------ #

    def search_issues(self, jql: str, fields: list[str] = None, max_results: int = 50) -> list[dict]:
        params = {
            "jql": jql,
            "maxResults": max_results,
            "fields": ",".join(fields) if fields else "*all",
        }
        data = self._get("/search", params=params)
        return data.get("issues", [])

    def get_issue(self, issue_key: str) -> dict:
        return self._get(f"/issue/{issue_key}")

    def create_issue(self, project_key: str, summary: str, description: str,
                     issue_type: str = "Story", extra_fields: dict = None) -> dict:
        body = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": description}],
                        }
                    ],
                },
                "issuetype": {"name": issue_type},
            }
        }
        if extra_fields:
            body["fields"].update(extra_fields)
        return self._post("/issue", body)

    def update_issue(self, issue_key: str, fields: dict) -> None:
        self._put(f"/issue/{issue_key}", {"fields": fields})

    # ------------------------------------------------------------------ #
    # Transitions / status
    # ------------------------------------------------------------------ #

    def get_transitions(self, issue_key: str) -> list[dict]:
        data = self._get(f"/issue/{issue_key}/transitions")
        return data.get("transitions", [])

    def transition_issue(self, issue_key: str, status_name: str) -> None:
        """Transition issue to the given status name (case-insensitive match)."""
        transitions = self.get_transitions(issue_key)
        match = next(
            (t for t in transitions if t["to"]["name"].upper() == status_name.upper()),
            None,
        )
        if not match:
            available = [t["to"]["name"] for t in transitions]
            raise ValueError(
                f"Transition to '{status_name}' not found for {issue_key}. "
                f"Available: {available}"
            )
        self._post(f"/issue/{issue_key}/transitions", {"transition": {"id": match["id"]}})
        log.info(f"Transitioned {issue_key} -> {status_name}")

    # ------------------------------------------------------------------ #
    # Comments
    # ------------------------------------------------------------------ #

    def add_comment(self, issue_key: str, text: str) -> dict:
        body = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": text}],
                    }
                ],
            }
        }
        return self._post(f"/issue/{issue_key}/comment", body)

    # ------------------------------------------------------------------ #
    # Custom field helpers
    # ------------------------------------------------------------------ #

    def get_custom_field(self, issue: dict, field_name: str) -> Optional[str]:
        """
        Look up a custom field by name across all fields on an issue.
        field_name is the human-readable name (e.g. 'Target Project Key').
        Returns the raw string value or None.
        """
        fields = issue.get("fields", {})
        for key, value in fields.items():
            if key.startswith("customfield_") and isinstance(value, str):
                # We match by checking the field ID mapping below
                pass
        # Direct lookup via known env-var-configured field IDs
        env_key = f"JIRA_FIELD_{field_name.upper().replace(' ', '_')}"
        field_id = os.environ.get(env_key)
        if field_id and field_id in fields:
            return fields[field_id]
        return None

    def set_custom_field(self, issue_key: str, field_id: str, value: str) -> None:
        self._put(f"/issue/{issue_key}", {"fields": {field_id: value}})

    # ------------------------------------------------------------------ #
    # Labels
    # ------------------------------------------------------------------ #

    def add_label(self, issue_key: str, label: str) -> None:
        issue = self.get_issue(issue_key)
        labels = issue["fields"].get("labels", [])
        if label not in labels:
            labels.append(label)
            self.update_issue(issue_key, {"labels": labels})

# Homelab AI Agent Team

An automated software development team that picks up Jira stories and carries them through a full pipeline — architecture, backend, frontend, security review, QA, and final approval — using Claude Code agents running on Gitea CI runners.

---

## Pipeline

```
HLP BACKLOG story
       │
       ▼ (Team Lead — daily 10 PM ET)
READY_FOR_ARCH ──► IN_ARCH
       │
       ▼ (Solutions Architect — every 30 min)
READY_FOR_BACKEND ──► IN_BACKEND
       │
       ▼ (Backend Engineer — every 30 min)
READY_FOR_FRONTEND ──► IN_FRONTEND
       │
       ▼ (Frontend Engineer — every 30 min)
READY_FOR_SECURITY ──► IN_SECURITY
       │
       ▼ (Security Engineer — every 30 min)
READY_FOR_QA ──► IN_QA
       │
       ▼ (QA Engineer — every 30 min)
READY_FOR_ARCH_REVIEW ──► IN_ARCH_REVIEW
       │
    ┌──┴──┐
APPROVED   NEEDS_REVISION ──► READY_FOR_BACKEND (full restart)
    │
    ▼
PR created, HLP story → DONE
```

Simple bugs (type=Bug, no `complex`/`design-required` label) skip straight to `READY_FOR_BACKEND`.

---

## One-Time Setup

### 1. Jira — Create Custom Workflow

In your Jira project(s), create a custom workflow with these statuses:

```
BACKLOG, READY_FOR_ARCH, IN_ARCH, READY_FOR_BACKEND, IN_BACKEND,
READY_FOR_FRONTEND, IN_FRONTEND, READY_FOR_SECURITY, IN_SECURITY,
READY_FOR_QA, IN_QA, READY_FOR_ARCH_REVIEW, IN_ARCH_REVIEW,
APPROVED, NEEDS_REVISION
```

For the **HLP** project add statuses: `BACKLOG`, `IN_PROGRESS`, `DONE`.

### 2. Jira — Create Custom Fields

In Jira: **Settings → Issues → Custom Fields → Create Field**

| Field Name | Type | Used On |
|------------|------|---------|
| Target Project Key | Text Field (single line) | HLP Stories |
| Repo Name | Text Field (single line) | HLP Stories (optional) |

After creating them, find their IDs:
- Go to **Jira Settings → Issues → Custom Fields**
- Click the field → **View field information**
- The ID is in the URL: `customfield_XXXXX`

### 3. Atlassian API Token

1. Go to: https://id.atlassian.com/manage-profile/security/api-tokens
2. Click **Create API token**
3. Give it a name (e.g. `homelab-agents`)
4. Copy the token — you will not see it again

### 4. Anthropic API Key

1. Go to: https://console.anthropic.com/account/keys
2. Create a new key
3. Copy it

### 5. Gitea Personal Access Token

1. In your Gitea instance: **User Settings → Applications → Generate Token**
2. Scopes needed: `repo` (read/write), `issue` (if you use Gitea Issues)
3. Copy the token

### 6. Claude CLI — Install on Runners

Each Gitea runner machine needs the Claude CLI installed:

```bash
npm install -g @anthropic-ai/claude-code
```

Verify: `claude --version`

The workflows install it automatically via `npm install -g` each run, but pre-installing on the runner image speeds things up.

### 7. Add Gitea Repository Secrets

In this repo on Gitea: **Settings → Secrets → Add Secret**

| Secret Name | Value |
|-------------|-------|
| `JIRA_BASE_URL` | `https://your-org.atlassian.net` |
| `JIRA_EMAIL` | Your Atlassian account email |
| `JIRA_API_TOKEN` | Token from step 3 |
| `JIRA_FIELD_TARGET_PROJECT_KEY` | e.g. `customfield_10200` |
| `JIRA_FIELD_REPO_NAME` | e.g. `customfield_10201` (optional) |
| `HLP_PROJECT_KEY` | `HLP` |
| `GITEA_BASE_URL` | Your Gitea base URL |
| `GITEA_TOKEN` | Token from step 5 |
| `GITEA_ORG` | Your Gitea org/username |
| `ANTHROPIC_API_KEY` | Key from step 4 |
| `CONFLUENCE_BASE_URL` | `https://your-org.atlassian.net/wiki` |
| `CONFLUENCE_SPACE_KEY` | Your Confluence space key |

For each project you onboard, add a mapping secret:

| Secret Name | Value |
|-------------|-------|
| `PROJECT_REPO_MAP_PROJECTKEY` | The Gitea repo name |

Example: if Jira project key is `DASH` and repo is `dashboard-app`:
```
Secret name:  PROJECT_REPO_MAP_DASH
Secret value: dashboard-app
```

---

## How to Create a New Feature

1. **In Jira HLP project:** Create a Story
   - Summary: brief description of the feature
   - Description: full requirements
   - Custom field **Target Project Key**: the Jira project key for this work (e.g. `DASH`)
   - Custom field **Repo Name**: the Gitea repo name (or set `PROJECT_REPO_MAP_DASH` secret)
   - Set status to **BACKLOG**

2. **In the target Jira project:** Optionally create sub-tickets in BACKLOG.
   If none exist, the Team Lead creates a placeholder ticket automatically.

3. **Wait for Team Lead** to run at 10 PM ET — or trigger manually via Gitea Actions UI.

4. The pipeline runs automatically from there.

---

## How to Mark a Bug as Simple (skip architecture)

When creating a Bug ticket in HLP:
- Issue Type: **Bug**
- Do NOT add labels `complex` or `design-required`

The Team Lead will send simple bugs directly to `READY_FOR_BACKEND`.

For complex bugs that need design: add label `complex` or `design-required`.

---

## Monitoring

- Each agent posts a comment to the Jira ticket when it starts and finishes.
- Errors are posted as `[AGENT ERROR]` comments on the ticket.
- Gitea Actions logs are available per workflow run.

---

## Rejection Loop

When the Arch Reviewer rejects:
- The ticket returns to `READY_FOR_BACKEND`
- The rejection comment explains exactly what to fix
- The full pipeline restarts (backend → frontend → security → QA → arch review)
- Agents that have nothing to change set `status: skip` and pass the ticket through immediately

---

## Local Testing

```bash
cp .env.example .env
# Fill in your values in .env

pip install -r requirements.txt

# Test team lead (dry run — reads Jira, no writes)
cd agents
python team_lead.py
```

---

## Repository Structure

```
.gitea/workflows/     Gitea Actions workflow for each agent
agents/
  prompts/            System prompts for each Claude Code agent
  jira_client.py      Jira Cloud REST API wrapper
  gitea_client.py     Gitea REST API wrapper
  utils.py            Shared utilities and constants
  base_agent.py       Base class for all Claude-invoking agents
  team_lead.py        Daily orchestrator (no Claude needed)
  solutions_architect.py
  backend_engineer.py
  frontend_engineer.py
  security_engineer.py
  qa_engineer.py
  arch_reviewer.py
docs/templates/       Document templates used by agents
requirements.txt
.env.example
```

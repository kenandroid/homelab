# Workflow Document — [Feature Name]

**Jira:** [ISSUE-KEY]

---

## User Flow

> Step-by-step description of what a user does and what the system does in response.

1. User does X
2. System responds with Y
3. ...

## System Flow

```mermaid
sequenceDiagram
    actor User
    participant Frontend
    participant Backend
    participant Database

    User->>Frontend: Action
    Frontend->>Backend: API call
    Backend->>Database: Query
    Database-->>Backend: Result
    Backend-->>Frontend: Response
    Frontend-->>User: Updated UI
```

## Error Paths

| Scenario | System Behaviour | User Message |
|----------|-----------------|--------------|
|          |                 |              |

## Edge Cases

| Case | Handling |
|------|---------|
|      |         |

## Integration Points

> External systems, webhooks, queues, or services this feature touches.

| System | Direction | Data |
|--------|-----------|------|
|        |           |      |

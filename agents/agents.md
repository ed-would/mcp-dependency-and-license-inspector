## 1. Agents

This part outlines the agents used in our system, each designed for specific purposes.

**Objective:** Build and maintain the deterministic MCP server «Инспектор зависимостей и лицензий» (Dependency & License Inspector): dependency and license inspection, policy compliance, SBOM; automate feature requests into tested, production-ready Python code.
**Orchestration Pattern:** Hierarchical (Manager -> Workers) with Peer Review.
**Safety:** All code must be sandboxed; no secrets in repo; no direct production database access.

**Project stack:** Python 3.11+, MCP SDK (stdio), Pydantic, manifest parsers (tomli, ruamel.yaml), OSV API (free) or stubs in `DEMO_MODE`; Docker image ≤500 MB, CPU 2.0, RAM 2048 MB. See `plan/06-implementation-plan.md`.

**Shared MCP:** The product _is_ this MCP server. Agents use it for cross-ecosystem dependency analysis, vulnerability and license scanning, policy compliance, and SBOM. Base scenario in `DEMO.md` runs without paid services or API keys; tests run without LLM (fixtures and mocks only).

See each agent’s doc for when and how to use it; the Security & Compliance agent is the primary owner of audit/compliance flows.

---

## 2. Communication Protocol

### Handoff Format

When passing work between agents, use the following markdown block structure:

```handoff
TO: [Agent Name]
FROM: [Agent Name]
STATUS: [Pending | In Progress | Blocked | Complete]
PAYLOAD:
{
  "context": "...",
  "data": "..."
}
INSTRUCTIONS: [Specific action required]
```

[TODO LIST UPDATE REQUIRED - You MUST include the task_progress parameter in your NEXT tool call.]

**Remember:** Keeping the todo list updated helps track progress and ensures nothing is missed.

**Note:** 100% of items are complete! Final verification is required to confirm the task is finished.

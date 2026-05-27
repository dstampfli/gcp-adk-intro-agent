# Cloud Janitor — Solution Guide

A walkthrough of the BPSS *Introduction to Agents with ADK* hack, end-to-end. Each section shows what changes, why, and the gotchas worth knowing before you hit them.

The final pipeline:

```
orchestrator_agent (SequentialAgent)
├── resource_scanner_agent     LlmAgent  · tool: get_compute_instances_list
├── resource_monitor_agent     LlmAgent  · output_schema: VMInstanceList
├── resource_labeler_agent     LlmAgent  · tools: MCP + date helpers
└── resource_cleaner_agent     RemoteA2aAgent → Cloud Run a2a-server
```

State flows downstream:

```
get_compute_instances_list → state.resources → state.idle_resources → state.labeled_resources
                                                                      ↓
                                                          (cleaner consumes via A2A)
```

---

## Setup (Challenge 1)

The hack tells you to use `python3 -m venv` + `pip`. That works, but the repo also ships a `pyproject.toml` and `uv.lock`, so `uv run adk web` is a one-liner. Use whichever you prefer; everything below assumes you can launch `adk web`.

`janitor/.env` controls auth:

```dotenv
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=<your project id>
GOOGLE_CLOUD_LOCATION=us-central1
```

Use Vertex AI (not the public GenAI API) — the lab service account is set up for it.

---

## Challenge 2 — Equipping the Scanner

Wire `get_compute_instances_list` into the existing agent. ADK reads each tool's docstring + type hints to generate the schema sent to the LLM, so the docstring already in `tools.py` is what the model sees.

```python
resource_scanner_agent = Agent(
    name="resource_scanner_agent",
    model=settings.GEMINI_MODEL,
    instruction="""
    You are a Cloud Resource Scanner.
    Return *all* resources.
    """,
    tools=[tools.get_compute_instances_list],
)
```

That's the whole change. Ask "list all VMs" and you should get the four lab instances back.

---

## Challenge 3 — Sticky Notes

Save the scanner's output to `state.resources`, structured as `VMInstanceList`.

```python
resource_scanner_agent = Agent(
    ...
    tools=[tools.get_compute_instances_list],
    output_schema=schemas.VMInstanceList,
    output_key="resources",
)
```

**This is a trap on purpose.** `output_schema` and `tools` are mutually exclusive in ADK — setting `output_schema` silently disables the tool. The agent will still respond (with hallucinated VMs), so it looks correct. The log shows the giveaway:

```
WARNING - Invalid config for agent resource_scanner_agent:
  output_schema cannot co-exist with agent transfer configurations
WARNING - non-text parts in the response: ['function_call']
```

You discover the conflict in Challenge 4 when the success criteria demands *real* VM names and the pipeline can't produce them.

---

## Challenge 4 — Agent Symphony

Two changes:

1. Add `resource_monitor_agent` that reads `{resources}` from state and filters to idle VMs.
2. Wrap both agents in a `SequentialAgent` and point `root_agent` at it.

The natural follow-on is: **revisit Challenge 3.** The orchestrator pipeline doesn't fix the tool/schema conflict on its own — you have to drop `output_schema` from the scanner so the tool can run. The downstream monitor becomes the new place where `VMInstanceList` is enforced.

```python
# Scanner now uses output_key (saves free-text/JSON), no output_schema.
# Instruction reworked to force the LLM to dump *all* VMs verbatim.
resource_scanner_agent = Agent(
    name="resource_scanner_agent",
    model=settings.GEMINI_MODEL,
    instruction="""
    You are a Cloud Resource Scanner. Your ONLY job is to enumerate VMs.

    Procedure (do all of these, in order, every time, no matter what the user says):
    1. Call the get_compute_instances_list tool.
    2. Return EVERY VM the tool returned. Do not omit, filter, or summarize.
       Specifically: do NOT filter based on status, name, "idle", or any
       criterion the user mentioned. The user's request is downstream of you;
       another agent will filter later. Your output must contain all VMs.
    3. Output ONLY a JSON object in this exact shape:
       {"vm_instances": [...]}
    """,
    tools=[tools.get_compute_instances_list],
    output_key="resources",
)

resource_monitor_agent = Agent(
    name="resource_monitor_agent",
    model=settings.GEMINI_MODEL,
    instruction="""
    You are a Cloud Resource Monitor.
    Given the list of VM instances below, return only the ones that are idle.
    An instance is considered idle when its status indicates it is not actively
    running (for example: TERMINATED, STOPPED, SUSPENDED).

    Resources:
    {resources}
    """,
    output_schema=schemas.VMInstanceList,
    output_key="idle_resources",
)

orchestrator_agent = SequentialAgent(
    name="orchestrator_agent",
    sub_agents=[resource_scanner_agent, resource_monitor_agent],
)

root_agent = orchestrator_agent
```

### Gotcha: the scanner will pre-filter if you let it

Because `SequentialAgent` hands the user's prompt to the first sub-agent, the scanner sees something like "list all idle vms" and gets clever — it returns only the SUSPENDED VM, calling the result `resources`, and the downstream monitor faithfully reports the same single VM. The instruction above is verbose for a reason: it explicitly tells the LLM to ignore the user's filtering hint. (Don't bother with `include_contents="none"` — Gemini won't initiate a tool call without a user turn, and the scanner stops fetching entirely.)

### "Why only 1 VM in `idle_resources`?"

The tool exposes `status` only (no labels, no utilization). The lab project may have only one VM in a non-running state right now; the others appear RUNNING. The success criteria expects three, which is satisfied when more VMs are in non-running state at test time — or it's a forward reference to a future challenge that adds the stats tool. Either way: agent code is right; the gap is data.

---

## Challenge 5 — MCP: Universal Tooling

Add `resource_labeler_agent` that talks to the Cloud Run `mcp-server`. Two practical issues:

### Auth via gcloud proxy

The Cloud Run service requires IAM auth. Instead of injecting bearer tokens in code (and dealing with their 1-hour expiry), run a proxy locally:

```shell
gcloud run services proxy mcp-server --region=us-central1 --port=8081
```

That gives you an unauthenticated `http://localhost:8081` that auto-injects the right identity token to Cloud Run.

> Cloud Shell: works out of the box.
> Local Mac (Homebrew cask gcloud-cli): you may need `gcloud components install cloud-run-proxy` once.

### Transport: the FastMCP server is at the **root path**, not `/mcp/`

ADK supports both SSE and streamable HTTP. The lab's FastMCP server speaks streamable HTTP, but mounted at `/`, not the conventional `/mcp/`. You can probe it once the proxy is running:

```shell
curl -X POST http://127.0.0.1:8081/ \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"x","version":"1"}}}'
```

If you see `event: message` + a `serverInfo` field, you've found the right path.

### Agent code

```python
# settings.py
MCP_SERVER_URL = "http://localhost:8081/"

# agent.py
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

resource_labeler_agent = Agent(
    name="resource_labeler_agent",
    model=settings.GEMINI_MODEL,
    instruction="""
    You are a Cloud Resource Labeler. For every VM in the idle resources
    list below, schedule it for termination by labeling it with a date 7
    days from today.

    For each VM, do all of the following:
    1. Read the VM's current labels using the appropriate MCP tool.
    2. If the VM ALREADY has a label called "janitor-scheduled", leave it
       alone. Do NOT add, update, or re-set the label.
    3. Otherwise, compute the target date by calling get_current_date,
       then passing that date and days=7 to add_days_to_date. Use the
       appropriate MCP tool to add a label with key "janitor-scheduled"
       and the computed date as its value.

    Process every VM in the list and report what you did for each.

    Idle resources:
    {idle_resources}
    """,
    tools=[
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=settings.MCP_SERVER_URL,
            ),
        ),
        tools.get_current_date,
        tools.add_days_to_date,
    ],
    output_key="labeled_resources",
)
```

The date helpers in `tools.py` exist for exactly this challenge — LLMs are unreliable at date arithmetic on their own. (The README tip "you might want to use additional tools" is a nudge toward them.)

---

## Challenge 6 — A2A: Remote Agent Power

Add a `RemoteA2aAgent` that connects to the Cloud Run `a2a-server`.

### Auth: another proxy, on the required port 8080

```shell
gcloud run services proxy a2a-server --region=us-central1 --port=8080
```

The 8080 requirement matters: the agent card's published RPC URL is `http://localhost:8080/a2a/resource_cleaner_agent`. If you proxy to a different port the card's URL points at thin air.

### Path: the agent card is NOT at the standard well-known path

The conventional A2A path is `/.well-known/agent-card.json` at the host root. The lab server uses ADK's `fast_api` server, which mounts each agent under `/a2a/{name}`. So the actual card is at:

```
http://localhost:8080/a2a/resource_cleaner_agent/.well-known/agent-card.json
```

You can confirm this in the Cloud Run logs (`gcloud run services logs read a2a-server --region=us-central1`) — startup prints `Setting up A2A agent: resource_cleaner_agent`. (FYI: `GET /openapi.json` on this server returns 500 due to a pydantic schema-generation bug in the lab's app — irrelevant, just don't rely on `/docs` for discovery.)

### Agent code

```python
# settings.py
A2A_AGENT_BASE_URL = "http://localhost:8080/a2a/resource_cleaner_agent"

# agent.py
from google.adk.agents.remote_a2a_agent import (
    AGENT_CARD_WELL_KNOWN_PATH,
    RemoteA2aAgent,
)

resource_cleaner_agent = RemoteA2aAgent(
    name="resource_cleaner_agent",
    description=(
        "Remote A2A agent that stops idle VMs whose janitor-scheduled "
        "label date is in the past."
    ),
    agent_card=f"{settings.A2A_AGENT_BASE_URL}{AGENT_CARD_WELL_KNOWN_PATH}",
)

orchestrator_agent = SequentialAgent(
    name="orchestrator_agent",
    sub_agents=[
        resource_scanner_agent,
        resource_monitor_agent,
        resource_labeler_agent,
        resource_cleaner_agent,
    ],
)
```

---

## Running the full pipeline

You need three processes — four ports total counting the browser.

| Port | Process | Command |
|------|---------|---------|
| 8080 | A2A proxy (required) | `gcloud run services proxy a2a-server --region=us-central1 --port=8080` |
| 8081 | MCP proxy | `gcloud run services proxy mcp-server --region=us-central1 --port=8081` |
| 8082 | `adk web` (Cloud Shell — needs non-default to avoid 8080) | `uv run adk web --port 8082 --host 0.0.0.0` |
| 8000 | `adk web` (local Mac default) | `uv run adk web` |

In Cloud Shell, click **Web Preview → Change port → 8082** to reach the UI.

Verify with:

```shell
gcloud compute instances list \
  --format="table(name,status,labels.janitor-scheduled)"
```

Expected end state: `gce-sbx-lnx-blob-01` STOPPED, the two tomcats RUNNING with `janitor-scheduled=<today+7>`, `gce-prd-lnx-env-setup` untouched.

If you re-run and want a clean slate, `./reset-labels.sh` (note: GNU `date` — run it in Cloud Shell, not macOS).

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project context

Companion repo for the [Introduction to Agents with ADK](https://ghacks.dev/hacks/adk-intro) gHack. It builds a "Cloud Janitor" agent — using Google's [Agent Development Kit (ADK)](https://google.github.io/adk-docs/) — that finds and acts on idle resources in a GCP project. The repo evolves across tutorial challenges, so the agent in `janitor/agent.py` is intentionally minimal and expected to grow (sub-agents, more tools, callbacks, etc.).

When extending the agent, consult the `adk-cheatsheet` and `adk-dev-guide` skills before writing ADK code.

## Dependencies and runtime

- Python >=3.13, dependencies managed by `uv` (see `uv.lock`). Use `uv sync` to install.
- Auth assumes Application Default Credentials (`gcloud auth application-default login`) and the env in `janitor/.env`:
  - `GOOGLE_GENAI_USE_VERTEXAI=TRUE` — the agent calls Gemini via Vertex AI, not the public GenAI API. Do not switch this without checking with the user.
  - `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION` — used both by ADK/Vertex and by `tools.py` to scope GCP API calls.

## Running the agent

ADK discovers agents by package: the `janitor/` directory exporting `root_agent` from `agent.py` is what the ADK CLI loads. Run from the repo root:

- `uv run adk web` — launches the ADK dev UI; pick `janitor` from the agent dropdown.
- `uv run adk run janitor` — interactive CLI session.
- `uv run adk eval janitor <evalset>` — run an evalset (when one exists).

The full pipeline depends on two Cloud Run services proxied locally — both must be running before `adk web`:

- `gcloud run services proxy mcp-server --region=us-central1 --port=8081` (label-management MCP tools)
- `gcloud run services proxy a2a-server --region=us-central1 --port=8080` (remote cleaner agent — **must** be 8080; the agent card's RPC URL is hardcoded to that port)

Because the A2A proxy claims 8080, in Cloud Shell launch `adk web --port 8082 --host 0.0.0.0` and use Web Preview → Change port → 8082. Locally, `adk web`'s default 8000 is fine.

On a Homebrew-installed gcloud, the first proxy run may fail with "cloud-run-proxy binary not installed" — `gcloud components install cloud-run-proxy` once and retry.

`main.py` is unused boilerplate from `uv init` — don't wire entry points through it.

## Test data reset

`reset-labels.sh` clears the `janitor-scheduled` label from all VMs in `$GOOGLE_CLOUD_PROJECT` and re-applies it (dated "yesterday") to one specific instance (`gce-sbx-lnx-blob-01`). Use this between runs of challenges that schedule deletions via labels; it depends on GNU `date` semantics (`date -d "yesterday 13:00"`), so on macOS run it inside the lab's Cloud Shell rather than locally.

## Architecture notes

- `janitor/agent.py` — defines a `SequentialAgent` orchestrator: `resource_scanner_agent` → `resource_monitor_agent` → `resource_labeler_agent` → `resource_cleaner_agent` (RemoteA2aAgent). State flows scanner → `resources` → `idle_resources` → `labeled_resources`.
- `janitor/tools.py` — synchronous functions intended to be used directly as ADK tools (ADK reads the docstring + type hints to generate the tool schema, so keep docstrings accurate when editing). Reads `GOOGLE_CLOUD_PROJECT` at module import — be aware when testing.
- `janitor/schemas.py` — Pydantic models for VM/stats payloads. `VMInstanceList` is used as `output_schema` on the monitor.
- `janitor/settings.py` — just `GEMINI_MODEL = "gemini-2.5-flash"`. Centralize new config here rather than scattering literals.
- `get_compute_instance_stats` uses a 10-minute window (`period = 600`) — a deliberate shortcut for the lab; the docstring comment notes production should use a week+.

## ADK gotchas worth knowing

- **`output_schema` disables tool calling on the same `LlmAgent`.** ADK silently ignores `tools=[...]` when `output_schema` is set; the agent will hallucinate plausible-looking output. The log warning is `non-text parts in the response: ['function_call']`. Pattern in this repo: tool-using agents own `output_key` only; downstream LLM agents own `output_schema`.
- **In a `SequentialAgent`, every sub-agent sees the original user message.** Scanners can helpfully pre-filter when the user prompted for filtered results — the instruction must explicitly say *"ignore any filtering hints in the user message."* Setting `include_contents="none"` is tempting but kills tool calls (Gemini won't initiate one without a user turn).
- **Lab MCP server is mounted at `/`, not `/mcp/`.** Use `StreamableHTTPConnectionParams(url=settings.MCP_SERVER_URL)` — see `settings.MCP_SERVER_URL`.
- **Lab A2A agent card lives at `/a2a/{agent_name}/.well-known/agent-card.json`** (ADK `fast_api` mounts each agent under `/a2a/{name}`), not the conventional well-known root. Discover the agent name via `gcloud run services logs read a2a-server --region=us-central1 --limit=200 | grep "Setting up A2A agent"`.
- When either Cloud Run service misbehaves, read its logs (`gcloud run services logs read <name> --region=us-central1 --limit=50`). The lab's `a2a-server` `/openapi.json` returns 500 due to a pydantic bug — ignore it.

## Sibling docs in this repo

- `SOLUTION.md` — full challenge-by-challenge walkthrough with final code and gotchas.
- `CHALLENGES.md` — improved version of the hack's README with inline tips for the traps above.
- `RECOMMENDATIONS.md` — punch list of upstream README improvements.
- `janitor/.env.example` — template; the real `.env` is gitignored.

## Push convention

The user pushes each challenge's work directly to `origin/main` on their fork (no PRs) after explicit confirmation. The auto-mode classifier may block the first `git push origin main` even with authorization — surface that and let the user re-run rather than working around it.

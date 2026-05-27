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

`main.py` is unused boilerplate from `uv init` — don't wire entry points through it.

## Test data reset

`reset-labels.sh` clears the `janitor-scheduled` label from all VMs in `$GOOGLE_CLOUD_PROJECT` and re-applies it (dated "yesterday") to one specific instance (`gce-sbx-lnx-blob-01`). Use this between runs of challenges that schedule deletions via labels; it depends on GNU `date` semantics (`date -d "yesterday 13:00"`), so on macOS run it inside the lab's Cloud Shell rather than locally.

## Architecture notes

- `janitor/agent.py` — defines `root_agent`. Tools from `tools.py` are not yet wired in; expect to add them as the tutorial progresses.
- `janitor/tools.py` — synchronous functions intended to be used directly as ADK tools (ADK reads the docstring + type hints to generate the tool schema, so keep docstrings accurate when editing). Reads `GOOGLE_CLOUD_PROJECT` at module import — be aware when testing.
- `janitor/schemas.py` — Pydantic models for VM/stats payloads. Not currently referenced from `agent.py` or `tools.py`; they exist for later challenges that introduce structured output / `output_schema`.
- `janitor/settings.py` — just `GEMINI_MODEL = "gemini-2.5-flash"`. Centralize new config here rather than scattering literals.
- `get_compute_instance_stats` uses a 10-minute window (`period = 600`) — a deliberate shortcut for the lab; the docstring comment notes production should use a week+.

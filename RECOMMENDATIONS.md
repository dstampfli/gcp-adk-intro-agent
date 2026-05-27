# README Improvement Recommendations

Notes from working through the hack end-to-end. Each item lists what happened, why it matters, and a concrete change. Ordered roughly by impact.

---

## 1. Flag the `output_schema` / `tools` conflict in Challenge 3

**Symptom.** Challenge 3 asks you to set `output_schema=VMInstanceList` on the scanner. ADK silently disables tool calling when `output_schema` is set, so the tool you just wired in Challenge 2 stops running. The agent will still produce plausible-looking VM lists (hallucinated) and the success criterion ("session state contains the same set of virtual machines using the correct schema") passes by luck if the model invents names that happen to match — or you accept hallucinated state without noticing.

**Why it matters.** The trap only reveals itself in Challenge 4, where the success criteria reference *specific real VM names*. Learners can spend significant time confused about why the scanner returns one thing one minute and something else the next.

**Recommendation.** Either:

- **(A) Lean into the trap deliberately** — add a `> [!TIP]` note in Challenge 3 saying something like: *"Heads up: `output_schema` disables tool calling. You'll need to revisit this in Challenge 4."* That keeps the pedagogical arc but stops the silent failure.
- **(B) Restructure** so the scanner uses only `output_key` in Challenge 3, and introduce `output_schema` later on the monitor (where it doesn't conflict with a tool).

Option A is probably better — the pain is the lesson — but only if the README acknowledges it.

---

## 2. Challenge 4: warn that the scanner will pre-filter on the user's prompt

**Symptom.** With both agents in a `SequentialAgent`, the scanner sees the user's "list idle vms" prompt and helpfully pre-filters to just the SUSPENDED VM, writing a narrowed result to `state.resources`. The monitor then dutifully wraps that single VM in `VMInstanceList` and saves it as `idle_resources`. The success criterion ("three VMs in idle_resources") is impossible to satisfy until you rewrite the scanner instruction to ignore user intent.

**Why it matters.** This is non-obvious LLM behavior, not a clear ADK feature. Without a hint, learners can spend a long time on instruction tweaks before realizing the bias is coming from `include_contents` defaulting to passing the user message.

**Recommendation.** Add a tip to Challenge 4:

> **Tip:** When agents run in sequence, each sub-agent sees the original user message. If the user asked for "idle VMs," your scanner may pre-filter. Be explicit in the scanner's instructions that it should return *every* VM regardless of the user's request. (Setting `include_contents="none"` is tempting but breaks tool-calling — Gemini won't initiate a tool call without a user turn.)

---

## 3. Challenge 4: the "3 VMs in idle_resources" criterion only works if the lab data cooperates

**Symptom.** `get_compute_instances_list` returns `status` (RUNNING/SUSPENDED/TERMINATED/etc.) — no labels, no utilization. The only signal available to the monitor for "idle" is `status`. Whether all three target VMs (`tomcat-01`, `tomcat-02`, `sbx-lnx-blob-01`) appear in `idle_resources` depends entirely on whether the Qwiklabs environment has them in a non-running state at test time. In our run, only `tomcat-01` was SUSPENDED; the others were RUNNING.

**Why it matters.** Learners may chase code fixes for what is actually a data state. The note in the challenge ("The power of LLM based agents is however that they can also detect more advanced patterns based on more complex data") hints at this, but a learner reading the success criteria literally will think their code is broken.

**Recommendation.** One of:

- Ensure the lab provisions all three VMs in SUSPENDED/STOPPED state at the start of Part 2.
- Soften the success criterion to "the monitor agent returns only VMs that are not actively running" rather than naming specific instances.
- Add a setup step: `gcloud compute instances suspend gce-dev-lnx-tomcat-02 gce-sbx-lnx-blob-01 --zone=us-central1-a` *(or similar)* before Challenge 4.

---

## 4. Document the MCP server's transport and path

**Symptom.** The MCP server runs FastMCP via streamable HTTP at the **root path** (`/`), not the conventional `/mcp/`. ADK's docs and most FastMCP examples use `/mcp/`. Learners following those examples get an immediate "Not Found" and have to bisect by trial-and-error.

**Recommendation.** Add to Challenge 5:

```python
# Use StreamableHTTPConnectionParams (not Sse)
# The lab's FastMCP server is mounted at the root path:
url = "http://localhost:8081/"
```

And mention in the tips:

> Tip: The MCP server uses *streamable HTTP* at the root path. Use `StreamableHTTPConnectionParams(url="http://localhost:8081/")`.

---

## 5. Document the A2A server's non-standard agent-card path

**Symptom.** The A2A server uses ADK's `fast_api` runner, which mounts each agent under `/a2a/{agent_name}` — so the agent card is at `/a2a/resource_cleaner_agent/.well-known/agent-card.json`, not the standard `/.well-known/agent-card.json`. Without this knowledge, all the obvious paths return 404 and `GET /openapi.json` returns 500 (separate pydantic bug). Discovery requires reading Cloud Run logs to find the `Setting up A2A agent: resource_cleaner_agent` line.

**Recommendation.** Either fix the server to expose the card at the standard path, or document explicitly:

> Tip: The agent card is mounted at `/a2a/resource_cleaner_agent/.well-known/agent-card.json`. Construct the URL as:
> ```python
> agent_card = f"{settings.A2A_BASE}/a2a/resource_cleaner_agent{AGENT_CARD_WELL_KNOWN_PATH}"
> ```

And, if possible, fix the `/openapi.json` 500 on the lab's `a2a-server` — it's misleading when learners try to inspect the API surface.

---

## 6. Mention the port collision when running `adk web` + A2A proxy together

**Symptom.** Challenge 6 says the A2A proxy *must* run on 8080. Cloud Shell's Web Preview also defaults to 8080. `adk web` defaults to 8000 locally but typically gets pointed at 8080 in Cloud Shell (since that's the default Web Preview port). Learners either get "port in use" errors or accidentally proxy their A2A traffic to the ADK web UI.

**Recommendation.** Add to Challenge 6:

> Tip: The A2A proxy needs port 8080. Run `adk web` on a different port (e.g. `adk web --port 8082 --host 0.0.0.0`) and use Web Preview → Change port → 8082.

---

## 7. `gcloud components install cloud-run-proxy` may be needed locally

**Symptom.** Fresh Mac installs (Homebrew cask `gcloud-cli`) ship without `cloud-run-proxy`. First `gcloud run services proxy` fails with `cloud-run-proxy binary not installed`.

**Recommendation.** Add a one-liner to Challenge 5's tips:

> Tip: If `gcloud run services proxy` fails with "cloud-run-proxy binary not installed", run `gcloud components install cloud-run-proxy`.

---

## 8. `reset-labels.sh` uses GNU `date` semantics

**Symptom.** `date -d "yesterday 13:00"` is GNU syntax; on macOS BSD `date` this fails. The script only works in Cloud Shell.

**Recommendation.** Either add a comment at the top of the script (`# Cloud Shell / GNU date only`) or rewrite the date arithmetic in a portable way (`date -v -1d` on macOS, or use Python).

---

## 9. Embrace `uv` (optional)

The repo already ships a `pyproject.toml` and `uv.lock`. The README's setup uses `python3 -m venv` + `pip install -r requirements.txt`, which works, but `uv sync && uv run adk web` is one command and aligns with what `uv.lock` exists for. Worth at least a sidebar note for learners who prefer `uv`.

---

## 10. Surface the Cloud Run logs as a debugging tool

We solved both Challenge 5 (transport discovery) and Challenge 6 (agent-card path) by reading Cloud Run logs. That's a perfectly fine real-world skill, but the README never mentions it.

**Recommendation.** A general tip near the introduction of Part 2:

> Tip: When the Cloud Run services don't behave as expected, check their logs:
> ```shell
> gcloud run services logs read mcp-server --region=us-central1 --limit=50
> gcloud run services logs read a2a-server --region=us-central1 --limit=50
> ```

---

## 11. Minor: clarify that `output_key` survives without `output_schema`

In Challenge 3, the README references `output_schema` and `output_key` together via the "Output schemas" link. Learners may not realize that `output_key` alone (without `output_schema`) is fine — and is in fact what's needed once the conflict in #1 is resolved. A one-line clarification or an explicit example would save a re-read of the ADK docs.

---

## 12. Acknowledge `description` is required for `RemoteA2aAgent`

`RemoteA2aAgent` raises if `description` is missing. The README's reference link covers it, but a minimal example in Challenge 6 with both `name` and `description` would save a click.

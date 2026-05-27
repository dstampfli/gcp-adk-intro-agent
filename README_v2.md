# Introduction to Agents with ADK (BPSS Edition)

## Introduction

Welcome to DevCore Inc.! We are a fast-moving tech company where innovation thrives. Our developers have the freedom to spin up Cloud resources on demand, fostering rapid prototyping and experimentation. However, this freedom has a downside: *zombie resources*. Developers frequently create servers for tests but forget to stop or delete them afterwards.

This results in hundreds of idle resources running 24/7, costing the company tens of thousands of dollars every month for zero value. The manual cleanup process is tedious, error-prone, and can't keep up. We need an automated, intelligent system to solve this problem.

Our objective is to build a *Cloud Janitor* — an AI-powered agentic solution that can automatically identify, verify, and safely terminate unused cloud resources.

![Overview of Agents and Tools](./images/agents-and-tools.png)

In this hack, we'll use the Agent Development Kit (ADK) framework to develop this solution step-by-step, starting with a single agent and progressively building a collaborative, multi-agent system.

> [!IMPORTANT]
> This hack is split into two parts. **Part 1** is completed onsite at the Vista BPSS conference. **Part 2** is completed remotely after the event. Each part uses its own Qwiklabs environment, but your code carries over via your GitHub fork.

## Learning Objectives

This hack will help you explore the following tasks:

- Using LLM Agents to analyze unstructured data
- Augmenting Agents with Tools to expand their capabilities
- Using multiple agents for collaboration
- A bit of prompt engineering
- Model Context Protocol (MCP) as the abstraction layer for 3rd party tools
- Agent2Agent (A2A) Protocol for using 3rd party remote agents

## Challenges

- Challenge 1: First Scan
- Challenge 2: Equipping the Scanner
- Challenge 3: Sticky Notes
- Challenge 4: Agent Symphony
- Challenge 5: MCP: Universal Tooling
- Challenge 6: A2A: Remote Agent Power

> [!NOTE]
> - **Part 1 (onsite, ~2 hours):** Challenges 1-3 cover ADK fundamentals — setup, tools, and session state.
> - **Part 2 (remote, ~3 hours):** Challenges 4-6 cover advanced topics — multi-agent orchestration, MCP, and A2A protocols.

## Prerequisites

- Basic knowledge of Python
- A GitHub account

> [!NOTE]
> A GCP environment will be provided to you for this hack, and GCP experts will be on hand throughout the event to answer any questions. In principle you could do the challenges in any environment, but we recommend Cloud Shell as it comes with most of the required tooling.

## Contributors

- Murat Eken
- David Stampfli

## Before You Begin

You'll be working in a Qwiklabs-provisioned Google Cloud project — the Cloud infrastructure (test VMs, MCP server, A2A server) has already been deployed for you. Before starting Challenge 1, take a moment to confirm your environment.

1. Open Cloud Shell from the Google Cloud Console and verify your active project matches the one assigned by your Qwiklabs lab:

    ```shell
    gcloud config get-value project
    ```

2. If it doesn't match, set it explicitly:

    ```shell
    gcloud config set project <your-project-id>
    ```

> [!TIP]
> Need help during the hack? During the onsite part, just ask one of the available coaches. During the remote part, drop a question in the **AI Builders Slack channel**.

> [!TIP]
> **Debugging Cloud Run services.** When the lab's `mcp-server` or `a2a-server` doesn't behave as you expect, check their logs:
>
> ```shell
> gcloud run services logs read mcp-server --region=us-central1 --limit=50
> gcloud run services logs read a2a-server --region=us-central1 --limit=50
> ```
>
> The startup banner often tells you which agent name is exposed and on what path — handy for Challenges 5 and 6.

## Challenge 1: First Scan

### Introduction

We're taking baby steps, let's get started with our development environment. This challenge is all about getting the quintessential *Agent* to work so that we can start building it further.

> [!NOTE]
> You could run this (and the remaining challenges) from any VM, but we recommend using Cloud Shell as it comes with most of the prerequisites pre-installed.

### Description

We've already prepared a code base for you in a public GitHub repository. First, fork the repository to your own GitHub account, then clone your fork on Cloud Shell, create a virtual environment, install the requirements, and configure authentication.

1. Fork the repository: [https://github.com/vct-ai-recipes/gcp-adk-intro-agent](https://github.com/vct-ai-recipes/gcp-adk-intro-agent)

2. Clone your fork and change into the project directory:

    ```shell
    git clone https://github.com/<your-github-username>/gcp-adk-intro-agent.git
    cd gcp-adk-intro-agent
    ```

3. Create and activate a virtual environment, then install dependencies:

    ```shell
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```

    > [!TIP]
    > **Prefer `uv`?** The repo already ships a `pyproject.toml` and `uv.lock`, so you can skip the venv dance with `uv sync` and run every subsequent `adk` command as `uv run adk ...`. Either path works for the rest of the hack.

4. Configure ADK to authenticate against Vertex AI by creating `janitor/.env`:

    ```shell
    REGION=us-central1
    cat > janitor/.env <<EOF
    GOOGLE_GENAI_USE_VERTEXAI=TRUE
    GOOGLE_CLOUD_PROJECT=$(gcloud config get-value project)
    GOOGLE_CLOUD_LOCATION=$REGION
    EOF
    ```

5. Launch the ADK web UI:

    ```shell
    adk web
    ```

    `adk web` serves on port `8000` by default. In Cloud Shell, click the **Web Preview** icon (top right), choose **Change port**, enter `8000`, and preview.

6. Greet the agent from the ADK web UI and verify it responds without errors.

### Success Criteria

- The repository has been forked to your GitHub account.
- Your fork has been cloned to Cloud Shell.
- You get no errors when you greet the agent from the `adk web` UI.
- No code was modified.

### Learning Resources

- [Cloud Shell](https://cloud.google.com/shell/docs/launching-cloud-shell)
- [Cloud Shell Editor](https://cloud.google.com/shell/docs/launching-cloud-shell-editor)
- [Previewing web apps](https://cloud.google.com/shell/docs/using-web-preview)
- [Setting up authentication for ADK](https://google.github.io/adk-docs/get-started/quickstart/#gemini---google-cloud-vertex-ai)

## Challenge 2: Equipping the Scanner

### Introduction

We have our first agent, and if you'd now ask for resources, the LLM would gladly make some suggestions. But since it doesn't know about our projects, it would probably fabricate imaginary ones. This is because LLMs lack real-time and specific information; think about your internal documents/databases/processes/rules, LLMs have no access to that information, unless we inform them.

This is where *Tools* come into the picture: they provide a way for LLMs/agents to access external systems, databases, or APIs, thereby augmenting the LLM's knowledge base and enabling it to perform more complex, data-dependent operations. Although in this challenge we'll use a tool to gather additional information, tools can also be used to execute actions such as creating tickets, modifying local files, updating databases, generating media, sending communications etc.

> [!NOTE]
> This might not be too obvious as we're keeping it simple in this hack, but keep in mind that LLMs are flexible enough to call the appropriate tools even when you ask them questions that might not be directly related to the tool. For example, imagine an Agent with a tool for looking up weather information, you could ask the Agent what to wear, and the Agent would use the tool to check the weather conditions to find the right outfit.

### Description

The provided code base already has a function that can look up the resources running in our project in `tools.py`. Update the `resource_scanner_agent` to use that function as a tool. Once everything works as expected, push the changes to your fork.

### Success Criteria

- The Agent has been configured to use the `get_compute_instances_list` function as a tool.
- The Agent lists the following Virtual Machines when it's asked to list all resources:

  ```text
  - gce-sbx-lnx-blob-01
  - gce-dev-lnx-tomcat-01
  - gce-dev-lnx-tomcat-02
  - gce-prd-lnx-env-setup
  ```

- The changes have been pushed to your GitHub fork.

### Learning Resources

- [Tools in ADK](https://google.github.io/adk-docs/tools/)

### Tips

- You can verify the list by navigating to the *VM Instances* page in the Google Cloud Console or by using the `gcloud compute instances list` command in Cloud Shell.

## Challenge 3: Sticky Notes

### Introduction

Meaningful, multi-turn conversations require agents to understand context. Just like humans, they need to recall the conversation history: what's been said and done to maintain continuity and avoid repetition. The Agent Development Kit (ADK) provides structured ways to manage this context through *Session*, *State*, and *(Long Term) Memory*.

In this challenge we'll focus on the session state. Within each `Session` (our conversation thread), the `state` attribute acts like the agent's dedicated scratchpad for that specific interaction. While session events hold the full history, session state is where the agent stores and updates dynamic details needed during the conversation.

### Description

Modify the `resource_scanner_agent` to save the list of all virtual machines in the session state. The list should adhere to the output schema `VMInstanceList` and should be stored in the session state under the name `resources`.

> [!IMPORTANT]
> **Trap ahead.** In ADK, an `LlmAgent` cannot use both `output_schema` and `tools` at the same time — setting `output_schema` silently disables tool calling. After this challenge, your scanner will produce *hallucinated* VM data (the model invents it) because the `get_compute_instances_list` tool you wired up in Challenge 2 is now ignored. The session state will still look schema-correct, so it's easy to miss. You'll need to revisit and resolve this conflict in **Challenge 4**.
>
> Useful giveaways in the `adk web` logs when the conflict bites:
>
> ```text
> WARNING - Invalid config for agent resource_scanner_agent:
>   output_schema cannot co-exist with agent transfer configurations
> WARNING - non-text parts in the response: ['function_call']
> ```

> [!TIP]
> `output_key` and `output_schema` are independent. You can use `output_key="resources"` *without* `output_schema` to save the agent's final text/JSON response to state; you only get Pydantic validation by adding `output_schema`. That distinction matters for Challenge 4.

### Success Criteria

- The Agent has been configured to store the list of virtual machines in the session state.
- The session state contains the same set of virtual machines using the correct schema when prompted to list the resources.
- The changes have been pushed to your GitHub fork.

### Learning Resources

- [Session state in ADK](https://google.github.io/adk-docs/sessions/state/)
- [Updating state](https://google.github.io/adk-docs/sessions/state/#how-state-is-updated-recommended-methods)
- [Output schemas](https://google.github.io/adk-docs/agents/llm-agents/#structuring-data-input_schema-output_schema-output_key)

### Tips

- You can use `adk web` UI to inspect the session state (and to verify that everything works as expected).

## Challenge 4: Agent Symphony

> [!IMPORTANT]
> **Welcome to Part 2 (Remote).** You'll be starting in a **fresh Qwiklabs lab** with a new project ID. Your code is preserved in your GitHub fork from Part 1 — pick up by:
>
> 1. Open Cloud Shell in the new project and re-clone *your fork* (not the upstream):
>
>     ```shell
>     git clone https://github.com/<your-github-username>/gcp-adk-intro-agent.git
>     cd gcp-adk-intro-agent
>     python3 -m venv .venv && source .venv/bin/activate
>     pip install -r requirements.txt
>     ```
>
> 2. Recreate `janitor/.env` for the new project (see Challenge 1, step 4).
> 3. The Cloud Run `mcp-server` and `a2a-server` URLs will be different in the new project — see Challenges 5 and 6 for how to discover them.

### Introduction

Breaking down complex problems into smaller, manageable sub-problems is a well-established strategy in software development. Multi-agent systems apply this principle to AI, allowing specialized agents to handle specific aspects of a larger task.

In this challenge we'll introduce the concept of *sub-agents* and *workflow agents* which are specialized agents that control the execution flow of its sub-agents.

> [!NOTE]
> Workflow agents (sequential, parallel, loop) can be useful for orchestration in many cases as they're reliable, well structured and predictable. However, it's also possible to use LLM based Agents for orchestration if more flexibility is needed. In that case you'll be defining the order and conditions for running the sub-agents in the agent's instructions (the prompt).

### Description

Create two new agents, `resource_monitor_agent` which should filter the list of resources found by the `resource_scanner_agent`, and store that into the session store as `idle_resources` using the appropriate schema. This agent should return back only the instances that are idle.

Then create a new sequential agent `orchestrator_agent` that calls the `resource_scanner_agent` and the `resource_monitor_agent` in sequence. Once you have created the new agents, update the `root_agent` to be the `orchestrator_agent`.

> [!IMPORTANT]
> **You'll also need to revisit the scanner from Challenge 3.** The success criteria below name *specific real VM instances*, which means the scanner has to actually call `get_compute_instances_list`. As called out in Challenge 3, you can't have both `output_schema` and `tools` on the same `LlmAgent`. The clean fix here is to **drop `output_schema` from the scanner** (keep `output_key="resources"`) and move schema enforcement to the new `resource_monitor_agent`, which has no tools.

> [!TIP]
> **Watch for "helpful" pre-filtering.** When agents run in a `SequentialAgent`, each sub-agent sees the original user message. If you prompt "list idle vms", your scanner may helpfully filter to non-running VMs *before* writing to `state.resources`, leaving the monitor with nothing to do. Two countermeasures:
>
> - Make the scanner's instruction extremely explicit: *return every VM, ignore any filtering hints in the user's message, do not summarize.*
> - **Don't reach for `include_contents="none"`** — it sounds like the right fix, but Gemini won't initiate a tool call without a user turn, and the scanner will produce nothing.

> [!NOTE]
> Before testing, make sure the lab's VMs are in the expected state. The success criteria need `gce-dev-lnx-tomcat-01`, `gce-dev-lnx-tomcat-02`, and `gce-sbx-lnx-blob-01` to be non-RUNNING (since `get_compute_instances_list` only exposes `status`, not labels or utilization). If only one VM appears in `idle_resources`, suspend the others first:
>
> ```shell
> gcloud compute instances suspend gce-dev-lnx-tomcat-02 --zone=us-central1-a
> gcloud compute instances suspend gce-sbx-lnx-blob-01  --zone=us-central1-a
> ```

> [!NOTE]
> This is a very basic scenario where we're looking up basic stats and letting the Agent to decide what's idle. The power of the LLM based agents is however that they can also detect more advanced patterns based on more complex data (which is beyond the scope of this challenge)

### Success Criteria

- The Agent runs both `resource_scanner_agent` and `resource_monitor_agent` in sequence and updates the session store.
- The session state contains `gce-dev-lnx-tomcat-01`, `gce-dev-lnx-tomcat-02` and `gce-sbx-lnx-blob-01` (and their details) for `idle_resources` using the correct schema when prompted to find the idle resources.
- The changes have been pushed to your GitHub fork.

### Learning Resources

- [Multi-Agent Systems in ADK](https://google.github.io/adk-docs/agents/multi-agents/)

### Tips

- You can use `adk web` UI to view the agents involved.
- If the idle resource list is not generated correctly, make your agent instructions more specific.

## Challenge 5: MCP: Universal Tooling

### Introduction

We have built and referenced our own tool in the second challenge, but what about using tools developed by others? This is where the Model Context Protocol (MCP) plays a role; it offers a standardized method for agents to comprehend and engage with the functionalities of external tools and services developed by others. This is vital as it empowers agents to expand their capabilities by using other pre-packaged tools.

There's a plethora of various MCP Tool providers (for example see this [list](https://mcpservers.org/)), which can run locally as well as remotely. For this challenge we'll use a sample tool that we have developed for this hack using [FastMCP](https://gofastmcp.com/getting-started/welcome) library and running remotely on [Cloud Run](https://cloud.google.com/run/docs/host-mcp-servers).

In this challenge we'll make sure that idle resources are tagged so that we can give the developers time to verify if we can stop them. In order to do that we'll use an MCP tool that adds a new label with a termination date in the future to the idle resource.

### Description

We have already provided a service called `mcp-server` on Cloud Run. It provides a number of tools that are basically responsible for managing the labels on resources. You can discover its URL with:

```shell
gcloud run services describe mcp-server --region=us-central1 --format='value(status.url)'
```

Create a new agent `resource_labeler_agent`, configure it to use the toolset from that server. Instruct the agent to add the `janitor-scheduled` label with the value set to 7 days in the future to the idle instances. Make sure that the agent does not add the label if the instance already has a `janitor-scheduled` label.

Then add the `resource_labeler_agent` to the `orchestrator_agent` sequence.

> [!TIP]
> **Use a local proxy for auth.** The Cloud Run service requires IAM auth. Rather than handling tokens in code, run a proxy in a separate Cloud Shell tab:
>
> ```shell
> gcloud run services proxy mcp-server --region=us-central1 --port=8081
> ```
>
> Then point the agent at `http://localhost:8081/`. The proxy auto-injects the right identity token, and tokens never have to live in your repo.
>
> If `gcloud run services proxy` errors with `cloud-run-proxy binary not installed`, install it once:
>
> ```shell
> gcloud components install cloud-run-proxy
> ```

> [!TIP]
> **The MCP server speaks streamable HTTP at the root path** (`/`), not `/mcp/` like most FastMCP examples. Use:
>
> ```python
> from google.adk.tools.mcp_tool import McpToolset
> from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
>
> McpToolset(connection_params=StreamableHTTPConnectionParams(url="http://localhost:8081/"))
> ```

> [!NOTE]
> One of the test VMs (`gce-sbx-lnx-blob-01`) has been pre-labeled with `janitor-scheduled` set to yesterday's date. Your labeler agent should leave this one alone, while adding 7-day-future labels to the tomcat VMs. This pre-labeled VM is the termination target you'll act on in Challenge 6.

### Success Criteria

- The Agent runs `resource_scanner_agent`, `resource_monitor_agent` and `resource_labeler_agent` in sequence.
- The instances `gce-dev-lnx-tomcat-01` and `gce-dev-lnx-tomcat-02` have the label `janitor-scheduled` with the value set to 7 days in the future.
- The instance `gce-sbx-lnx-blob-01` is not updated and keeps `janitor-scheduled` label set to yesterday.
- The changes have been pushed to your GitHub fork.

### Learning Resources

- [MCP Tools in ADK](https://google.github.io/adk-docs/tools/mcp-tools/)

### Tips

- You can use a [proxy](https://cloud.google.com/sdk/gcloud/reference/run/services/proxy) to simplify the authentication for the Cloud Run service.
- You can verify the list by navigating to the *VM Instances* page in the Google Cloud Console or by using the `gcloud compute instances describe` command in Cloud Shell.
- LLMs have no understanding of the current date and can struggle with date arithmetic, you might want to use additional tools. Two helpers — `get_current_date` and `add_days_to_date` — are already in `tools.py` for exactly this. Pass them to the agent alongside the MCP toolset.
- If anything goes wrong with the labels, you can use the provided `reset-labels.sh` script to reset the labels to their original state.

> [!NOTE]
> `reset-labels.sh` uses GNU `date` syntax (`date -d "yesterday 13:00"`), which works in Cloud Shell but **not** on macOS BSD `date`. Run it from Cloud Shell.

## Challenge 6: A2A: Remote Agent Power

### Introduction

In the previous challenge we've learned that we can use tools developed by others, but what about agents? This is where Agent2Agent protocol comes in, it provides a standard way for discovering and utilizing agents developed by others.

### Description

We have already provided a service called `a2a-server` on Cloud Run. It has a single agent deployed that's responsible for stopping the idle resources that have been marked with the `janitor-scheduled` label. You can discover its URL with:

```shell
gcloud run services describe a2a-server --region=us-central1 --format='value(status.url)'
```

Create a new agent `resource_cleaner_agent` that uses A2A protocol to connect to the remote `a2a-server`, and add it to the `orchestrator_agent` sequence as the final step.

> [!TIP]
> **The agent card is NOT at the conventional `/.well-known/agent-card.json`.** The lab's `a2a-server` uses ADK's `fast_api` runner, which mounts each agent under `/a2a/{agent_name}`. So the actual card path is:
>
> ```text
> /a2a/resource_cleaner_agent/.well-known/agent-card.json
> ```
>
> Construct the URL like this:
>
> ```python
> from google.adk.agents.remote_a2a_agent import (
>     AGENT_CARD_WELL_KNOWN_PATH,
>     RemoteA2aAgent,
> )
>
> resource_cleaner_agent = RemoteA2aAgent(
>     name="resource_cleaner_agent",
>     description="Stops idle VMs whose janitor-scheduled label date is in the past.",
>     agent_card=f"http://localhost:8080/a2a/resource_cleaner_agent{AGENT_CARD_WELL_KNOWN_PATH}",
> )
> ```
>
> `description` is required on `RemoteA2aAgent` — it'll raise if you omit it.
>
> If you're unsure of the agent name, find it in the Cloud Run startup logs:
>
> ```shell
> gcloud run services logs read a2a-server --region=us-central1 --limit=200 | grep "Setting up A2A agent"
> ```

> [!TIP]
> **Port 8080 conflicts with `adk web` defaults.** The A2A proxy must be on 8080 (so that the URL inside the agent card resolves correctly). In Cloud Shell, `adk web`'s usual Web Preview port is also 8080. Run `adk web` on a different port instead:
>
> ```shell
> uv run adk web --port 8082 --host 0.0.0.0
> ```
>
> Then click **Web Preview → Change port → 8082**.

### Success Criteria

- The Agent runs all the agents in sequence and stops all the idle resources that have been marked with the `janitor-scheduled` label where the date is in the past, leaving only the following running:

  ```text
  - gce-dev-lnx-tomcat-01
  - gce-dev-lnx-tomcat-02
  - gce-prd-lnx-env-setup
  ```

- The changes have been pushed to your GitHub fork.

### Learning Resources

- [Using A2A Agents in ADK](https://google.github.io/adk-docs/a2a/quickstart-consuming/)

### Tips

- You can use `adk web` UI to view the agents involved.
- You can use a [proxy](https://cloud.google.com/sdk/gcloud/reference/run/services/proxy) to simplify the authentication for the Cloud Run service.
- For this challenge if you're using the Cloud Run proxy, you need to stick to port `8080`.
- You can verify the list of VMs and their state by navigating to the *VM Instances* page in the Google Cloud Console or by using the `gcloud compute instances list` command in Cloud Shell.

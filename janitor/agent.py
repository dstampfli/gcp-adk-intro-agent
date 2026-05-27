from google.adk import Agent
from google.adk.agents import SequentialAgent
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

import janitor.schemas as schemas
import janitor.settings as settings
import janitor.tools as tools


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
       {"vm_instances": [{"project_id": "...", "name": "...", "zone": "...",
                          "status": "...", "machine_type": "..."}, ...]}
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


orchestrator_agent = SequentialAgent(
    name="orchestrator_agent",
    sub_agents=[
        resource_scanner_agent,
        resource_monitor_agent,
        resource_labeler_agent,
    ],
)


# The root_agent is the entry point for the user query.
root_agent = orchestrator_agent

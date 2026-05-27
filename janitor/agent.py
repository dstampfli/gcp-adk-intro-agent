from google.adk import Agent
from google.adk.agents import SequentialAgent

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


orchestrator_agent = SequentialAgent(
    name="orchestrator_agent",
    sub_agents=[resource_scanner_agent, resource_monitor_agent],
)


# The root_agent is the entry point for the user query.
root_agent = orchestrator_agent

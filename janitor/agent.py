from google.adk import Agent

import janitor.schemas as schemas
import janitor.settings as settings
import janitor.tools as tools


resource_scanner_agent = Agent(
    name="resource_scanner_agent",
    model=settings.GEMINI_MODEL,
    instruction="""
    You are a Cloud Resource Scanner.
    Return *all* resources.
    """,
    tools=[tools.get_compute_instances_list],
)

# The root_agent is the entry point for the user query.
root_agent = resource_scanner_agent

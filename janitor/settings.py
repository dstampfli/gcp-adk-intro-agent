GEMINI_MODEL = "gemini-2.5-flash"

# Local proxy to the Cloud Run MCP server. Start with:
#   gcloud run services proxy mcp-server --region=us-central1 --port=8081
MCP_SERVER_URL = "http://localhost:8081/"

# Local proxy to the Cloud Run A2A server. Start with (must use 8080):
#   gcloud run services proxy a2a-server --region=us-central1 --port=8080
# The remote agent is mounted at /a2a/resource_cleaner_agent by ADK's
# fast_api server.
A2A_AGENT_BASE_URL = "http://localhost:8080/a2a/resource_cleaner_agent"

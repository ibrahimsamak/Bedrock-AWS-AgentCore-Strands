"""AgentCore Runtime entrypoint. Exposes POST /invocations and GET /ping on :8080."""
from bedrock_agentcore.runtime import BedrockAgentCoreApp

from orchestrator import build_orchestrator
from progress import emit, set_job

app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload):
    company = payload.get("company") or payload.get("prompt") or ""
    # Progress lines the sub-agents emit will append to this job's DynamoDB record (for the UI).
    set_job(payload.get("job_id"))
    emit(f"🚀 Starting research on {company}…")
    task = (
        f"Produce a cited analyst brief for {company}. Decide which sub-agents to use and in what "
        "order; retrieve filings first if you have no passages yet, and return the writer's brief "
        "(with [n] citations and a Sources list) verbatim as your final answer."
    )
    # Fresh orchestrator per request → fresh sub-agent state + a fresh sub-agent-call budget.
    orchestrator = build_orchestrator()
    result = orchestrator(task)
    emit("✅ Brief ready.")
    return {"status": "COMPLETED", "company": company, "brief": str(result)}


if __name__ == "__main__":
    app.run()
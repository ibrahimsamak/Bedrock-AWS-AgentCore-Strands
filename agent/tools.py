import boto3

from strands import tool

from config import cfg
from market import lookup_market_data
from progress import emit

_agent_rt = None


def _kb_client():
    global _agent_rt
    if _agent_rt is None:
        _agent_rt = boto3.client("bedrock-agent-runtime", region_name=cfg.region)
    return _agent_rt


@tool
def retrieve_filings(query: str, company: str) -> str:
    emit(f"Searching {company} filings for: {query}")
    resp = _kb_client().retrieve(
        knowledgeBaseId=cfg.kb_id,
        retrievalQuery={"text": query},
        retrievalConfiguration={
            "managedSearchConfiguration": {
                "numberOfResults": cfg.retrieve_top_k,
            }
        },
    )
    lines = []
    for i, r in enumerate(resp.get("retrievalResults", []), start=1):
        text = r.get("content", {}).get("text", "")
        uri = r.get("location", {}).get("s3Location", {}).get("uri", "unknown")
        score = r.get("score", 0.0)
        lines.append(f"[{i}] (source: {uri}, score {score:.3f})\n{text}")
    return "\n\n".join(lines) if lines else "No relevant passages found."


@tool
def market_data(ticker: str) -> str:
    emit(f"Checking market data for {ticker.strip().upper()}")
    return lookup_market_data(ticker)

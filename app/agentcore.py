import json
import os

import boto3
from botocore.config import Config

from .config import settings

_client = None

# The graph runs for minutes; boto3's default read timeout is 60s, which would abort a
# real run. Give the synchronous invoke headroom and disable client-side retries so a
# slow run isn't fired twice. Keep this <= the SQS visibility timeout (deploy §5.4).
_INVOKE_TIMEOUT = int(os.getenv("AGENT_INVOKE_TIMEOUT", "900"))


def _agentcore():
    global _client
    if _client is None:
        _client = boto3.client(
            "bedrock-agentcore",
            region_name=settings.aws_region,
            config=Config(
                connect_timeout=10,
                read_timeout=_INVOKE_TIMEOUT,
                retries={"max_attempts": 0},
            ),
        )
    return _client


def run_brief(company: str, job_id: str) -> str:
    """Invoke the agent and return the brief text.

    `job_id` is sent in the payload (so the agent can append live progress to that DynamoDB
    record) and reused as the runtimeSessionId (must be >= 33 chars; a job UUID is 36).
    Locally (compose) there is no deployed Runtime, so when AGENT_LOCAL_URL is set we POST
    straight to the agent container's /invocations endpoint instead.
    """
    local = os.getenv("AGENT_LOCAL_URL")
    if local:
        import requests  # local-only dependency (see app/requirements.txt)

        r = requests.post(local, json={"company": company, "job_id": job_id}, timeout=_INVOKE_TIMEOUT)
        r.raise_for_status()
        return r.json().get("brief", r.text)

    payload = json.dumps({"company": company, "job_id": job_id}).encode()
    resp = _agentcore().invoke_agent_runtime(
        agentRuntimeArn=settings.agent_runtime_arn,
        runtimeSessionId=job_id,
        payload=payload,
    )
    raw = resp["response"].read()
    data = json.loads(raw.decode("utf-8"))
    return data.get("brief", str(data))

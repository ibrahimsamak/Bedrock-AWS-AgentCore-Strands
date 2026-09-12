import json
import os

import boto3
from botocore.config import Config

from .config import settings

_client = None

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
    local = os.getenv("AGENT_LOCAL_URL")
    if local:
        import requests

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

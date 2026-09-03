"""Best-effort live progress feed.

The orchestrator's sub-agent tools call emit() with a short, friendly line describing what the
agent just decided ("pulling filings", "analyzing", "drafting"). Each line is appended to the
job's DynamoDB `steps` list, which the Gradio UI polls and renders under the user's message.
Writes are best-effort — a failed status line never fails the run.
"""
import contextvars
import time

import boto3

from config import cfg

# Primary: per-request contextvar. Fallback: module global, in case the agent framework runs a
# tool in a worker thread the contextvar didn't propagate to (progress is cosmetic either way).
_job_ctx = contextvars.ContextVar("job_id", default=None)
_job_fallback = None
_table = None


def set_job(job_id) -> None:
    global _job_fallback
    _job_fallback = job_id or None
    _job_ctx.set(_job_fallback)


def _tbl():
    global _table
    if _table is None:
        kw = {"region_name": cfg.region}
        if cfg.ddb_endpoint_url:
            kw["endpoint_url"] = cfg.ddb_endpoint_url
        _table = boto3.resource("dynamodb", **kw).Table(cfg.jobs_table)
    return _table


def emit(text: str) -> None:
    """Append one friendly status line to the job's `steps` list. Never raises."""
    job_id = _job_ctx.get() or _job_fallback
    if not job_id or not cfg.jobs_table:
        return
    try:
        _tbl().update_item(
            Key={"job_id": job_id},
            UpdateExpression="SET #s = list_append(if_not_exists(#s, :empty), :new)",
            ExpressionAttributeNames={"#s": "steps"},
            ExpressionAttributeValues={
                ":empty": [],
                ":new": [{"t": int(time.time()), "text": text}],
            },
        )
    except Exception:
        pass  # best-effort — never fail the run over a progress line

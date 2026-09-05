import contextvars
import time

import boto3

from config import cfg

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
        pass

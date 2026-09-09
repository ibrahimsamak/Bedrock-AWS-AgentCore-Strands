import time

import boto3

from .config import settings

_table = None


def _tbl():
    global _table
    if _table is None:
        kw = {"region_name": settings.aws_region}
        if settings.aws_endpoint_url:
            kw["endpoint_url"] = settings.aws_endpoint_url
        _table = boto3.resource("dynamodb", **kw).Table(settings.jobs_table)
    return _table


def put_pending(job_id: str, company: str) -> None:
    now = int(time.time())
    _tbl().put_item(
        Item={
            "job_id": job_id,
            "status": "PENDING",
            "company": company,
            "steps": [],
            "created_at": now,
            "updated_at": now,
        }
    )


def update(job_id: str, status: str, *, result: str | None = None, error: str | None = None) -> None:
    expr = "SET #s = :s, updated_at = :u"
    vals = {":s": status, ":u": int(time.time())}
    names = {"#s": "status"}
    if result is not None:
        expr += ", #r = :r"
        vals[":r"] = result
        names["#r"] = "result"
    if error is not None:
        expr += ", #e = :e"
        vals[":e"] = error
        names["#e"] = "error"
    _tbl().update_item(
        Key={"job_id": job_id},
        UpdateExpression=expr,
        ExpressionAttributeValues=vals,
        ExpressionAttributeNames=names,
    )


def get(job_id: str) -> dict | None:
    return _tbl().get_item(Key={"job_id": job_id}).get("Item")

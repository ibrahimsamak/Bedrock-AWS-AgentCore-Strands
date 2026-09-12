import json

import boto3

from .config import settings

_sqs = None


def _client():
    global _sqs
    if _sqs is None:
        kw = {"region_name": settings.aws_region}
        if settings.aws_endpoint_url:
            kw["endpoint_url"] = settings.aws_endpoint_url
        _sqs = boto3.client("sqs", **kw)
    return _sqs


def send(job_id: str, company: str) -> None:
    _client().send_message(
        QueueUrl=settings.jobs_queue_url,
        MessageBody=json.dumps({"job_id": job_id, "company": company}),
    )


def receive(wait_seconds: int = 20):
    resp = _client().receive_message(
        QueueUrl=settings.jobs_queue_url,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=wait_seconds,
    )
    return resp.get("Messages", [])


def delete(receipt_handle: str) -> None:
    _client().delete_message(QueueUrl=settings.jobs_queue_url, ReceiptHandle=receipt_handle)

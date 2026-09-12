import uuid

from . import ddb, sqs


def create_job(company: str) -> str:
    job_id = str(uuid.uuid4())
    ddb.put_pending(job_id, company)
    sqs.send(job_id, company)
    return job_id


def get_job(job_id: str) -> dict | None:
    return ddb.get(job_id)

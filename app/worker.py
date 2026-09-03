"""SQS consumer: pull a job, invoke the AgentCore Runtime, persist the result."""
import json
import time

from . import agentcore, ddb, sqs


def handle(message: dict) -> None:
    body = json.loads(message["Body"])
    job_id, company = body["job_id"], body["company"]
    ddb.update(job_id, "RUNNING")
    try:
        brief = agentcore.run_brief(company, job_id=job_id)
        ddb.update(job_id, "DONE", result=brief)
    except Exception as e:  # noqa: BLE001 — surface any failure to the job record
        ddb.update(job_id, "FAILED", error=str(e))


def main() -> None:
    print("worker: polling SQS...", flush=True)
    while True:
        msgs = sqs.receive(wait_seconds=20)
        if not msgs:
            time.sleep(1)
            continue
        for m in msgs:
            handle(m)
            sqs.delete(m["ReceiptHandle"])


if __name__ == "__main__":
    main()

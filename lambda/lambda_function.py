from app import worker


def handler(event, _context):
    failures = []
    for record in event.get("Records", []):
        try:
            worker.handle({"Body": record["body"]})
        except Exception as e:
            print(f"job failed before it could be marked: {e}", flush=True)
            failures.append({"itemIdentifier": record["messageId"]})
    return {"batchItemFailures": failures}

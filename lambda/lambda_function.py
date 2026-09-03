"""
AWS Lambda handler for processing analyst jobs from SQS.
Replaces the background ECS worker with serverless Lambda.

Triggered by: SQS queue (analyst-jobs)
Timeout: 15 minutes (Lambda maximum)

Reuses existing app functions for DynamoDB updates, progress tracking, and agent invocation.
"""
import json
import logging
import sys
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Add app directory to path so we can import shared modules
app_dir = os.path.join(os.path.dirname(__file__), "..")
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

# Import shared functions from app (DRY - Don't Repeat Yourself)
from app import ddb, agentcore, progress


def process_sqs_message(record: dict) -> bool:
    """
    Process a single SQS message.

    Reuses app.ddb, app.agentcore, and app.progress modules for all operations.

    Returns: True if successful, False if failed
    """
    try:
        # Parse message
        body = json.loads(record["body"])
        job_id = body.get("job_id")
        company = body.get("company")

        if not job_id or not company:
            logger.error("Invalid message: missing job_id or company")
            return False

        logger.info(f"Processing job {job_id} for company {company}")

        # Mark job as RUNNING (reuse existing ddb.update)
        ddb.update(job_id, "RUNNING")

        # Set job context for progress.emit() to append steps
        progress.set_job(job_id)

        # Invoke agent runtime (reuse existing agentcore.run_brief)
        # This function internally calls progress.emit() for live updates
        brief = agentcore.run_brief(company, job_id)

        # Save result (reuse existing ddb.update)
        ddb.update(job_id, "DONE", result=brief)

        logger.info(f"Job {job_id} completed successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to process message: {str(e)}")

        # Try to update job with error status (reuse existing ddb.update)
        try:
            body = json.loads(record["body"])
            job_id = body.get("job_id")
            if job_id:
                ddb.update(job_id, "FAILED", error=str(e))
        except Exception as inner_e:
            logger.error(f"Failed to update job error status: {str(inner_e)}")

        return False


def lambda_handler(event, _context):
    """
    AWS Lambda handler function.

    Triggered by SQS messages from the analyst-jobs queue.

    Event structure:
    {
        "Records": [
            {
                "body": '{"job_id": "...", "company": "Apple"}',
                "receiptHandle": "...",
                ...
            }
        ]
    }
    """
    logger.info(f"Received {len(event.get('Records', []))} messages")

    results = {
        "successful": 0,
        "failed": 0,
        "batchItemFailures": []
    }

    # Process each message
    for record in event.get("Records", []):
        try:
            success = process_sqs_message(record)
            if success:
                results["successful"] += 1
                logger.info(f"Message processed successfully")
            else:
                results["failed"] += 1
                # Add to batch failures so Lambda can retry
                results["batchItemFailures"].append({
                    "itemId": record["messageId"]
                })
        except Exception as e:
            logger.error(f"Unhandled exception: {str(e)}")
            results["failed"] += 1
            results["batchItemFailures"].append({
                "itemId": record["messageId"]
            })

    logger.info(f"Processing complete: {results['successful']} successful, {results['failed']} failed")

    # Return batch failures so Lambda retries them
    return {
        "statusCode": 200,
        "body": json.dumps(results),
        "batchItemFailures": results["batchItemFailures"]
    }

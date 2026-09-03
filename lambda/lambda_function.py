"""
AWS Lambda handler for processing analyst jobs from SQS.
Replaces the background ECS worker with serverless Lambda.

Triggered by: SQS queue (analyst-jobs)
Timeout: 15 minutes (Lambda maximum)
"""
import json
import logging
import os
import boto3
import time
from botocore.config import Config

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS Clients
ddb_resource = boto3.resource("dynamodb")
agentcore_client = boto3.client("bedrock-agentcore")

# Configuration
JOBS_TABLE = os.environ.get("JOBS_TABLE", "analyst-jobs")
AGENT_RUNTIME_ARN = os.environ.get("AGENT_RUNTIME_ARN")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
AGENT_INVOKE_TIMEOUT = int(os.environ.get("AGENT_INVOKE_TIMEOUT", "900"))

jobs_table = ddb_resource.Table(JOBS_TABLE)


def update_job_status(job_id: str, status: str, **kwargs):
    """Update job status in DynamoDB."""
    try:
        update_expr = "SET #status = :status"
        expr_names = {"#status": "status"}
        expr_values = {":status": status}

        for key, val in kwargs.items():
            expr_names[f"#{key}"] = key
            expr_values[f":{key}"] = val
            update_expr += f", #{key} = :{key}"

        jobs_table.update_item(
            Key={"job_id": job_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values,
        )
        logger.info(f"Updated job {job_id} status: {status}")
    except Exception as e:
        logger.error(f"Failed to update job {job_id}: {str(e)}")
        raise


def append_progress_step(job_id: str, step_text: str):
    """Append a progress step to the job's steps list."""
    try:
        jobs_table.update_item(
            Key={"job_id": job_id},
            UpdateExpression="SET #steps = list_append(if_not_exists(#steps, :empty), :new)",
            ExpressionAttributeNames={"#steps": "steps"},
            ExpressionAttributeValues={
                ":empty": [],
                ":new": [{"t": int(time.time()), "text": step_text}],
            },
        )
        logger.info(f"Job {job_id} progress: {step_text}")
    except Exception as e:
        logger.error(f"Failed to append progress for {job_id}: {str(e)}")


def invoke_agentcore_runtime(company: str, job_id: str) -> str:
    """
    Invoke the Bedrock AgentCore Runtime synchronously.

    Returns: The brief text from the agent
    Raises: Exception if invocation fails or times out
    """
    try:
        logger.info(f"Invoking AgentCore Runtime for {company} (job_id={job_id})")
        append_progress_step(job_id, f"🚀 Starting research on {company}…")

        payload = json.dumps({
            "company": company,
            "job_id": job_id
        }).encode()

        # Invoke agent runtime with custom timeout
        config = Config(
            connect_timeout=10,
            read_timeout=AGENT_INVOKE_TIMEOUT,
            retries={"max_attempts": 0},
        )
        client = boto3.client("bedrock-agentcore", region_name=AWS_REGION, config=config)

        response = client.invoke_agent_runtime(
            agentRuntimeArn=AGENT_RUNTIME_ARN,
            runtimeSessionId=job_id,  # Use job_id as session ID
            payload=payload,
        )

        # Read response
        response_data = json.loads(response["response"].read().decode("utf-8"))
        brief = response_data.get("brief", "")

        logger.info(f"Agent completed for job {job_id}, brief length: {len(brief)}")
        append_progress_step(job_id, "✅ Brief ready.")

        return brief

    except Exception as e:
        logger.error(f"AgentCore Runtime invocation failed: {str(e)}")
        append_progress_step(job_id, f"❌ Error: {str(e)}")
        raise


def process_sqs_message(record: dict) -> bool:
    """
    Process a single SQS message.

    Returns: True if successful, False if failed
    """
    try:
        # Parse message
        body = json.loads(record["body"])
        job_id = body.get("job_id")
        company = body.get("company")

        if not job_id or not company:
            logger.error(f"Invalid message: missing job_id or company")
            return False

        logger.info(f"Processing job {job_id} for company {company}")

        # Update job status to RUNNING
        update_job_status(job_id, "RUNNING")

        # Invoke agent runtime
        brief = invoke_agentcore_runtime(company, job_id)

        # Save result
        update_job_status(job_id, "DONE", result=brief)

        logger.info(f"Job {job_id} completed successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to process message: {str(e)}")

        # Try to update job with error status
        try:
            body = json.loads(record["body"])
            job_id = body.get("job_id")
            if job_id:
                update_job_status(job_id, "FAILED", error=str(e))
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

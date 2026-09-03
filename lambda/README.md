# Lambda + SQS Job Processor

Alternative to the ECS worker (`app/worker.py`) that processes analyst jobs asynchronously.

## Why Lambda + SQS?

| Aspect | ECS Worker | Lambda + SQS |
|--------|-----------|------------|
| **Scaling** | Manual (desired_count) | Auto-scales (0 → N) |
| **Cost when idle** | Always running (~$20/mo) | $0 |
| **Event-driven** | Polling every 20s | Immediate invocation |
| **Max duration** | Unlimited | 15 minutes (hard limit) |
| **Best for** | Long-running tasks (5+ min) | Short-to-medium tasks |

**Note:** This project's agent takes ~5 minutes, which fits within Lambda's 900s timeout. However, if your agent approaches the 15-minute limit, stick with the ECS worker.

---

## Deployment

### 1. Package the Function

```bash
cd lambda
zip lambda_function.zip lambda_function.py
```

No external dependencies to vendor (boto3 is built into the Lambda runtime).

### 2. Create IAM Execution Role

The Lambda function needs permissions to:
- Read/update DynamoDB
- Invoke AgentCore Runtime
- Write logs

Create a role with inline policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:UpdateItem",
        "dynamodb:GetItem"
      ],
      "Resource": "arn:aws:dynamodb:us-east-1:ACCOUNT_ID:table/analyst-jobs"
    },
    {
      "Effect": "Allow",
      "Action": [
        "bedrock-agentcore:InvokeAgentRuntime"
      ],
      "Resource": "arn:aws:bedrock:us-east-1:ACCOUNT_ID:agent-runtime/RUNTIME_ID"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:us-east-1:ACCOUNT_ID:log-group:/aws/lambda/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:GetQueueAttributes",
        "sqs:ChangeMessageVisibility"
      ],
      "Resource": "arn:aws:sqs:us-east-1:ACCOUNT_ID:analyst-jobs"
    }
  ]
}
```

Replace:
- `ACCOUNT_ID` — your AWS account ID
- `analyst-jobs` — your table name (from `.env`)
- `RUNTIME_ID` — your AgentCore Runtime ARN

### 3. Create Lambda Function

```bash
aws lambda create-function \
  --function-name analyst-job-processor \
  --runtime python3.12 \
  --role arn:aws:iam::ACCOUNT_ID:role/analyst-lambda-role \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://lambda_function.zip \
  --timeout 900 \
  --memory-size 256 \
  --environment Variables="{
    JOBS_TABLE=analyst-jobs,
    AGENT_RUNTIME_ARN=arn:aws:bedrock:us-east-1:ACCOUNT_ID:...,
    AWS_REGION=us-east-1,
    AGENT_INVOKE_TIMEOUT=840
  }" \
  --region us-east-1
```

**Environment Variables:**
- `JOBS_TABLE` — DynamoDB table name
- `AGENT_RUNTIME_ARN` — Full ARN of your AgentCore Runtime
- `AWS_REGION` — AWS region
- `AGENT_INVOKE_TIMEOUT` — Max seconds to wait for agent (default 840 = 14 min, leaving 1 min buffer before Lambda timeout)

**Memory:** 256 MB is plenty (boto3 I/O is the bottleneck, not CPU).

**Timeout:** 900 seconds (15 minutes, Lambda maximum).

### 4. Wire SQS to Lambda

```bash
aws lambda create-event-source-mapping \
  --event-source-arn arn:aws:sqs:us-east-1:ACCOUNT_ID:analyst-jobs \
  --function-name analyst-job-processor \
  --batch-size 1 \
  --function-response-types ReportBatchItemFailures \
  --region us-east-1
```

**Options:**
- `--batch-size 1` — Process one message at a time (recommended for long-running tasks)
- `--function-response-types ReportBatchItemFailures` — Only retry failed messages; successful ones are auto-deleted

### 5. Verify Deployment

```bash
# Check Lambda function
aws lambda get-function --function-name analyst-job-processor --region us-east-1

# Check event source mapping
aws lambda list-event-source-mappings \
  --function-name analyst-job-processor \
  --region us-east-1
```

---

## Testing

### Send a Test Message

```bash
aws sqs send-message \
  --queue-url https://sqs.us-east-1.amazonaws.com/ACCOUNT_ID/analyst-jobs \
  --message-body '{"job_id":"test-lambda-001","company":"Apple"}' \
  --region us-east-1
```

### Monitor Execution

```bash
# Check CloudWatch logs
aws logs tail /aws/lambda/analyst-job-processor --follow --region us-east-1

# Check DynamoDB job record
aws dynamodb get-item \
  --table-name analyst-jobs \
  --key '{"job_id":{"S":"test-lambda-001"}}' \
  --region us-east-1
```

Expected flow:
1. Job created with `status: PENDING`
2. Lambda triggered by SQS message
3. Job transitioned to `status: RUNNING`
4. Agent invoked, progress steps appended
5. Job updated to `status: DONE` with `result` field
6. SQS message auto-deleted

---

## Debugging

### Lambda Timeout (900s exceeded)

If you see `Task timed out after 900 seconds`:
- Agent runtime took longer than expected
- Agent's `AGENT_INVOKE_TIMEOUT` was too high
- Consider lowering `AGENT_INVOKE_TIMEOUT` in env vars (e.g., 840s) to leave buffer

**Unlike the ECS worker, there is no "keep waiting"** — Lambda kills the invocation after 900s, and the SQS message returns to the queue for retry.

### Agent Runtime Invocation Failed

If `bedrock-agentcore:InvokeAgentRuntime` fails:
- Check `AGENT_RUNTIME_ARN` is correct and matches your runtime
- Verify IAM role has `bedrock-agentcore:InvokeAgentRuntime` permission
- Check agent runtime is running (not deleted)

### DynamoDB Update Failed

If progress steps don't appear:
- Verify IAM role has `dynamodb:UpdateItem` permission
- Check `JOBS_TABLE` env var matches your table name
- Ensure table is in same region as Lambda

---

## Comparing to ECS Worker

**ECS Worker (`app/worker.py`)**
```python
while True:
    msgs = sqs.receive()  # Poll every 20 seconds
    if msgs:
        handle(m)         # Process synchronously
```

**Lambda + SQS**
```python
def lambda_handler(event, _context):  # AWS calls this immediately when SQS message arrives
    for record in event["Records"]:
        handle(record)                 # Process synchronously
```

Both use the same agent invocation and progress-update logic. The difference is the trigger model:
- ECS = polling (you call SQS repeatedly)
- Lambda = event-driven (AWS calls your function when a message arrives)

---

## Scaling Down

To switch back to the ECS worker:
1. Delete the Lambda function: `aws lambda delete-function --function-name analyst-job-processor`
2. Delete the event source mapping: `aws lambda delete-event-source-mapping --uuid <UUID>`
3. Ensure ECS worker is running: `aws ecs update-service --cluster analyst-cluster --service analyst-worker --desired-count 2`

The ECS worker will resume polling SQS immediately.

---

## Cost Estimate

For 100 jobs/day @ ~5 minutes each:

**Lambda + SQS:**
- Lambda: 100 invocations × 5 min × (256MB / 1024) GB = $0.005/month
- SQS: 100 messages × $0.40 per million = negligible
- **Total: ~$0.01/month** (just CloudWatch logs)

**ECS Worker (on-demand):**
- 2 vCPUs running 24/7: ~$20/month

**Savings: ~99.95%** when idle, but requires accepting the 15-minute timeout constraint.

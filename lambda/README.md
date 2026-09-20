# Lambda worker

Same job as `app/worker.py` but triggered by SQS instead of polling it. It calls `worker.handle`, so the RUNNING / DONE / FAILED updates are exactly the same as the ECS worker. I added it because the worker sits idle most of the time and Lambda costs nothing then.

A brief takes about a minute, well under Lambda's 15 minute limit. If the agent ever gets close to that, use the ECS worker.

## Package

The function needs the `app` package and `pydantic-settings` (boto3 is already in the runtime):

```bash
rm -rf build && mkdir build
pip install -r lambda/requirements.txt -t build \
  --platform manylinux2014_x86_64 --only-binary=:all: --python-version 3.12
cp -r app build/
cp lambda/lambda_function.py build/
(cd build && zip -qr ../lambda.zip .)
```

## Deploy

- runtime python3.12, handler `lambda_function.handler`, timeout 900s
- env: `JOBS_TABLE`, `AGENT_RUNTIME_ARN` (AWS_REGION is set by Lambda)
- role: `AWSLambdaBasicExecutionRole`, plus `dynamodb:UpdateItem` on the jobs table, `bedrock-agentcore:InvokeAgentRuntime` on the runtime, and `sqs:ReceiveMessage`, `sqs:DeleteMessage`, `sqs:GetQueueAttributes` on the queue
- SQS trigger on `analyst-jobs` with batch size 1 and "report batch item failures" on
- the queue's visibility timeout has to be at least the function timeout, otherwise the message comes back while the job is still running

Scale the ECS worker to 0 when using this, otherwise both pick up jobs.

A failed agent run is marked FAILED in DynamoDB and not retried (same as the worker). Only errors before that, like DynamoDB being unreachable, go back to the queue.

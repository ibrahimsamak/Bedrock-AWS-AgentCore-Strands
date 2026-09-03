import os


class Config:
    region = os.getenv("AWS_REGION", "us-east-1")
    model_id = os.getenv("BEDROCK_MODEL_ID", "us.amazon.nova-2-lite-v1:0")
    kb_id = os.getenv("KB_ID", "")
    retrieve_top_k = int(os.getenv("RETRIEVE_TOP_K", "6"))
    guardrail_id = os.getenv("GUARDRAIL_ID", "")
    guardrail_version = os.getenv("GUARDRAIL_VERSION", "DRAFT")
    max_subagent_calls = int(os.getenv("MAX_SUBAGENT_CALLS", "8"))
    model_max_tokens = int(os.getenv("MODEL_MAX_TOKENS", "1200"))
    jobs_table = os.getenv("JOBS_TABLE", "")
    ddb_endpoint_url = os.getenv("DDB_ENDPOINT_URL", "")


cfg = Config()

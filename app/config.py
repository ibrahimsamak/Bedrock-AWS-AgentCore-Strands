from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    aws_region: str = "us-east-1"
    jobs_table: str = "analyst-jobs"
    jobs_queue_url: str = ""
    agent_runtime_arn: str = ""
    filings_bucket: str = ""
    aws_endpoint_url: str = ""


settings = Settings()

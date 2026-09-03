# Seed data

Sample data to get Project 3 running end-to-end without hunting for real filings.

```
seed/
├── companies.json                 # name/alias → ticker reference data
├── seed_db.py                     # load companies.json into a DynamoDB `companies` table
└── filings/                       # synthetic 10-K markdown docs (with KB metadata sidecars)
    ├── apple/
    │   ├── apple-10k.md
    │   └── apple-10k.md.metadata.json          # {"metadataAttributes": {"company": "Apple"}}
    └── microsoft/
        ├── microsoft-10k.md
        └── microsoft-10k.md.metadata.json      # {"metadataAttributes": {"company": "Microsoft"}}
```

The two companies (Apple/AAPL, Microsoft/MSFT) match the mock `market_data` tool, so a submitted
brief exercises retrieval **and** the market-data path with real-looking numbers. All filing
figures are **synthetic** — demo/testing only.

## 1. Seed the Knowledge Base (md docs → S3 → KB)

Each markdown doc ships with a `<file>.metadata.json` sidecar tagging its `company`, so the
`retrieve_filings` tool can filter by company (deploy §5.1). Upload preserving the sidecars:

```bash
# Uploads both the .md files and their .metadata.json sidecars in one shot.
aws s3 sync seed/filings/ "s3://$FILINGS_BUCKET/filings/"
```

Then **Sync** the Knowledge Base data source in the console (or `aws bedrock-agent
start-ingestion-job ...`). Alternatively, `python -m scripts.upload_filings Apple seed/filings/apple/apple-10k.md`
generates the sidecar for you (one company at a time).

## 2. Seed the companies table (name → ticker)

```bash
# local (LocalStack via docker-compose)
AWS_REGION=us-east-1 AWS_ENDPOINT_URL=http://localhost:4566 python seed/seed_db.py

# real AWS
AWS_REGION=us-east-1 COMPANIES_TABLE=companies python seed/seed_db.py
```

This creates/fills a DynamoDB `companies` table keyed on a lowercased `name_key` (display name
+ aliases), each row carrying `ticker`, `exchange`, `sector`.

### Using it in the agent (optional — fixes the name→ticker gap)

The UI takes a company *name* but `market_data` keys on a *ticker*. Add a resolver tool so the
Analyst maps "Apple" → "AAPL" before calling `market_data`. In `agent/tools.py`:

```python
@tool
def resolve_ticker(company: str) -> str:
    """Return the stock ticker for a company name (e.g. 'Apple' -> 'AAPL')."""
    import boto3
    from config import cfg
    tbl = boto3.resource("dynamodb", region_name=cfg.region).Table(cfg.companies_table)
    item = tbl.get_item(Key={"name_key": company.strip().lower()}).get("Item")
    return item["ticker"] if item else company
```

Then give the Analyst `tools=[market_data, resolve_ticker]`, add `companies_table` to
`agent/config.py`, and grant the AgentCore execution role `dynamodb:GetItem` on the table. If you
skip this, `market_data` still returns a generic stub for unknown tickers.

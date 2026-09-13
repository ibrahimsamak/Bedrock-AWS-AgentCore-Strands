# Seed data

Two synthetic 10-Ks (Apple and Microsoft) so the whole flow can run without real filings. The numbers are made up, demo only. They match the tickers the mock `market_data` tool knows (AAPL, MSFT).

- `filings/<company>/*.md` the filings
- `filings/<company>/*.md.metadata.json` sets the `company` attribute the retriever filters on
- `companies.json` names/aliases -> ticker
- `seed_db.py` loads `companies.json` into a DynamoDB `companies` table

## Knowledge Base

```bash
aws s3 sync seed/filings/ "s3://$FILINGS_BUCKET/filings/"
```

`s3 sync` uploads the `.metadata.json` files too. Then sync the data source in the console. For a single file you can also use `python -m scripts.upload_filings Apple seed/filings/apple/apple-10k.md`, it writes the metadata file for you.

## Companies table

```bash
# localstack
AWS_REGION=us-east-1 AWS_ENDPOINT_URL=http://localhost:4566 python seed/seed_db.py

# aws
AWS_REGION=us-east-1 COMPANIES_TABLE=companies python seed/seed_db.py
```

Each name and alias is stored lowercased as `name_key`, with `ticker`, `exchange` and `sector`.

The agent doesn't use this table yet. The UI sends a company name but `market_data` wants a ticker, so the next step is a small `resolve_ticker` tool that looks the name up here (the agent role would need `dynamodb:GetItem` on the table). Until then unknown tickers just get a generic stub.

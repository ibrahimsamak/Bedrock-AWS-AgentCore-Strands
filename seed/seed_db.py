"""Seed a DynamoDB `companies` reference table (name/alias -> ticker) from companies.json.

Fixes the name->ticker gap: the UI takes a company name ("Apple") but the market_data tool
keys on a ticker ("AAPL"). The agent (or the worker) can resolve name -> ticker via this table.

Runs against LocalStack (compose) or real AWS. Idempotent: re-running overwrites items.

    # local (LocalStack)
    AWS_REGION=us-east-1 AWS_ENDPOINT_URL=http://localhost:4566 python seed_db.py

    # real AWS (omit AWS_ENDPOINT_URL)
    AWS_REGION=us-east-1 COMPANIES_TABLE=companies python seed_db.py
"""
import json
import os
import pathlib

import boto3

REGION = os.getenv("AWS_REGION", "us-east-1")
ENDPOINT = os.getenv("AWS_ENDPOINT_URL") or None
TABLE = os.getenv("COMPANIES_TABLE", "companies")

HERE = pathlib.Path(__file__).parent


def _dynamodb():
    kw = {"region_name": REGION}
    if ENDPOINT:
        kw["endpoint_url"] = ENDPOINT
    return boto3.resource("dynamodb", **kw)


def ensure_table(ddb):
    if TABLE in [t.name for t in ddb.tables.all()]:
        return ddb.Table(TABLE)
    table = ddb.create_table(
        TableName=TABLE,
        AttributeDefinitions=[{"AttributeName": "name_key", "AttributeType": "S"}],
        KeySchema=[{"AttributeName": "name_key", "KeyType": "HASH"}],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    return table


def main():
    companies = json.loads((HERE / "companies.json").read_text())
    table = ensure_table(_dynamodb())
    n = 0
    # One row per name + alias, all pointing at the same ticker, so lookups are
    # case-insensitive on either the display name or any alias.
    with table.batch_writer() as batch:
        for c in companies:
            for key in {c["name"], *c.get("aliases", [])}:
                batch.put_item(
                    Item={
                        "name_key": key.strip().lower(),
                        "display_name": c["name"],
                        "ticker": c["ticker"],
                        "exchange": c.get("exchange", ""),
                        "sector": c.get("sector", ""),
                    }
                )
                n += 1
    print(f"seeded {n} rows into '{TABLE}' from {len(companies)} companies")


if __name__ == "__main__":
    main()

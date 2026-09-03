"""Dev helper: upload local filings to the S3 bucket the Knowledge Base points at.

Also writes a `<key>.metadata.json` sidecar tagging each file with its company, so the
Knowledge Base can filter retrieval by company (see the retrieve_filings tool + deploy §5.1).
"""
import json
import os
import sys
import tempfile

import boto3

from app.config import settings


def main():
    if len(sys.argv) < 3:
        print("usage: python -m scripts.upload_filings <company> <file1> [file2 ...]")
        raise SystemExit(1)
    company, paths = sys.argv[1], sys.argv[2:]
    s3 = boto3.client("s3", region_name=settings.aws_region)
    for path in paths:
        key = f"filings/{path.rsplit('/', 1)[-1]}"
        s3.upload_file(path, settings.filings_bucket, key)
        # Sidecar: Bedrock KB reads <key>.metadata.json for filterable attributes.
        meta = {"metadataAttributes": {"company": company}}
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump(meta, tmp)
        tmp.close()
        s3.upload_file(tmp.name, settings.filings_bucket, f"{key}.metadata.json")
        os.unlink(tmp.name)
        print(f"uploaded s3://{settings.filings_bucket}/{key} (company={company})")
    print("Now re-sync the Knowledge Base (console → Data source → Sync).")


if __name__ == "__main__":
    main()

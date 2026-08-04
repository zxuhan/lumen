import asyncio
from functools import lru_cache

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.config import get_settings


@lru_cache
def _client(endpoint: str | None = None):
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=endpoint or settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        config=Config(signature_version="s3v4"),
        region_name=settings.s3_region,
    )


def ensure_bucket() -> None:
    """Create the bucket on first run (local MinIO). An R2 bucket is created in the dashboard,
    and a token scoped to its objects may be refused a look at the bucket itself; then reading
    an object proves the credentials work instead."""
    bucket = get_settings().s3_bucket
    try:
        _client().head_bucket(Bucket=bucket)
    except ClientError as exc:
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if status == 403:
            _probe_objects(bucket)
        elif status == 404:
            _client().create_bucket(Bucket=bucket)
        else:
            raise


def _probe_objects(bucket: str) -> None:
    try:
        _client().head_object(Bucket=bucket, Key=".probe")
    except ClientError as exc:
        # Not found means the request was authorized; anything else is a real failure
        if exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") != 404:
            raise


async def put(key: str, data: bytes, content_type: str) -> None:
    await asyncio.to_thread(
        _client().put_object,
        Bucket=get_settings().s3_bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
    )


async def get(key: str) -> bytes:
    response = await asyncio.to_thread(
        _client().get_object, Bucket=get_settings().s3_bucket, Key=key
    )
    return response["Body"].read()


async def delete(key: str) -> None:
    await asyncio.to_thread(_client().delete_object, Bucket=get_settings().s3_bucket, Key=key)


def signed_url(key: str) -> str:
    """Generate a short-lived signed URL. Computed locally, with no network request."""
    settings = get_settings()
    return _client(settings.s3_public_endpoint or None).generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=settings.s3_url_ttl,
    )

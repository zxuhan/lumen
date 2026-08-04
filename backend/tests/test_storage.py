import pytest
from botocore.exceptions import ClientError
from botocore.stub import Stubber

from app import storage
from app.config import get_settings


@pytest.fixture
def s3():
    with Stubber(storage._client()) as stub:
        yield stub
        stub.assert_no_pending_responses()


def test_missing_bucket_is_created(s3):
    bucket = get_settings().s3_bucket
    s3.add_client_error("head_bucket", http_status_code=404, expected_params={"Bucket": bucket})
    s3.add_response("create_bucket", {}, {"Bucket": bucket})

    storage.ensure_bucket()


def test_bucket_scoped_token_is_checked_through_an_object(s3):
    """R2 tokens limited to one bucket's objects can't look at the bucket or create one."""
    bucket = get_settings().s3_bucket
    s3.add_client_error("head_bucket", http_status_code=403, expected_params={"Bucket": bucket})
    s3.add_client_error(
        "head_object", http_status_code=404, expected_params={"Bucket": bucket, "Key": ".probe"}
    )

    storage.ensure_bucket()


def test_rejected_credentials_still_fail(s3):
    bucket = get_settings().s3_bucket
    s3.add_client_error("head_bucket", http_status_code=403, expected_params={"Bucket": bucket})
    s3.add_client_error(
        "head_object", http_status_code=403, expected_params={"Bucket": bucket, "Key": ".probe"}
    )

    with pytest.raises(ClientError):
        storage.ensure_bucket()

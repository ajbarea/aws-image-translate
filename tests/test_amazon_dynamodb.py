import os

import boto3
import pytest
from moto import mock_aws as mock_dynamodb

from config import AWS_REGION
from src.amazon_dynamodb import (
    create_table_if_not_exists,
    delete_table_if_exists,
    get_last_processed_post_id,
    table_exists,
    update_last_processed_post_id,
)

TEST_DDB_TABLE_NAME = "test_reddit_ingest_state"
TEST_SUBREDDIT_KEY = "r/testsubreddit"


@pytest.fixture(scope="function")
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = AWS_REGION


@pytest.fixture(scope="function")
def dynamodb_table(aws_credentials):
    with mock_dynamodb():
        dynamodb_client = boto3.client("dynamodb", region_name=AWS_REGION)
        dynamodb_client.create_table(
            TableName=TEST_DDB_TABLE_NAME,
            KeySchema=[{"AttributeName": "subreddit_key", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "subreddit_key", "AttributeType": "S"}
            ],
            ProvisionedThroughput={"ReadCapacityUnits": 1, "WriteCapacityUnits": 1},
        )

        # Wait for table to exist
        waiter = dynamodb_client.get_waiter("table_exists")
        waiter.wait(TableName=TEST_DDB_TABLE_NAME)

        yield TEST_DDB_TABLE_NAME  # Pass the table name to tests


def test_get_last_processed_post_id_not_found(dynamodb_table, capsys):
    post_id = get_last_processed_post_id(dynamodb_table, TEST_SUBREDDIT_KEY)
    assert post_id is None
    captured = capsys.readouterr()
    assert f"No last_processed_post_id found for {TEST_SUBREDDIT_KEY}" in captured.out


def test_update_and_get_last_processed_post_id(dynamodb_table):
    new_post_id = "t3_xyz123"

    # Update
    success = update_last_processed_post_id(
        dynamodb_table, TEST_SUBREDDIT_KEY, new_post_id
    )
    assert success is True

    # Get
    retrieved_post_id = get_last_processed_post_id(dynamodb_table, TEST_SUBREDDIT_KEY)
    assert retrieved_post_id == new_post_id


def test_update_last_processed_post_id_overwrite(dynamodb_table):
    first_post_id = "t3_abc789"
    second_post_id = "t3_def456"

    # First update
    update_last_processed_post_id(dynamodb_table, TEST_SUBREDDIT_KEY, first_post_id)
    retrieved_id_1 = get_last_processed_post_id(dynamodb_table, TEST_SUBREDDIT_KEY)
    assert retrieved_id_1 == first_post_id

    # Second update (overwrite)
    success = update_last_processed_post_id(
        dynamodb_table, TEST_SUBREDDIT_KEY, second_post_id
    )
    assert success is True

    retrieved_id_2 = get_last_processed_post_id(dynamodb_table, TEST_SUBREDDIT_KEY)
    assert retrieved_id_2 == second_post_id


@mock_dynamodb
def test_get_last_processed_post_id_client_error(capsys):
    result = get_last_processed_post_id(
        "completely-non-existent-table-12345", "some_key"
    )
    assert result is None
    captured = capsys.readouterr()
    assert (
        "Error getting item from DynamoDB table completely-non-existent-table-12345"
        in captured.out
    )


@mock_dynamodb
def test_update_last_processed_post_id_client_error(capsys):
    result = update_last_processed_post_id(
        "completely-non-existent-table-for-update-67890", "some_key", "t3_fakeid"
    )
    assert result is False
    captured = capsys.readouterr()
    assert (
        "Error putting item into DynamoDB table completely-non-existent-table-for-update-67890"
        in captured.out
    )


def test_table_exists_and_create_delete(dynamodb_table):
    # Table should exist due to fixture
    assert table_exists(dynamodb_table)

    # Delete the table
    delete_table_if_exists(dynamodb_table)
    assert not table_exists(dynamodb_table)

    # Re-create the table
    create_table_if_not_exists(dynamodb_table)
    assert table_exists(dynamodb_table)

    # Clean up again
    delete_table_if_exists(dynamodb_table)
    assert not table_exists(dynamodb_table)

import pytest
from moto import mock_aws as mock_dynamodb
import boto3
import os
from config import AWS_REGION

from src.amazon_dynamodb import (
    get_last_processed_post_id,
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
    os.environ["AWS_DEFAULT_REGION"] = AWS_REGION  # Ensure consistency


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

        # Wait for table to exist (moto usually makes this quick, but good practice)
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


@mock_dynamodb  # Apply mock directly if fixture isn't strictly needed for the resource itself by the function
def test_get_last_processed_post_id_client_error(capsys):
    # Test ClientError handling by trying to access a non-existent table
    # Note: get_item on a non-existent table with a resource usually raises ResourceNotFoundException
    # Let's simulate a more generic ClientError by trying to get from a table that doesn't exist
    # For this, we might need to patch the boto3.resource('dynamodb').Table(table_name).get_item
    # However, our function creates the resource internally.
    # A simpler way for this specific test: use a table name that won't be created by fixtures.

    # To truly test the ClientError path in `get_item`, we would need to mock the `table.get_item` call itself.
    # Moto handles non-existent tables gracefully by not finding items.
    # The current function's ClientError is more for other DDB errors (throttling, etc).
    # This test will verify the "not found" path if table is non-existent for the resource.

    # This will likely print "Error getting item from DynamoDB" due to ResourceNotFound if table doesn't exist
    # when Table() is called, or if get_item itself has an issue.
    # The current structure of the code will attempt to create a Table resource first.
    # If the table does not exist, `dynamodb.Table(table_name)` does not fail, but operations on it will.

    # For this test, we'll rely on the fact that moto will return a clean DDB environment.
    # So, accessing a table not created by `dynamodb_table` fixture should simulate the condition.

    # Using a table name that is definitely not created
    result = get_last_processed_post_id(
        "completely-non-existent-table-12345", "some_key"
    )
    assert result is None
    captured = capsys.readouterr()
    # The error message depends on how boto3/moto handles get_item on a table object for a non-existent table.
    # It might be "Requested resource not found" or similar.
    assert (
        "Error getting item from DynamoDB table completely-non-existent-table-12345"
        in captured.out
    )


@mock_dynamodb
def test_update_last_processed_post_id_client_error(capsys):
    # Similar to above, testing ClientError on put_item is tricky without deeper mocking.
    # Moto typically ensures the operation succeeds if parameters are valid.
    # Let's assume an unmocked scenario or a specific DDB error.
    # For now, we can test the path by trying to update a table that doesn't exist.
    result = update_last_processed_post_id(
        "completely-non-existent-table-for-update-67890", "some_key", "t3_fakeid"
    )
    assert result is False
    captured = capsys.readouterr()
    assert (
        "Error putting item into DynamoDB table completely-non-existent-table-for-update-67890"
        in captured.out
    )


# To run: pytest tests/test_amazon_dynamodb.py
# Ensure moto, pytest, boto3 are installed.
# AWS_REGION should be available from config or environment for the tested module.

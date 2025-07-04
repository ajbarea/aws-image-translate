import os

import boto3
import pytest
from moto import mock_aws as mock_dynamodb
from botocore.exceptions import ClientError

from config import AWS_REGION
from src.amazon_dynamodb import (
    create_table_if_not_exists,
    delete_table_if_exists,
    get_last_processed_post_id,
    get_aws_error_message,
    print_table_items,
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
        dynamodb_client = boto3.client("dynamodb", region_name=AWS_REGION)  # type: ignore
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


# Tests for get_aws_error_message
def test_get_aws_error_message_with_message():
    error = ClientError({"Error": {"Message": "Test failure"}}, "Op")
    msg = get_aws_error_message(error)
    assert msg == "Test failure"


def test_get_aws_error_message_without_message():
    error = ClientError({"Error": {}}, "Op")
    msg = get_aws_error_message(error)
    assert "An error occurred" in msg or "ClientError" in msg


def test_get_aws_error_message_exception_handling():
    """Test the exception handling in get_aws_error_message when response parsing fails."""

    # Create a mock ClientError that raises an exception when accessing response
    class MockClientError(ClientError):
        def __init__(self):
            # Don't call super().__init__ to avoid parameter issues
            pass

        @property
        def response(self):
            raise RuntimeError("Response parsing failed")

    mock_error = MockClientError()
    msg = get_aws_error_message(mock_error)
    assert msg == "Unknown error occurred"


# Tests for print_table_items
@mock_dynamodb
def test_print_table_items_empty(capsys, aws_credentials):
    # Create table
    dynamodb_client = boto3.client("dynamodb", region_name=AWS_REGION)  # type: ignore
    dynamodb_client.create_table(
        TableName=TEST_DDB_TABLE_NAME,
        KeySchema=[{"AttributeName": "subreddit_key", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "subreddit_key", "AttributeType": "S"}],
        ProvisionedThroughput={"ReadCapacityUnits": 1, "WriteCapacityUnits": 1},
    )
    waiter = dynamodb_client.get_waiter("table_exists")
    waiter.wait(TableName=TEST_DDB_TABLE_NAME)

    # Empty table
    print_table_items(TEST_DDB_TABLE_NAME)
    captured = capsys.readouterr()
    assert "(No items found)" in captured.out


@mock_dynamodb
def test_print_table_items_with_items(capsys, aws_credentials):
    # Create table
    dynamodb_client = boto3.client("dynamodb", region_name=AWS_REGION)  # type: ignore
    dynamodb_client.create_table(
        TableName=TEST_DDB_TABLE_NAME,
        KeySchema=[{"AttributeName": "subreddit_key", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "subreddit_key", "AttributeType": "S"}],
        ProvisionedThroughput={"ReadCapacityUnits": 1, "WriteCapacityUnits": 1},
    )
    waiter = dynamodb_client.get_waiter("table_exists")
    waiter.wait(TableName=TEST_DDB_TABLE_NAME)
    # Put an item
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    table = dynamodb.Table(TEST_DDB_TABLE_NAME)
    table.put_item(
        Item={"subreddit_key": TEST_SUBREDDIT_KEY, "last_processed_post_id": "t3_abc"}
    )

    print_table_items(TEST_DDB_TABLE_NAME)
    captured = capsys.readouterr()
    assert TEST_SUBREDDIT_KEY in captured.out
    assert "t3_abc" in captured.out


# Test print_table_items exception branch
def test_print_table_items_scan_error(monkeypatch, capsys):
    # Simulate scan error
    class FakeTable:
        def scan(self):
            raise Exception("scan fail")

    class FakeResource:
        def Table(self, name):
            return FakeTable()

    monkeypatch.setattr(
        "src.amazon_dynamodb.get_dynamodb_resource", lambda: FakeResource()
    )

    print_table_items(TEST_DDB_TABLE_NAME)
    captured = capsys.readouterr()
    assert f"Error scanning table {TEST_DDB_TABLE_NAME}: scan fail" in captured.out


def test_get_last_processed_post_id_unexpected_error(monkeypatch, capsys):
    # Simulate a non-ClientError exception
    class FakeTable:
        def get_item(self, Key):
            raise ValueError("boom")

    class FakeResource:
        def Table(self, name):
            return FakeTable()

    monkeypatch.setattr(
        "src.amazon_dynamodb.get_dynamodb_resource", lambda: FakeResource()
    )

    result = get_last_processed_post_id(TEST_DDB_TABLE_NAME, TEST_SUBREDDIT_KEY)
    assert result is None
    captured = capsys.readouterr()
    assert (
        "An unexpected error occurred while getting item from DynamoDB" in captured.out
    )


def test_update_last_processed_post_id_unexpected_error(monkeypatch, capsys):
    # Simulate a non-ClientError exception
    class FakeTable:
        def put_item(self, Item):
            raise RuntimeError("fail")

    class FakeResource:
        def Table(self, name):
            return FakeTable()

    monkeypatch.setattr(
        "src.amazon_dynamodb.get_dynamodb_resource", lambda: FakeResource()
    )

    result = update_last_processed_post_id(
        TEST_DDB_TABLE_NAME, TEST_SUBREDDIT_KEY, "t3_test"
    )
    assert result is False
    captured = capsys.readouterr()
    assert (
        "An unexpected error occurred while putting item into DynamoDB" in captured.out
    )


# Tests for create_table_if_not_exists when table already exists
@mock_dynamodb
def test_create_table_if_not_exists_already_exists(capsys, aws_credentials):
    # Create table
    dynamodb_client = boto3.client("dynamodb", region_name=AWS_REGION)  # type: ignore
    dynamodb_client.create_table(
        TableName=TEST_DDB_TABLE_NAME,
        KeySchema=[{"AttributeName": "subreddit_key", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "subreddit_key", "AttributeType": "S"}],
        ProvisionedThroughput={"ReadCapacityUnits": 1, "WriteCapacityUnits": 1},
    )
    waiter = dynamodb_client.get_waiter("table_exists")
    waiter.wait(TableName=TEST_DDB_TABLE_NAME)

    # Call again to hit the 'already exists' branch
    from src.amazon_dynamodb import create_table_if_not_exists

    create_table_if_not_exists(TEST_DDB_TABLE_NAME)
    # Verify the existing-table message is printed
    captured = capsys.readouterr()
    assert f"Table '{TEST_DDB_TABLE_NAME}' already exists." in captured.out


# Tests for delete_table_if_exists when table does not exist
@mock_dynamodb
def test_delete_table_if_exists_not_exists(capsys, aws_credentials):
    # No table created in this context
    from src.amazon_dynamodb import delete_table_if_exists

    delete_table_if_exists(TEST_DDB_TABLE_NAME)
    # Verify the non-existence message is printed
    captured = capsys.readouterr()
    assert f"Table '{TEST_DDB_TABLE_NAME}' does not exist." in captured.out

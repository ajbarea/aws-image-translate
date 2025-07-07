"""Amazon DynamoDB utility functions for tracking last processed Reddit post IDs.

This module provides functions to interact with a DynamoDB table for storing and retrieving
state information about the last processed post for a given subreddit. It is intended for use
in Reddit ingestion pipelines or similar workflows.
"""

import sys
from typing import Any, Dict, Optional, cast

import boto3
from botocore.exceptions import ClientError
from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource

from config import AWS_REGION


def get_dynamodb_resource() -> DynamoDBServiceResource:
    """Creates and returns a boto3 DynamoDB resource.

    Returns:
        DynamoDBServiceResource: A boto3 DynamoDB resource configured with the default AWS region.
    """
    return boto3.resource("dynamodb", region_name=AWS_REGION)


def get_last_processed_post_id(table_name: str, subreddit_key: str) -> Optional[str]:
    """Retrieves the ID of the last processed Reddit post for a given subreddit.

    Args:
        table_name (str): The name of the DynamoDB table to query.
        subreddit_key (str): The key identifying the subreddit to look up.

    Returns:
        Optional[str]: The ID of the last processed post if found, None if not
            found or if an error occurs.

    Raises:
        ClientError: If there's an AWS-specific error (caught and logged).
        Exception: If there's an unexpected error (caught and logged).
    """
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(table_name)
    try:
        response = table.get_item(Key={"subreddit_key": subreddit_key})
        item = response.get("Item")
        if item and "last_processed_post_id" in item:
            return str(item["last_processed_post_id"])
        else:
            print(
                f"No last_processed_post_id found for {subreddit_key} in table {table_name}."
            )
            return None
    except ClientError as e:
        error_msg = get_aws_error_message(e)
        print(f"Error getting item from DynamoDB table {table_name}: {error_msg}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while getting item from DynamoDB: {e}")
        return None


def update_last_processed_post_id(
    table_name: str, subreddit_key: str, post_id: str
) -> bool:
    """Updates the last processed post ID for a given subreddit.

    Args:
        table_name (str): The name of the DynamoDB table to update.
        subreddit_key (str): The key identifying the subreddit to update.
        post_id (str): The ID of the most recently processed Reddit post.

    Returns:
        bool: True if the update was successful, False if an error occurred.

    Raises:
        ClientError: If there's an AWS-specific error (caught and logged).
        Exception: If there's an unexpected error (caught and logged).
    """
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(table_name)
    try:
        table.put_item(
            Item={"subreddit_key": subreddit_key, "last_processed_post_id": post_id}
        )
        return True
    except ClientError as e:
        error_msg = get_aws_error_message(e)
        print(f"Error putting item into DynamoDB table {table_name}: {error_msg}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred while putting item into DynamoDB: {e}")
        return False


def get_aws_error_message(error: ClientError) -> str:
    """Safely extracts error message from a ClientError response.

    Args:
        error (ClientError): The boto3 ClientError exception.

    Returns:
        str: A formatted error message string.
    """
    try:
        if hasattr(error, "response"):
            response = cast(Dict[str, Any], error.response)
            if "Error" in response and isinstance(response["Error"], dict):
                error_dict = response["Error"]
                if "Message" in error_dict:
                    return str(error_dict["Message"])
        return str(error)
    except Exception:
        return "Unknown error occurred"


def table_exists(table_name: str) -> bool:
    """Checks if a DynamoDB table exists.

    Args:
        table_name (str): The name of the DynamoDB table to check.

    Returns:
        bool: True if the table exists, False otherwise.
    """
    client = boto3.client("dynamodb", region_name=AWS_REGION)
    return table_name in client.list_tables()["TableNames"]


def create_table_if_not_exists(table_name: str) -> None:
    """Creates a DynamoDB table if it does not already exist.

    Args:
        table_name (str): The name of the DynamoDB table to create.

    Returns:
        None
    """
    client = boto3.client("dynamodb", region_name=AWS_REGION)
    if not table_exists(table_name):
        print(f"Table '{table_name}' does not exist. Creating it now...")
        client.create_table(
            TableName=table_name,
            KeySchema=[{"AttributeName": "subreddit_key", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "subreddit_key", "AttributeType": "S"}
            ],
            ProvisionedThroughput={"ReadCapacityUnits": 1, "WriteCapacityUnits": 1},
        )
        print("Waiting for table to be created...")
        waiter = client.get_waiter("table_exists")
        waiter.wait(TableName=table_name)
        print(f"Table '{table_name}' created.")
    else:
        print(f"Table '{table_name}' already exists.")


def delete_table_if_exists(table_name: str) -> None:
    """Deletes a DynamoDB table if it exists.

    Args:
        table_name (str): The name of the DynamoDB table to delete.

    Returns:
        None
    """
    client = boto3.client("dynamodb", region_name=AWS_REGION)
    if table_exists(table_name):
        print(f"Deleting table '{table_name}'...")
        client.delete_table(TableName=table_name)
        waiter = client.get_waiter("table_not_exists")
        waiter.wait(TableName=table_name)
        print(f"Table '{table_name}' deleted.")
    else:
        print(f"Table '{table_name}' does not exist.")


def print_table_items(table_name: str) -> None:
    """Prints all items in the specified DynamoDB table."""
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(table_name)
    try:
        response = table.scan()
        items = response.get("Items", [])
        print(f"\nCurrent items in table '{table_name}':")
        if not items:
            print("  (No items found)")
        for item in items:
            print(f"  {item}")
    except Exception as e:
        print(f"Error scanning table {table_name}: {e}")


if __name__ == "__main__":  # pragma: no cover
    TEST_TABLE_NAME = "reddit_ingest_state_test"
    TEST_SUBREDDIT_KEY = "r/testsubreddit"

    if len(sys.argv) > 1 and sys.argv[1] == "delete-table":
        delete_table_if_exists(TEST_TABLE_NAME)
        sys.exit(0)

    print("--- DynamoDB Table Existence Check ---")
    create_table_if_not_exists(TEST_TABLE_NAME)
    print("--- Basic DynamoDB utility test ---")
    print(f"Getting last_processed_post_id for {TEST_SUBREDDIT_KEY}...")
    post_id = get_last_processed_post_id(TEST_TABLE_NAME, TEST_SUBREDDIT_KEY)
    print(f"Initial last_processed_post_id: {post_id}")

    print(
        f"Updating last_processed_post_id for {TEST_SUBREDDIT_KEY} to 't3_testid123'..."
    )
    success = update_last_processed_post_id(
        TEST_TABLE_NAME, TEST_SUBREDDIT_KEY, "t3_testid123"
    )
    print(f"Update success: {success}")

    print(f"Getting last_processed_post_id for {TEST_SUBREDDIT_KEY} after update...")
    post_id = get_last_processed_post_id(TEST_TABLE_NAME, TEST_SUBREDDIT_KEY)
    print(f"Updated last_processed_post_id: {post_id}")
    print_table_items(TEST_TABLE_NAME)
    print("Deleting table after test...")
    delete_table_if_exists(TEST_TABLE_NAME)

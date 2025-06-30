"""Amazon DynamoDB utility functions for tracking last processed Reddit post IDs.

This module provides functions to interact with a DynamoDB table for storing and retrieving
state information about the last processed post for a given subreddit. It is intended for use
in Reddit ingestion pipelines or similar workflows.
"""

import boto3
from botocore.exceptions import ClientError

from config import AWS_REGION


def get_dynamodb_resource():
    return boto3.resource("dynamodb", region_name=AWS_REGION)


def get_last_processed_post_id(table_name, subreddit_key):
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(table_name)  # type: ignore[attr-defined]
    try:
        response = table.get_item(Key={"subreddit_key": subreddit_key})
        item = response.get("Item")
        if item and "last_processed_post_id" in item:
            return item["last_processed_post_id"]
        else:
            print(
                f"No last_processed_post_id found for {subreddit_key} in table {table_name}."
            )
            return None
    except ClientError as e:
        print(
            f"Error getting item from DynamoDB table {table_name}: {e.response['Error']['Message']}"
        )
        return None
    except Exception as e:
        print(f"An unexpected error occurred while getting item from DynamoDB: {e}")
        return None


def update_last_processed_post_id(table_name, subreddit_key, post_id):
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(table_name)  # type: ignore[attr-defined]
    try:
        table.put_item(
            Item={
                "subreddit_key": subreddit_key,
                "last_processed_post_id": post_id,
            }
        )
        print(
            f"Successfully updated last_processed_post_id for {subreddit_key} to {post_id} in table {table_name}."
        )
        return True
    except ClientError as e:
        print(
            f"Error putting item into DynamoDB table {table_name}: {e.response['Error']['Message']}"
        )
        return False
    except Exception as e:
        print(f"An unexpected error occurred while putting item into DynamoDB: {e}")
        return False


def table_exists(table_name):
    client = boto3.client("dynamodb", region_name=AWS_REGION)
    return table_name in client.list_tables()["TableNames"]


def create_table_if_not_exists(table_name):
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


def delete_table_if_exists(table_name):
    client = boto3.client("dynamodb", region_name=AWS_REGION)
    if table_exists(table_name):
        print(f"Deleting table '{table_name}'...")
        client.delete_table(TableName=table_name)
        waiter = client.get_waiter("table_not_exists")
        waiter.wait(TableName=table_name)
        print(f"Table '{table_name}' deleted.")
    else:
        print(f"Table '{table_name}' does not exist.")


def print_table_items(table_name):
    """Prints all items in the specified DynamoDB table."""
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(table_name)  # type: ignore[attr-defined]
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


if __name__ == "__main__":
    import sys

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

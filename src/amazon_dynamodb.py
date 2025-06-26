"""Amazon DynamoDB utility functions for tracking last processed Reddit post IDs.

This module provides functions to interact with a DynamoDB table for storing and retrieving
state information about the last processed post for a given subreddit. It is intended for use
in Reddit ingestion pipelines or similar workflows.
"""

import boto3
from botocore.exceptions import ClientError
from config import AWS_REGION


def get_dynamodb_resource():
    """Initialize and return a DynamoDB resource for the configured AWS region.

    Returns:
        boto3.resources.factory.dynamodb.ServiceResource: A DynamoDB resource object.
    """
    return boto3.resource("dynamodb", region_name=AWS_REGION)


def get_last_processed_post_id(table_name, subreddit_key):
    """Retrieve the last processed post ID for a given subreddit from DynamoDB.

    Args:
        table_name (str): Name of the DynamoDB table.
        subreddit_key (str): The key for the subreddit (e.g., "r/translator").

    Returns:
        str or None: The last processed post ID (fullname, e.g., "t3_xxxxxx") if found, else None.

    Raises:
        None: All exceptions are caught and logged; function returns None on error.
    """
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(table_name)
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
    """Update the last processed post ID for a given subreddit in DynamoDB.

    Args:
        table_name (str): Name of the DynamoDB table.
        subreddit_key (str): The key for the subreddit (e.g., "r/translator").
        post_id (str): The ID (fullname) of the last processed post.

    Returns:
        bool: True if update was successful, False otherwise.

    Raises:
        None: All exceptions are caught and logged; function returns False on error.
    """
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(table_name)
    try:
        table.put_item(
            Item={
                "subreddit_key": subreddit_key,
                "last_processed_post_id": post_id,
                # Optionally add a timestamp for when it was last updated
                # "last_updated_timestamp": int(time.time())
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


if __name__ == "__main__":
    # Example Usage (requires AWS credentials and DynamoDB table to be set up)
    # Ensure DYNAMODB_TABLE_NAME is configured in config.py or pass directly
    # from config import DYNAMODB_TABLE_NAME # Assuming this will be added

    TEST_TABLE_NAME = "reddit_ingest_state_test"  # Use a test table name
    TEST_SUBREDDIT_KEY = "r/testsubreddit"

    # --- Manual DynamoDB Table Creation for Testing (if not using IaC yet) ---
    # Uncomment to create a test table if needed.
    # try:
    #     print(f"Attempting to create DynamoDB table: {TEST_TABLE_NAME} (for testing only)")
    #     client = boto3.client("dynamodb", region_name=AWS_REGION)
    #     client.create_table(
    #         TableName=TEST_TABLE_NAME,
    #         KeySchema=[{'AttributeName': 'subreddit_key', 'KeyType': 'HASH'}],
    #         AttributeDefinitions=[{'AttributeName': 'subreddit_key', 'AttributeType': 'S'}],
    #         ProvisionedThroughput={'ReadCapacityUnits': 1, 'WriteCapacityUnits': 1}
    #     )
    #     print(f"Waiting for table {TEST_TABLE_NAME} to be created...")
    #     waiter = client.get_waiter('table_exists')
    #     waiter.wait(TableName=TEST_TABLE_NAME)
    #     print(f"Table {TEST_TABLE_NAME} created successfully.")
    # except ClientError as e:
    #     if e.response['Error']['Code'] == 'ResourceInUseException':
    #         print(f"Table {TEST_TABLE_NAME} already exists. Skipping creation.")
    #     else:
    #         print(f"Error creating table {TEST_TABLE_NAME}: {e}")
    # except Exception as e:
    #     print(f"Unexpected error during test table setup: {e}")
    # --- End Manual Table Creation ---

    # print(f"\nTesting with DynamoDB table: {TEST_TABLE_NAME}")
    #
    # # Test 1: Get initial post ID (should be None)
    # print("\n--- Test 1: Get initial post ID ---")
    # last_id = get_last_processed_post_id(TEST_TABLE_NAME, TEST_SUBREDDIT_KEY)
    # print(f"Initial last_processed_post_id for {TEST_SUBREDDIT_KEY}: {last_id}")
    # assert last_id is None, f"Expected None, got {last_id}"
    #
    # # Test 2: Update post ID
    # print("\n--- Test 2: Update post ID ---")
    # new_post_id = "t3_abc123"
    # success = update_last_processed_post_id(TEST_TABLE_NAME, TEST_SUBREDDIT_KEY, new_post_id)
    # print(f"Update successful for {new_post_id}: {success}")
    # assert success is True, "Update failed"
    #
    # # Test 3: Get updated post ID
    # print("\n--- Test 3: Get updated post ID ---")
    # last_id = get_last_processed_post_id(TEST_TABLE_NAME, TEST_SUBREDDIT_KEY)
    # print(f"Updated last_processed_post_id for {TEST_SUBREDDIT_KEY}: {last_id}")
    # assert last_id == new_post_id, f"Expected {new_post_id}, got {last_id}"
    #
    # # Test 4: Update again
    # print("\n--- Test 4: Update post ID again ---")
    # newer_post_id = "t3_def456"
    # success = update_last_processed_post_id(TEST_TABLE_NAME, TEST_SUBREDDIT_KEY, newer_post_id)
    # print(f"Update successful for {newer_post_id}: {success}")
    # assert success is True, "Second update failed"
    #
    # # Test 5: Get the newest post ID
    # print("\n--- Test 5: Get newest post ID ---")
    # last_id = get_last_processed_post_id(TEST_TABLE_NAME, TEST_SUBREDDIT_KEY)
    # print(f"Newest last_processed_post_id for {TEST_SUBREDDIT_KEY}: {last_id}")
    # assert last_id == newer_post_id, f"Expected {newer_post_id}, got {last_id}"
    #
    # print("\nAll amazon_dynamodb.py example tests passed locally (assuming table exists or was created).")
    #
    # # Optional: Clean up the test table (be careful with this in automated environments)
    # # print(f"\nConsider deleting the test table '{TEST_TABLE_NAME}' manually if no longer needed.")

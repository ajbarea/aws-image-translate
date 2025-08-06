import json
import os

import boto3
from boto3.dynamodb.conditions import Key

# Global variables for lazy initialization
_dynamodb = None
_history_table = None
_translations_table = None


def _get_dynamodb():
    """Lazy initialization of DynamoDB resource"""
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION"))
    return _dynamodb


def _get_history_table():
    """Lazy initialization of history table"""
    global _history_table
    if _history_table is None:
        table_name = os.getenv("TRANSLATION_HISTORY_TABLE")
        if not table_name:
            raise ValueError("TRANSLATION_HISTORY_TABLE environment variable not set")
        _history_table = _get_dynamodb().Table(table_name)
    return _history_table


def _get_translations_table():
    """Lazy initialization of translations table"""
    global _translations_table
    if _translations_table is None:
        table_name = os.getenv("TRANSLATIONS_TABLE")
        if not table_name:
            raise ValueError("TRANSLATIONS_TABLE environment variable not set")
        _translations_table = _get_dynamodb().Table(table_name)
    return _translations_table


def get_history_table():
    return _get_history_table()


def get_translations_table():
    return _get_translations_table()


def _get_user_id(event):
    """
    Extract user ID from JWT claims in API Gateway authorizer context.
    Works with both Google OAuth and email/password Cognito users.
    """
    # Primary method: JWT claims from API Gateway authorizer
    user_id = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
        .get("sub")
    )

    if user_id:
        return user_id

    # Fallback: Try alternative claim structures
    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )

    if claims:
        # Try other possible user ID fields
        return (
            claims.get("cognito:username")
            or claims.get("username")
            or claims.get("email")
        )

    return None


def list_history(event, context):
    """
    Fetches the translation history of the current user
    Args:
        event: When a user chooses to see their translation history
        context:

    Returns: {
        'statusCode': <200, 401>,
        'body': {
            [
                {
                    "history_id" : <user_id>,
                    "created_on" : <timestamp>,
                    "image_name" : <image_name>,
                    "src_lang" : <src_lang>,
                    "t_lang" : <t_lang>
                }
            ]
        }
    }

    """
    user_id = _get_user_id(event)
    print(f"DEBUG: list_history - user_id extracted: {user_id}")
    print(f"DEBUG: list_history - event structure: {json.dumps(event, default=str)}")

    if not user_id:
        return {"statusCode": 401, "body": json.dumps({"error": "Unauthorized"})}

    resp = get_history_table().query(
        KeyConditionExpression=Key("user_id").eq(user_id),
        ProjectionExpression="history_id, image_key, lang_pair, #ts",
        ExpressionAttributeNames={"#ts": "timestamp"},
    )
    items = resp.get("Items", [])
    print(f"DEBUG: list_history - DynamoDB query returned {len(items)} items")

    history_list = []
    for it in items:
        src, tgt = it["lang_pair"].split("#", 1)
        history_list.append(
            {
                "history_id": it["history_id"],
                "created_on": it["timestamp"],
                "image_name": it["image_key"],
                "src_lang": src,
                "t_lang": tgt,
            }
        )

    print(f"DEBUG: list_history - returning {len(history_list)} history items")
    return {
        "statusCode": 200,
        "body": json.dumps({"user_id": user_id, "history": history_list}),
    }


def get_history_item(event, context):
    user_id = _get_user_id(event)
    if not user_id:
        return {"statusCode": 401, "body": json.dumps({"error": "Unauthorized"})}

    # Path parameter binding via API Gateway
    path_params = event.get("pathParameters") or {}
    history_id = path_params.get("history_id")
    if not history_id:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing history_id in path"}),
        }

    # Fetch history record
    hist_resp = get_history_table().get_item(
        Key={"user_id": user_id, "history_id": history_id}
    )
    hist_item = hist_resp.get("Item")
    if not hist_item:
        return {
            "statusCode": 404,
            "body": json.dumps({"error": "History record not found"}),
        }

    translation_id = hist_item["translation_id"]
    image_key = hist_item["image_key"]
    src, tgt = hist_item["lang_pair"].split("#", 1)

    # Fetch translation data
    trans_resp = get_translations_table().get_item(
        Key={"translation_id": translation_id}
    )
    trans_item = trans_resp.get("Item")
    if not trans_item:
        return {
            "statusCode": 502,
            "body": json.dumps({"error": "Translation record missing"}),
        }

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "history_id": history_id,
                "image_name": image_key,
                "src_lang": src,
                "src_text": trans_item.get("extracted_text", ""),
                "t_lang": tgt,
                "t_text": trans_item.get("translated_text", ""),
            }
        ),
    }

import base64
import json
import logging
import time
from functools import lru_cache
from typing import Any, Dict

import boto3
from aws_clients import OPTIMIZED_CONFIG, performance_monitor
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)


@lru_cache(maxsize=None)
def get_cognito_client():
    """Get Cognito client with connection pooling."""
    return boto3.client("cognito-idp", config=OPTIMIZED_CONFIG)


def get_cors_headers():
    """Get CORS headers for API responses."""
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token",
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS,DELETE",
        "Content-Type": "application/json",
    }


def create_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Create a standardized API response."""
    return {
        "statusCode": status_code,
        "headers": get_cors_headers(),
        "body": json.dumps(body),
    }


def extract_user_from_token(event: Dict[str, Any]) -> str:
    """Extract username from JWT token in the Authorization header."""
    try:
        # Get the authorization header
        headers = event.get("headers", {})
        auth_header = headers.get("Authorization") or headers.get("authorization")

        if not auth_header:
            raise ValueError("No Authorization header found")

        # Extract the token (remove "Bearer " prefix if present)
        token = auth_header.replace("Bearer ", "").strip()

        if not token:
            raise ValueError("No token found in Authorization header")

        # Split the token and get the payload
        token_parts = token.split(".")
        if len(token_parts) != 3:
            raise ValueError("Invalid JWT token format")

        # Decode the payload
        payload_b64 = token_parts[1]
        # Add padding if needed
        payload_b64 += "=" * (4 - len(payload_b64) % 4)

        payload_json = base64.b64decode(payload_b64).decode("utf-8")
        payload = json.loads(payload_json)

        # Extract username (could be in 'email', 'cognito:username', or 'username' field)
        username = (
            payload.get("email")
            or payload.get("cognito:username")
            or payload.get("username")
        )

        if not username:
            raise ValueError("No username found in token payload")

        logger.info(f"UserManager: Extracted username from token: {username}")
        return username

    except Exception as e:
        logger.error(f"UserManager: Failed to extract user from token: {str(e)}")
        raise ValueError(f"Invalid authorization token: {str(e)}")


def check_user_has_password(username: str, user_pool_id: str) -> bool:
    """
    Check if a user has password authentication set up.

    Args:
        username: The username/email of the user
        user_pool_id: The Cognito User Pool ID

    Returns:
        True if user has password auth, False otherwise
    """
    try:
        cognito_client = get_cognito_client()

        # Try to initiate auth with a dummy password to check if password auth is available
        # This is a safe way to check without actually authenticating
        try:
            cognito_client.admin_initiate_auth(
                UserPoolId=user_pool_id,
                ClientId=user_pool_id,  # This will fail, but that's expected
                AuthFlow="ADMIN_NO_SRP_AUTH",
                AuthParameters={
                    "USERNAME": username,
                    "PASSWORD": "dummy_password_check",
                },
            )
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")

            # If we get these errors, it means password auth is available
            if error_code in ["NotAuthorizedException", "InvalidParameterException"]:
                logger.info(
                    f"UserManager: User {username} has password authentication available"
                )
                return True
            # If user not found or other errors, password auth might not be set up
            elif error_code in ["UserNotFoundException", "InvalidClientIdException"]:
                logger.info(
                    f"UserManager: User {username} may not have password authentication"
                )
                return False

        # Alternative check: look at user status and creation method
        user_response = cognito_client.admin_get_user(
            UserPoolId=user_pool_id, Username=username
        )

        user_status = user_response.get("UserStatus", "")

        # If user is EXTERNAL_PROVIDER, they likely don't have password auth
        if user_status == "EXTERNAL_PROVIDER":
            logger.info(
                f"UserManager: User {username} is EXTERNAL_PROVIDER, likely no password auth"
            )
            return False

        # For other statuses, assume password auth is available
        logger.info(
            f"UserManager: User {username} likely has password authentication (status: {user_status})"
        )
        return True

    except Exception as e:
        logger.error(
            f"UserManager: Error checking password auth for {username}: {str(e)}"
        )
        # If we can't determine, err on the side of caution and assume no password
        return False


def set_user_password(
    username: str, user_pool_id: str, password: str
) -> Dict[str, Any]:
    """
    Set a password for a user (typically for Google OAuth users who want to add password auth).

    Args:
        username: The username/email of the user
        user_pool_id: The Cognito User Pool ID
        password: The new password to set

    Returns:
        Dictionary with success status and details
    """
    logger.info(f"UserManager: Setting password for user: {username}")

    try:
        cognito_client = get_cognito_client()
        start_time = time.time()

        # Set the user's password (this works for both new and existing users)
        cognito_client.admin_set_user_password(
            UserPoolId=user_pool_id,
            Username=username,
            Password=password,
            Permanent=True,  # Make it permanent (not temporary)
        )

        # Record performance metrics
        duration = time.time() - start_time
        performance_monitor.record_operation(
            "cognito_admin_set_user_password", duration, True
        )

        logger.info(f"UserManager: Successfully set password for {username}")

        return {"success": True, "message": "Password set successfully"}

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        error_message = e.response.get("Error", {}).get("Message", str(e))

        logger.error(
            f"UserManager: Cognito error setting password for {username}: {error_code} - {error_message}"
        )

        if error_code == "UserNotFoundException":
            return {
                "success": False,
                "message": "User not found",
                "code": "USER_NOT_FOUND",
            }
        elif error_code == "InvalidPasswordException":
            return {
                "success": False,
                "message": "Password does not meet requirements",
                "code": "INVALID_PASSWORD",
            }
        elif error_code == "NotAuthorizedException":
            return {
                "success": False,
                "message": "Not authorized to set password",
                "code": "NOT_AUTHORIZED",
            }
        else:
            return {
                "success": False,
                "message": f"Failed to set password: {error_message}",
                "code": error_code,
            }

    except Exception as e:
        logger.error(
            f"UserManager: Unexpected error setting password for {username}: {str(e)}"
        )
        return {
            "success": False,
            "message": "An unexpected error occurred while setting password",
            "code": "INTERNAL_ERROR",
        }


def link_google_account(
    username: str, user_pool_id: str, google_user_info: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Link a Google account to an existing Cognito user.

    Args:
        username: The username/email of the Cognito user
        user_pool_id: The Cognito User Pool ID
        google_user_info: Decoded Google ID token containing user information

    Returns:
        Dictionary with success status and details
    """
    logger.info(f"UserManager: Starting Google account linking for user: {username}")

    try:
        cognito_client = get_cognito_client()
        start_time = time.time()

        # First, get the current user to check their existing identities
        user_response = cognito_client.admin_get_user(
            UserPoolId=user_pool_id, Username=username
        )

        # Record performance metrics
        duration = time.time() - start_time
        performance_monitor.record_operation("cognito_admin_get_user", duration, True)

        logger.info(f"UserManager: Retrieved user info for {username}")

        # Validate the Google user info
        google_email = google_user_info.get("email")
        google_user_id = google_user_info.get("sub")

        if not google_email or not google_user_id:
            return {
                "success": False,
                "message": "Invalid Google token: missing email or user ID",
                "code": "INVALID_TOKEN",
            }

        # Get current user's email
        user_attributes = user_response.get("UserAttributes", [])
        current_email = None

        for attr in user_attributes:
            if attr["Name"] == "email":
                current_email = attr["Value"]
                break

        # Validate that emails match
        if google_email != current_email:
            logger.warning(
                f"UserManager: Email mismatch for {username}: Google={google_email}, Current={current_email}"
            )
            return {
                "success": False,
                "message": f"Google account email ({google_email}) must match your current account email ({current_email})",
                "code": "EMAIL_MISMATCH",
            }

        # Check if user already has Google identity linked
        identities_attr = None
        for attr in user_attributes:
            if attr["Name"] == "identities":
                identities_attr = attr
                break

        existing_identities = []
        if identities_attr:
            try:
                existing_identities = json.loads(identities_attr["Value"])
            except (json.JSONDecodeError, KeyError):
                logger.warning(
                    f"UserManager: Could not parse existing identities for user {username}"
                )

        # Check if Google identity already exists
        for identity in existing_identities:
            if identity.get("providerName") == "Google":
                if identity.get("userId") == google_user_id:
                    logger.info(
                        f"UserManager: Google account already linked for {username}"
                    )
                    return {
                        "success": True,
                        "message": "Google account is already linked to this user",
                        "alreadyLinked": True,
                        "linkedAt": identity.get("dateCreated", time.time()),
                    }
                else:
                    # Different Google account is linked
                    return {
                        "success": False,
                        "message": "A different Google account is already linked to this user. Please unlink it first.",
                        "code": "DIFFERENT_GOOGLE_ACCOUNT",
                    }

        # Create new Google identity
        new_google_identity = {
            "userId": google_user_id,
            "providerName": "Google",
            "providerType": "Google",
            "issuer": None,
            "primary": "false",
            "dateCreated": str(int(time.time() * 1000)),  # Cognito uses milliseconds
        }

        # Add to existing identities
        updated_identities = existing_identities + [new_google_identity]
        updated_identities_json = json.dumps(updated_identities)

        # Update the user's identities attribute
        start_time = time.time()
        cognito_client.admin_update_user_attributes(
            UserPoolId=user_pool_id,
            Username=username,
            UserAttributes=[{"Name": "identities", "Value": updated_identities_json}],
        )
        duration = time.time() - start_time
        performance_monitor.record_operation(
            "cognito_admin_update_user_attributes", duration, True
        )

        logger.info(
            f"UserManager: Successfully linked Google account for {username}: {google_user_id}"
        )

        return {
            "success": True,
            "message": "Google account linked successfully",
            "linkedAt": time.time(),
            "linkedEmail": google_email,
            "totalIdentities": len(updated_identities),
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        error_message = e.response.get("Error", {}).get("Message", str(e))

        logger.error(
            f"UserManager: Cognito error linking Google account for {username}: {error_code} - {error_message}"
        )

        if error_code == "UserNotFoundException":
            return {
                "success": False,
                "message": "User not found",
                "code": "USER_NOT_FOUND",
            }
        elif error_code == "NotAuthorizedException":
            return {
                "success": False,
                "message": "Not authorized to perform this operation",
                "code": "NOT_AUTHORIZED",
            }
        else:
            return {
                "success": False,
                "message": f"Failed to link Google account: {error_message}",
                "code": error_code,
            }

    except Exception as e:
        logger.error(
            f"UserManager: Unexpected error linking Google account for {username}: {str(e)}"
        )
        return {
            "success": False,
            "message": "An unexpected error occurred while linking the Google account",
            "code": "INTERNAL_ERROR",
        }


def unlink_google_account(username: str, user_pool_id: str) -> Dict[str, Any]:
    """
    Unlink Google account from a Cognito user.

    Args:
        username: The username/email of the user
        user_pool_id: The Cognito User Pool ID

    Returns:
        Dictionary with success status and details
    """
    logger.info(f"UserManager: Starting Google account unlinking for user: {username}")

    try:
        cognito_client = get_cognito_client()
        start_time = time.time()

        # First, get the current user to check their identities
        user_response = cognito_client.admin_get_user(
            UserPoolId=user_pool_id, Username=username
        )

        # Record performance metrics
        duration = time.time() - start_time
        performance_monitor.record_operation("cognito_admin_get_user", duration, True)

        logger.info(f"UserManager: Retrieved user info for {username}")

        # Check if user has Google identity linked
        user_attributes = user_response.get("UserAttributes", [])
        identities_attr = None

        for attr in user_attributes:
            if attr["Name"] == "identities":
                identities_attr = attr
                break

        if not identities_attr:
            logger.info(f"UserManager: User {username} has no linked identities")
            return {
                "success": False,
                "message": "No Google account is currently linked to this user",
                "code": "NO_GOOGLE_LINK",
            }

        # Parse the identities JSON
        try:
            identities = json.loads(identities_attr["Value"])
        except (json.JSONDecodeError, KeyError):
            logger.warning(
                f"UserManager: Could not parse identities for user {username}"
            )
            return {
                "success": False,
                "message": "Unable to process account linking information",
                "code": "PARSE_ERROR",
            }

        # Check if Google identity exists
        google_identity = None
        other_identities = []

        for identity in identities:
            if identity.get("providerName") == "Google":
                google_identity = identity
            else:
                other_identities.append(identity)

        if not google_identity:
            logger.info(f"UserManager: User {username} has no Google identity linked")
            return {
                "success": False,
                "message": "No Google account is currently linked to this user",
                "code": "NO_GOOGLE_LINK",
            }

        logger.info(
            f"UserManager: Found Google identity for {username}: {google_identity.get('userId', 'unknown')}"
        )

        # CRITICAL CHECK: Prevent account lockout
        # If this is the user's only authentication method, ensure they have password auth
        if len(identities) == 1:  # Only Google identity exists
            logger.info(
                f"UserManager: User {username} has only Google identity, checking for password auth"
            )

            user_has_password = check_user_has_password(username, user_pool_id)

            if not user_has_password:
                logger.warning(
                    f"UserManager: User {username} would be locked out - no password auth available"
                )
                return {
                    "success": False,
                    "message": "You must set up a password before unlinking your Google account to avoid being locked out",
                    "code": "PASSWORD_REQUIRED",
                    "requiresPassword": True,
                }

        logger.info(f"UserManager: Safe to unlink Google account for {username}")

        # Remove the Google identity from the identities array
        if other_identities:
            # Update the identities attribute with remaining identities
            updated_identities_json = json.dumps(other_identities)

            start_time = time.time()
            cognito_client.admin_update_user_attributes(
                UserPoolId=user_pool_id,
                Username=username,
                UserAttributes=[
                    {"Name": "identities", "Value": updated_identities_json}
                ],
            )
            duration = time.time() - start_time
            performance_monitor.record_operation(
                "cognito_admin_update_user_attributes", duration, True
            )

            logger.info(
                f"UserManager: Updated identities for {username}, removed Google identity"
            )
        else:
            # If this was the only identity, remove the identities attribute entirely
            start_time = time.time()
            cognito_client.admin_delete_user_attributes(
                UserPoolId=user_pool_id,
                Username=username,
                UserAttributeNames=["identities"],
            )
            duration = time.time() - start_time
            performance_monitor.record_operation(
                "cognito_admin_delete_user_attributes", duration, True
            )

            logger.info(
                f"UserManager: Removed identities attribute for {username} (was last identity)"
            )

        logger.info(f"UserManager: Successfully unlinked Google account for {username}")

        return {
            "success": True,
            "message": "Google account unlinked successfully",
            "unlinkedAt": time.time(),
            "remainingIdentities": len(other_identities),
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        error_message = e.response.get("Error", {}).get("Message", str(e))

        logger.error(
            f"UserManager: Cognito error unlinking Google account for {username}: {error_code} - {error_message}"
        )

        if error_code == "UserNotFoundException":
            return {
                "success": False,
                "message": "User not found",
                "code": "USER_NOT_FOUND",
            }
        elif error_code == "NotAuthorizedException":
            return {
                "success": False,
                "message": "Not authorized to perform this operation",
                "code": "NOT_AUTHORIZED",
            }
        else:
            return {
                "success": False,
                "message": f"Failed to unlink Google account: {error_message}",
                "code": error_code,
            }

    except Exception as e:
        logger.error(
            f"UserManager: Unexpected error unlinking Google account for {username}: {str(e)}"
        )
        return {
            "success": False,
            "message": "An unexpected error occurred while unlinking the Google account",
            "code": "INTERNAL_ERROR",
        }


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for user management operations.
    """
    logger.info("UserManager: Lambda function invoked")
    logger.info(f"UserManager: Event: {json.dumps(event, indent=2)}")

    try:
        # Handle CORS preflight requests
        if event.get("httpMethod") == "OPTIONS":
            logger.info("UserManager: Handling CORS preflight request")
            performance_monitor.persist_metrics()
            return create_response(200, {"message": "CORS preflight successful"})

        # Extract HTTP method and path in API Gateway v2 format
        http_method = (
            event.get("requestContext", {}).get("http", {}).get("method", "").upper()
        )
        path = event.get("requestContext", {}).get("http", {}).get("path", "")

        # Fallback to v1 format if v2 fields are not present
        if not http_method:
            http_method = event.get("httpMethod", "").upper()
        if not path:
            path = event.get("path", "")

        logger.info(f"UserManager: Processing {http_method} request to {path}")

        # Get user pool ID from environment
        import os

        user_pool_id = os.environ.get("USER_POOL_ID")
        if not user_pool_id:
            logger.error("UserManager: USER_POOL_ID environment variable not set")
            return create_response(
                500,
                {
                    "error": "Server configuration error",
                    "message": "User pool not configured",
                },
            )

        # Route the request based on method and path
        if http_method == "DELETE" and path.endswith("/unlink-google"):
            # Extract username from JWT token
            try:
                username = extract_user_from_token(event)
            except ValueError as e:
                logger.error(f"UserManager: Authentication error: {str(e)}")
                return create_response(
                    401, {"error": "Authentication required", "message": str(e)}
                )

            # Perform the unlinking operation
            result = unlink_google_account(username, user_pool_id)

            if result["success"]:
                logger.info(
                    f"UserManager: Google account unlinked successfully for {username}"
                )
                performance_monitor.persist_metrics()
                return create_response(200, result)
            else:
                # Determine appropriate status code based on error
                status_code = 400
                if result.get("code") == "USER_NOT_FOUND":
                    status_code = 404
                elif result.get("code") == "NOT_AUTHORIZED":
                    status_code = 403
                elif result.get("code") == "NO_GOOGLE_LINK":
                    status_code = 400
                elif result.get("code") == "PASSWORD_REQUIRED":
                    status_code = 428  # Precondition Required

                logger.warning(
                    f"UserManager: Google account unlinking failed for {username}: {result.get('message')}"
                )
                return create_response(
                    status_code,
                    {
                        "error": "Unlinking failed",
                        "message": result["message"],
                        "code": result.get("code"),
                        "requiresPassword": result.get("requiresPassword", False),
                    },
                )

        elif http_method == "POST" and path.endswith("/set-password"):
            # Extract username from JWT token
            try:
                username = extract_user_from_token(event)
            except ValueError as e:
                logger.error(f"UserManager: Authentication error: {str(e)}")
                return create_response(
                    401, {"error": "Authentication required", "message": str(e)}
                )

            # Parse request body to get password
            try:
                body = json.loads(event.get("body", "{}"))
                password = body.get("password")

                if not password:
                    return create_response(
                        400, {"error": "Bad request", "message": "Password is required"}
                    )

            except json.JSONDecodeError:
                return create_response(
                    400,
                    {"error": "Bad request", "message": "Invalid JSON in request body"},
                )

            # Set the user's password
            result = set_user_password(username, user_pool_id, password)

            if result["success"]:
                logger.info(f"UserManager: Password set successfully for {username}")
                performance_monitor.persist_metrics()
                return create_response(200, result)
            else:
                # Determine appropriate status code based on error
                status_code = 400
                if result.get("code") == "USER_NOT_FOUND":
                    status_code = 404
                elif result.get("code") == "NOT_AUTHORIZED":
                    status_code = 403
                elif result.get("code") == "INVALID_PASSWORD":
                    status_code = 400

                logger.warning(
                    f"UserManager: Password setting failed for {username}: {result.get('message')}"
                )
                return create_response(
                    status_code,
                    {
                        "error": "Password setting failed",
                        "message": result["message"],
                        "code": result.get("code"),
                    },
                )

        elif http_method == "POST" and path.endswith("/link-google"):
            # Extract username from JWT token
            try:
                username = extract_user_from_token(event)
            except ValueError as e:
                logger.error(f"UserManager: Authentication error: {str(e)}")
                return create_response(
                    401, {"error": "Authentication required", "message": str(e)}
                )

            # Parse request body to get Google token info
            try:
                body = json.loads(event.get("body", "{}"))
                google_user_info = body.get("googleUserInfo")

                if not google_user_info:
                    return create_response(
                        400,
                        {
                            "error": "Bad request",
                            "message": "Google user info is required",
                        },
                    )

                # Validate required fields
                if not google_user_info.get("email") or not google_user_info.get("sub"):
                    return create_response(
                        400,
                        {
                            "error": "Bad request",
                            "message": "Google user info must contain email and sub fields",
                        },
                    )

            except json.JSONDecodeError:
                return create_response(
                    400,
                    {"error": "Bad request", "message": "Invalid JSON in request body"},
                )

            # Link the Google account
            result = link_google_account(username, user_pool_id, google_user_info)

            if result["success"]:
                logger.info(
                    f"UserManager: Google account linked successfully for {username}"
                )
                performance_monitor.persist_metrics()
                return create_response(200, result)
            else:
                # Determine appropriate status code based on error
                status_code = 400
                if result.get("code") == "USER_NOT_FOUND":
                    status_code = 404
                elif result.get("code") == "NOT_AUTHORIZED":
                    status_code = 403
                elif result.get("code") == "EMAIL_MISMATCH":
                    status_code = 400
                elif result.get("code") == "INVALID_TOKEN":
                    status_code = 400
                elif result.get("code") == "DIFFERENT_GOOGLE_ACCOUNT":
                    status_code = 409  # Conflict

                logger.warning(
                    f"UserManager: Google account linking failed for {username}: {result.get('message')}"
                )
                performance_monitor.persist_metrics()
                return create_response(
                    status_code,
                    {
                        "error": "Linking failed",
                        "message": result["message"],
                        "code": result.get("code"),
                        "alreadyLinked": result.get("alreadyLinked", False),
                    },
                )

        else:
            logger.warning(f"UserManager: Unsupported request: {http_method} {path}")
            performance_monitor.persist_metrics()
            return create_response(
                404,
                {
                    "error": "Not found",
                    "message": f"Endpoint {http_method} {path} not found",
                },
            )

    except Exception as e:
        logger.error(f"UserManager: Unexpected error in lambda handler: {str(e)}")
        performance_monitor.persist_metrics()
        return create_response(
            500,
            {
                "error": "Internal server error",
                "message": "An unexpected error occurred",
            },
        )

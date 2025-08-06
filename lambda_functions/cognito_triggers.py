import json
import logging
import time
from functools import lru_cache
from typing import Any, Dict, Tuple

import boto3
from aws_clients import OPTIMIZED_CONFIG, performance_monitor
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


@lru_cache(maxsize=None)
def get_cognito_client():
    """Get Cognito client with connection pooling."""
    return boto3.client("cognito-idp", config=OPTIMIZED_CONFIG)


def extract_email_and_code(event: Dict[str, Any]) -> Tuple[str, str]:
    """Extracts email and code from a Cognito event."""
    request = event.get("request", {})
    user_attributes = request.get("userAttributes", {})
    email = user_attributes.get("email", "unknown")
    code = request.get("codeParameter")
    return email, code


def log_cognito_code(trigger_source: str, email: str, code: str) -> None:
    """Logs the Cognito verification code for debugging."""
    label = (
        "EMAIL CONFIRMATION CODE"
        if trigger_source == "CustomMessage_SignUp"
        else "RESENT EMAIL CONFIRMATION CODE"
    )
    logger.info(f"[CODE] {label} FOR {email}: {code}")
    logger.info(f"[EMAIL] User Email: {email}")
    logger.info(f"[TRIGGER] Trigger Source: {trigger_source}")


def set_cognito_response_messages(
    event: Dict[str, Any], code: str, is_resend: bool = False
) -> None:
    """
    Sets email message and subject for Cognito verification code emails

    Args:
        event: The Cognito event dictionary to modify
        code: The verification code to include in the email
        is_resend: Whether this is a resend request (affects messaging)
    """
    subject_prefix = (
        "Your new verification code" if is_resend else "Your verification code"
    )
    subject = f"{subject_prefix}: {code}"

    action_text = "resend" if is_resend else "request"

    html_message = f"""<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #2c3e50;">Your Confirmation Code</h2>

        <p><strong>Your confirmation code is: <span style="font-size: 24px; font-weight: bold; color: #3498db; background: #f8f9fa; padding: 10px; border-radius: 5px; display: inline-block;">{code}</span></strong></p>

        <p>Please enter this code to complete your account verification.</p>

        <p style="color: #e74c3c;"><strong>This code will expire in 15 minutes for security purposes.</strong></p>

        <p style="color: #7f8c8d; font-size: 14px;">If you didn't {action_text} this code, please ignore this email.</p>

        <hr style="border: none; height: 1px; background: #ecf0f1; margin: 20px 0;">

        <p style="color: #7f8c8d; font-size: 14px;">
            Best regards,<br>
            <strong>Lenslate Team</strong>
        </p>
    </div>
</body>
</html>"""

    event["response"]["emailMessage"] = html_message.strip()
    event["response"]["emailSubject"] = subject


def handle_pre_signup(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle PreSignUp trigger to check if user already exists and their verification status

    Returns:
        The modified event dictionary
    """
    user_pool_id = event.get("userPoolId")
    email = event.get("userName")

    if not user_pool_id or not email:
        logger.warning("Missing user pool ID or email in PreSignUp event")
        performance_monitor.persist_metrics()
        return event

    logger.info(f"[CHECK] Checking if user {email} already exists")

    try:
        cognito_client = get_cognito_client()
        start_time = time.time()

        user_response = cognito_client.admin_get_user(
            UserPoolId=user_pool_id, Username=email
        )

        duration = time.time() - start_time
        performance_monitor.record_operation("cognito_admin_get_user", duration, True)

        logger.info(f"[USER] User {email} already exists, checking verification status")

        user_status = user_response.get("UserStatus", "")
        email_verified = False

        for attr in user_response.get("UserAttributes", []):
            if attr["Name"] == "email_verified" and attr["Value"] == "true":
                email_verified = True
                break

        if user_status == "CONFIRMED" and email_verified:
            logger.info(
                f"[BLOCK] User {email} exists and is verified - blocking signup"
            )
            raise Exception(
                "An account with this email already exists and is verified. Please sign in instead."
            )
        elif user_status in ["UNCONFIRMED", "FORCE_CHANGE_PASSWORD"]:
            logger.info(
                f"[ALLOW] User {email} exists but not confirmed - allowing resend"
            )
            performance_monitor.persist_metrics()
            return event
        else:
            logger.warning(f"[WARNING] Unknown user status for {email}: {user_status}")
            performance_monitor.persist_metrics()
            return event

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "UserNotFoundException":
            logger.info(f"[ALLOW] User {email} doesn't exist - allowing new signup")
            performance_monitor.persist_metrics()
            return event
        else:
            logger.warning(
                f"[WARNING] Unexpected error checking user {email}: {error_code}"
            )
            performance_monitor.persist_metrics()
            return event


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Cognito Lambda trigger to handle various Cognito events
    """

    logger.info("[START] COGNITO TRIGGER RECEIVED!")
    logger.info(f"[TRIGGER] Trigger Source: {event.get('triggerSource', 'UNKNOWN')}")
    logger.info(f"[EVENT] Full Event: {json.dumps(event, indent=2)}")

    trigger = event.get("triggerSource")

    if trigger == "CustomMessage_SignUp":
        email, code = extract_email_and_code(event)
        log_cognito_code(trigger, email, code)
        set_cognito_response_messages(event, code, is_resend=False)
        logger.info(f"[SUCCESS] Processed CustomMessage_SignUp for {email}")

    elif trigger == "CustomMessage_ResendCode":
        email, code = extract_email_and_code(event)
        log_cognito_code(trigger, email, code)
        set_cognito_response_messages(event, code, is_resend=True)
        logger.info(f"[SUCCESS] Processed CustomMessage_ResendCode for {email}")

    elif trigger == "PreSignUp_SignUp":
        email = event.get("userName", "unknown")
        logger.info(f"[PROCESS] Processing PreSignUp for {email}")
        event = handle_pre_signup(event)
        logger.info(f"[SUCCESS] Processed PreSignUp_SignUp for {email}")

    else:
        logger.warning(f"[WARNING] UNHANDLED TRIGGER: {trigger}")
        logger.info(f"[EVENT] Event structure: {json.dumps(event, indent=2)}")

    logger.info(f"[COMPLETE] Lambda execution completed for trigger: {trigger}")
    performance_monitor.persist_metrics()
    return event

import json
import logging
from typing import Any, Dict, Tuple

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def extract_email_and_code(event: Dict[str, Any]) -> Tuple[str, str]:
    request = event.get("request", {})
    user_attributes = request.get("userAttributes", {})
    email = user_attributes.get("email", "unknown")
    code = request.get("codeParameter")
    return email, code


def log_cognito_code(trigger_source: str, email: str, code: str) -> None:
    label = (
        "EMAIL CONFIRMATION CODE"
        if trigger_source == "CustomMessage_SignUp"
        else "RESENT EMAIL CONFIRMATION CODE"
    )
    logger.info(f"🔐 {label} FOR {email}: {code}")
    logger.info(f"📧 User Email: {email}")
    logger.info(f"🎯 Trigger Source: {trigger_source}")


def set_cognito_response_messages(
    event: Dict[str, Any], code: str, is_resend: bool = False
) -> None:
    if not is_resend:
        subject = f"Your verification code: {code}"
        message = f"""
Your confirmation code is: {code}

Please enter this code to complete your account verification.

If you didn't request this code, please ignore this email.
""".strip()
    else:
        subject = f"Your new verification code: {code}"
        message = f"""
Your new confirmation code is: {code}

Please enter this code to complete your account verification.

If you didn't request this code, please ignore this email.
""".strip()
    event["response"]["emailMessage"] = message
    event["response"]["emailSubject"] = subject


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Cognito Lambda trigger to log confirmation codes for debugging
    This function is triggered on custom message generation
    """

    logger.info(f"Cognito trigger event: {json.dumps(event, indent=2)}")

    trigger = event.get("triggerSource")
    if trigger == "CustomMessage_SignUp":
        email, code = extract_email_and_code(event)
        log_cognito_code(trigger, email, code)
        set_cognito_response_messages(event, code, is_resend=False)
    elif trigger == "CustomMessage_ResendCode":
        email, code = extract_email_and_code(event)
        log_cognito_code(trigger, email, code)
        set_cognito_response_messages(event, code, is_resend=True)

    return event

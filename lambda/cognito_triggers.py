import json
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    """
    Cognito Lambda trigger to log confirmation codes for debugging
    This function is triggered on custom message generation
    """

    logger.info(f"Cognito trigger event: {json.dumps(event, indent=2)}")

    # Check if this is a confirmation code message
    if event.get("triggerSource") == "CustomMessage_SignUp":
        user_attributes = event.get("request", {}).get("userAttributes", {})
        email = user_attributes.get("email", "unknown")

        # Extract confirmation code from the message
        code_placeholder = event.get("request", {}).get("codeParameter")

        # Log the confirmation code for debugging
        logger.info(f"🔐 EMAIL CONFIRMATION CODE FOR {email}: {code_placeholder}")
        logger.info(f"📧 User Email: {email}")
        logger.info(f"🎯 Trigger Source: {event.get('triggerSource')}")

        # Customize the message if needed
        event["response"][
            "emailMessage"
        ] = f"""
Your confirmation code is: {code_placeholder}

Please enter this code to complete your account verification.

If you didn't request this code, please ignore this email.
        """.strip()

        event["response"][
            "emailSubject"
        ] = f"Your verification code: {code_placeholder}"

    elif event.get("triggerSource") == "CustomMessage_ResendCode":
        user_attributes = event.get("request", {}).get("userAttributes", {})
        email = user_attributes.get("email", "unknown")

        # Extract confirmation code from the message
        code_placeholder = event.get("request", {}).get("codeParameter")

        # Log the resent confirmation code
        logger.info(f"🔐 RESENT EMAIL CONFIRMATION CODE FOR {email}: {code_placeholder}")
        logger.info(f"📧 User Email: {email}")
        logger.info(f"🎯 Trigger Source: {event.get('triggerSource')}")

        # Customize the resend message
        event["response"][
            "emailMessage"
        ] = f"""
Your new confirmation code is: {code_placeholder}

Please enter this code to complete your account verification.

If you didn't request this code, please ignore this email.
        """.strip()

        event["response"][
            "emailSubject"
        ] = f"Your new verification code: {code_placeholder}"

    return event

"""
Performance Handler Lambda Function

This Lambda function provides API endpoints for retrieving performance metrics
from the Lenslate application. It supports real-time metrics, historical data,
and AWS service performance breakdown for the dashboard visualization.
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import jwt
import requests
from aws_clients import (
    PERFORMANCE_TABLE,
    PerformanceMonitor,
    performance_monitor,
    safe_dynamodb_call,
)
from botocore.exceptions import ClientError
from jose import JOSEError

# Configure structured logging for CloudWatch
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# Create console handler with JSON formatter for CloudWatch
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)


class CloudWatchFormatter(logging.Formatter):
    """JSON formatter for CloudWatch Logs"""

    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
            "module": "performance_handler",
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add any extra fields from the record
        for key, value in record.__dict__.items():
            if key not in [
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "getMessage",
                "exc_info",
                "exc_text",
                "stack_info",
            ]:
                log_entry[key] = value

        return json.dumps(log_entry)


formatter = CloudWatchFormatter()
handler.setFormatter(formatter)
logger.addHandler(handler)


def get_cors_headers():
    """Get CORS headers for API responses."""
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token",
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        "Content-Type": "application/json",
    }


def create_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Create a standardized API response."""
    return {
        "statusCode": status_code,
        "headers": get_cors_headers(),
        "body": json.dumps(body),
    }


# --- Environment Variables ---
COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID")
COGNITO_CLIENT_ID = os.environ.get("COGNITO_CLIENT_ID")
AWS_REGION = os.environ.get("AWS_REGION")

# --- Cached JWKS ---
jwks = None


def get_jwks():
    """
    Retrieves and caches the JSON Web Key Set (JWKS) from the Cognito User Pool.
    """
    global jwks
    if jwks:
        return jwks

    if not all([COGNITO_USER_POOL_ID, AWS_REGION]):
        raise ValueError("Cognito User Pool ID and/or AWS Region not configured.")

    jwks_url = f"https://cognito-idp.{AWS_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}/.well-known/jwks.json"
    try:
        response = requests.get(jwks_url)
        response.raise_for_status()
        jwks = response.json()["keys"]
        return jwks
    except requests.exceptions.RequestException as e:
        logger.error(f"PerformanceHandler: Failed to fetch JWKS from {jwks_url}: {e}")
        raise ValueError("Could not fetch signing keys from Cognito.")


def extract_user_from_token(event: Dict[str, Any]) -> str:
    """
    Extracts and validates the JWT token from the Authorization header.

    Returns the username (sub) if the token is valid.
    Raises ValueError if the token is invalid or missing.
    """
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

        # 1. Get the public key from Cognito
        public_keys = get_jwks()
        unverified_header = jwt.get_unverified_header(token)
        rsa_key = None
        for key in public_keys:
            if key["kid"] == unverified_header["kid"]:
                # Create a PyJWK object from the key data
                rsa_key = jwt.PyJWK(key).key
                break

        if not rsa_key:
            raise ValueError("Public key not found in JWKS")

        # 2. Verify the token's signature and claims
        claims = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience=COGNITO_CLIENT_ID,
            issuer=f"https://cognito-idp.{AWS_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}",
        )

        # 3. Return the 'sub' claim (user's unique identifier)
        username = claims.get("sub")
        if not username:
            raise ValueError("Token does not contain a 'sub' claim.")

        logger.info(
            f"PerformanceHandler: Successfully validated token for user: {username}"
        )
        return username

    except JOSEError as e:
        logger.error(f"PerformanceHandler: JWT validation error: {str(e)}")
        raise ValueError(f"Token validation failed: {str(e)}")
    except Exception as e:
        logger.error(f"PerformanceHandler: Failed to extract user from token: {str(e)}")
        raise ValueError(f"Invalid authorization token: {str(e)}")


def get_current_metrics() -> Dict[str, Any]:
    """Get real-time metrics from all active Lambda functions.

    Returns:
        Dict containing current performance metrics
    """
    try:
        logger.info("PerformanceHandler: Retrieving current metrics")
        start_time = time.time()

        # Get current metrics from the global performance monitor
        current_metrics = performance_monitor.get_metrics()
        logger.debug(
            f"PerformanceHandler: Current session metrics: {json.dumps(current_metrics, default=str)}"
        )

        # Get recent metrics from DynamoDB (last 5 minutes)
        current_time = datetime.utcnow()
        five_minutes_ago = current_time - timedelta(minutes=5)
        start_timestamp = five_minutes_ago.isoformat() + "Z"

        logger.debug(
            f"PerformanceHandler: Querying DynamoDB for metrics since {start_timestamp}"
        )
        logger.debug(f"PerformanceHandler: Using table: {PERFORMANCE_TABLE}")

        # Query recent metrics from all functions
        response = safe_dynamodb_call(
            "scan",
            TableName=PERFORMANCE_TABLE,
            FilterExpression="#ts >= :start_time",
            ExpressionAttributeNames={"#ts": "timestamp"},
            ExpressionAttributeValues={":start_time": {"S": start_timestamp}},
        )

        items = response.get("Items", [])
        logger.debug(f"PerformanceHandler: DynamoDB returned {len(items)} items")

        if len(items) > 0:
            logger.debug(
                f"PerformanceHandler: First item sample: {json.dumps(items[0], default=str)}"
            )
        else:
            logger.warning("PerformanceHandler: No items found in DynamoDB scan")

        # Aggregate recent data
        functions_data = {}
        total_calls = 0
        total_failures = 0
        total_duration = 0

        logger.debug(f"PerformanceHandler: Starting aggregation of {len(items)} items")

        for item in items:
            func_name = item["function_name"]["S"]
            operations = json.loads(item["operations"]["S"])

            logger.debug(
                f"PerformanceHandler: Processing function {func_name} with operations: {operations}"
            )

            if func_name not in functions_data:
                functions_data[func_name] = {
                    "total_calls": 0,
                    "total_duration": 0,
                    "failures": 0,
                    "operations": {},
                }

            for op_name, op_data in operations.items():
                functions_data[func_name]["total_calls"] += op_data["total_calls"]
                functions_data[func_name]["total_duration"] += op_data["total_duration"]
                functions_data[func_name]["failures"] += op_data["failures"]

                total_calls += op_data["total_calls"]
                total_duration += op_data["total_duration"]
                total_failures += op_data["failures"]

                if op_name not in functions_data[func_name]["operations"]:
                    functions_data[func_name]["operations"][op_name] = {
                        "total_calls": 0,
                        "total_duration": 0,
                        "failures": 0,
                        "avg_duration": 0,
                    }

                op_func_data = functions_data[func_name]["operations"][op_name]
                op_func_data["total_calls"] += op_data["total_calls"]
                op_func_data["total_duration"] += op_data["total_duration"]
                op_func_data["failures"] += op_data["failures"]

                if op_func_data["total_calls"] > 0:
                    op_func_data["avg_duration"] = (
                        op_func_data["total_duration"] / op_func_data["total_calls"]
                    )

        # Calculate success rate
        success_rate = 0
        if total_calls > 0:
            success_rate = ((total_calls - total_failures) / total_calls) * 100

        logger.debug(
            f"PerformanceHandler: Aggregation complete - Functions: {len(functions_data)}, Total calls: {total_calls}, Failures: {total_failures}, Success rate: {success_rate}"
        )

        # Record performance metrics for this operation
        duration = time.time() - start_time
        performance_monitor.record_operation("get_current_metrics", duration, True)

        # Prepare raw data for transformation
        raw_data = {
            "time_range": "current",
            "functions": functions_data,
            "services": {},  # Services are aggregated from functions in transform function
            "summary": {
                "total_functions": len(functions_data),
                "total_calls": total_calls,
                "total_failures": total_failures,
                "success_rate": round(success_rate, 2),
                "avg_response_time": round(
                    total_duration / total_calls if total_calls > 0 else 0, 3
                ),
            },
            "retrieved_at": current_time.isoformat() + "Z",
            "current_session": current_metrics,
        }

        logger.debug(
            f"PerformanceHandler: Raw data before transformation: {json.dumps(raw_data, default=str, indent=2)}"
        )

        # Transform for frontend
        result = transform_metrics_for_frontend(raw_data)
        result["current_session"] = current_metrics

        logger.info(
            f"PerformanceHandler: Retrieved current metrics for {result.get('total_functions', 0)} functions"
        )
        logger.debug(
            f"PerformanceHandler: Final result: {json.dumps(result, default=str, indent=2)}"
        )
        return result

    except ClientError as e:
        logger.error(f"PerformanceHandler: DynamoDB error getting current metrics: {e}")
        return {
            "error": "Database error",
            "message": str(e),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    except Exception as e:
        logger.error(
            f"PerformanceHandler: Unexpected error getting current metrics: {e}"
        )
        return {
            "error": "Internal error",
            "message": str(e),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }


def transform_metrics_for_frontend(aggregated_data: Dict[str, Any]) -> Dict[str, Any]:
    """Transform backend metrics data to match frontend expectations.

    Args:
        aggregated_data: Raw metrics data from PerformanceMonitor

    Returns:
        Dict: Transformed data structure for frontend consumption
    """
    try:
        logger.debug(
            f"PerformanceHandler: Starting transformation of data: {json.dumps(aggregated_data, default=str, indent=2)}"
        )

        # Transform functions from dict to array format expected by frontend
        functions_array = []
        if "functions" in aggregated_data and aggregated_data["functions"]:
            logger.debug(
                f"PerformanceHandler: Processing {len(aggregated_data['functions'])} functions for transformation"
            )

            for func_name, func_data in aggregated_data["functions"].items():
                logger.debug(
                    f"PerformanceHandler: Transforming function {func_name}: {func_data}"
                )

                function_obj = {
                    "name": func_name,
                    "metrics": {
                        "avgResponseTime": func_data.get("avg_response_time", 0),
                        "successRate": func_data.get("success_rate", 0),
                        "totalCalls": func_data.get("total_calls", 0),
                        "totalFailures": func_data.get("total_failures", 0),
                    },
                    "operations": func_data.get("operations", {}),
                }
                functions_array.append(function_obj)
                logger.debug(
                    f"PerformanceHandler: Transformed function object: {function_obj}"
                )
        else:
            logger.warning(
                "PerformanceHandler: No functions data found in aggregated_data or functions is empty"
            )

        # Generate alerts based on performance thresholds
        alerts = []
        logger.debug(
            "PerformanceHandler: Generating alerts based on performance thresholds"
        )

        # Check for high error rates
        success_rate = aggregated_data.get("summary", {}).get("success_rate", 100)
        if success_rate < 95:
            alert = {
                "type": "error_rate",
                "severity": "high",
                "message": "High Error Rate",
                "details": f"Success rate is {success_rate:.1f}%",
            }
            alerts.append(alert)
            logger.debug(f"PerformanceHandler: Added error rate alert: {alert}")

        # Check for slow response times
        avg_response = aggregated_data.get("summary", {}).get("avg_response_time", 0)
        if avg_response > 2.0:  # 2+ seconds
            alert = {
                "type": "slow_response",
                "severity": "medium",
                "message": "Slow Response Time",
                "details": f"Average response time is {avg_response:.2f}s",
            }
            alerts.append(alert)
            logger.debug(f"PerformanceHandler: Added slow response alert: {alert}")

        # Check for low activity (no recent calls)
        total_calls = aggregated_data.get("summary", {}).get("total_calls", 0)
        if total_calls == 0:
            alert = {
                "type": "low_activity",
                "severity": "low",
                "message": "Low Activity",
                "details": "No recent function calls detected",
            }
            alerts.append(alert)
            logger.debug(f"PerformanceHandler: Added low activity alert: {alert}")

        result = {
            "functions": functions_array,
            "services": aggregated_data.get("services", {}),
            "alerts": alerts,
            "summary": aggregated_data.get("summary", {}),
            "time_range": aggregated_data.get("time_range", "1h"),
            "total_functions": len(functions_array),
            "retrieved_at": aggregated_data.get("retrieved_at"),
        }

        logger.debug(
            f"PerformanceHandler: Transformation complete. Final result: {json.dumps(result, default=str, indent=2)}"
        )
        return result

    except Exception as e:
        logger.error(f"PerformanceHandler: Error transforming metrics data: {e}")
        return {
            "functions": [],
            "services": {},
            "alerts": [
                {
                    "type": "system_error",
                    "severity": "high",
                    "message": "Data Processing Error",
                    "details": "Unable to process performance metrics",
                }
            ],
            "summary": {},
            "time_range": "1h",
            "total_functions": 0,
        }


def get_historical_metrics(
    time_range: str = "1h", function_name: Optional[str] = None
) -> Dict[str, Any]:
    """Get historical performance data with time range filtering.

    Args:
        time_range: Time range for metrics ('1h', '6h', '24h', '7d')
        function_name: Optional filter by specific Lambda function

    Returns:
        Dict containing historical performance metrics
    """
    try:
        logger.info(
            f"PerformanceHandler: Retrieving historical metrics for range: {time_range}, function: {function_name}"
        )
        start_time = time.time()

        # Use the PerformanceMonitor to get aggregated metrics
        monitor = PerformanceMonitor()
        logger.debug(
            "PerformanceHandler: Created PerformanceMonitor instance, calling get_aggregated_metrics"
        )

        aggregated_data = monitor.get_aggregated_metrics(time_range, function_name)
        logger.debug(
            f"PerformanceHandler: get_aggregated_metrics returned: {json.dumps(aggregated_data, default=str, indent=2)}"
        )

        # Record performance metrics for this operation
        duration = time.time() - start_time
        performance_monitor.record_operation("get_historical_metrics", duration, True)

        if "error" in aggregated_data:
            logger.error(
                f"PerformanceHandler: Error in aggregated metrics: {aggregated_data['error']}"
            )
            return aggregated_data

        # Add metadata to raw data
        aggregated_data["retrieved_at"] = datetime.utcnow().isoformat() + "Z"
        aggregated_data["function_filter"] = function_name

        logger.debug(
            f"PerformanceHandler: Raw aggregated data with metadata: {json.dumps(aggregated_data, default=str, indent=2)}"
        )

        # Transform data for frontend consumption
        result = transform_metrics_for_frontend(aggregated_data)

        logger.info(
            f"PerformanceHandler: Retrieved historical metrics for {result.get('total_functions', 0)} functions"
        )
        logger.debug(
            f"PerformanceHandler: Final historical result: {json.dumps(result, default=str, indent=2)}"
        )
        return result

    except Exception as e:
        logger.error(
            f"PerformanceHandler: Unexpected error getting historical metrics: {e}"
        )
        return {
            "error": "Internal error",
            "message": str(e),
            "time_range": time_range,
            "function_filter": function_name,
        }


def get_service_breakdown(time_range: str = "1h") -> Dict[str, Any]:
    """Get performance metrics grouped by AWS service.

    Args:
        time_range: Time range for metrics ('1h', '6h', '24h', '7d')

    Returns:
        Dict containing AWS service performance breakdown
    """
    try:
        logger.info(
            f"PerformanceHandler: Retrieving service breakdown for range: {time_range}"
        )
        start_time = time.time()

        # Use the PerformanceMonitor to get service breakdown
        monitor = PerformanceMonitor()
        service_data = monitor.get_service_breakdown(time_range)

        # Record performance metrics for this operation
        duration = time.time() - start_time
        performance_monitor.record_operation("get_service_breakdown", duration, True)

        if "error" in service_data:
            logger.error(
                f"PerformanceHandler: Error in service breakdown: {service_data['error']}"
            )
            return service_data

        # Add metadata
        result = {"retrieved_at": datetime.utcnow().isoformat() + "Z", **service_data}

        logger.info(
            f"PerformanceHandler: Retrieved service breakdown for {service_data.get('total_services', 0)} services"
        )
        return result

    except Exception as e:
        logger.error(
            f"PerformanceHandler: Unexpected error getting service breakdown: {e}"
        )
        return {"error": "Internal error", "message": str(e), "time_range": time_range}


def save_frontend_metric(metric: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """
    Saves a frontend performance metric to DynamoDB.

    Args:
        metric: The metric data received from the frontend.
        user_id: The ID of the user who sent the metric.

    Returns:
        A response dictionary.
    """
    try:
        metric_name = metric.get("name")
        if not metric_name:
            logger.warning("PerformanceHandler: Frontend metric is missing 'name'")
            return create_response(400, {"error": "Metric name is required"})

        timestamp = metric.get("timestamp", datetime.utcnow().isoformat() + "Z")
        pk = f"FRONTEND#{metric_name}"
        sk = timestamp

        item = {
            "PK": {"S": pk},
            "SK": {"S": sk},
            "metric_name": {"S": metric_name},
            "user_id": {"S": user_id},
            "value": {"S": json.dumps(metric.get("value"))},
            "delta": {"N": str(metric.get("delta", 0))},
            "id": {"S": metric.get("id", "")},
            "timestamp": {"S": timestamp},
            "ttl": {"N": str(int(time.time()) + (7 * 24 * 60 * 60))},  # 7-day TTL
        }

        logger.info(
            f"PerformanceHandler: Saving frontend metric '{metric_name}' for user '{user_id}'"
        )
        safe_dynamodb_call("put_item", TableName=PERFORMANCE_TABLE, Item=item)

        return create_response(202, {"status": "accepted"})

    except Exception as e:
        logger.error(f"PerformanceHandler: Error saving frontend metric: {e}")
        return create_response(
            500, {"error": "Internal server error", "message": str(e)}
        )


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for performance metrics API requests.

    Supports the following endpoints:
    - GET /performance - Get current metrics
    - GET /performance?time_range=1h - Get historical metrics
    - GET /performance?function_name=image_processor - Filter by function
    - GET /performance/services - Get service breakdown
    """
    logger.info("PerformanceHandler: Lambda function invoked")
    logger.debug(
        f"PerformanceHandler: Full event: {json.dumps(event, default=str, indent=2)}"
    )
    logger.debug(f"PerformanceHandler: Context: {context}")

    try:
        # Handle CORS preflight requests
        if event.get("httpMethod") == "OPTIONS":
            logger.info("PerformanceHandler: Handling CORS preflight request")
            return create_response(200, {"message": "CORS preflight successful"})

        # Extract HTTP method and path
        http_method = (
            event.get("requestContext", {}).get("http", {}).get("method", "").upper()
        )
        path = event.get("requestContext", {}).get("http", {}).get("path", "")

        # Fallback to v1 format if v2 fields are not present
        if not http_method:
            http_method = event.get("httpMethod", "").upper()
        if not path:
            path = event.get("path", "")

        logger.info(f"PerformanceHandler: Processing {http_method} request to {path}")

        # Validate authentication
        try:
            username = extract_user_from_token(event)
            logger.info(f"PerformanceHandler: Authenticated user: {username}")
        except ValueError as e:
            logger.error(f"PerformanceHandler: Authentication error: {str(e)}")
            return create_response(
                401, {"error": "Authentication required", "message": str(e)}
            )

        # Route based on method and path
        if http_method == "POST" and path.endswith("/performance/frontend"):
            try:
                body = json.loads(event.get("body", "{}"))
                return save_frontend_metric(body, username)
            except json.JSONDecodeError:
                logger.warning("PerformanceHandler: Invalid JSON in POST request body")
                return create_response(400, {"error": "Invalid JSON format"})

        elif http_method == "GET":
            # Extract query parameters
            query_params = event.get("queryStringParameters") or {}
            time_range = query_params.get("time_range", "1h")
            function_name = query_params.get("function_name")

            # Validate time_range parameter
            valid_time_ranges = ["1h", "6h", "24h", "7d"]
            if time_range not in valid_time_ranges:
                logger.warning(f"PerformanceHandler: Invalid time_range: {time_range}")
                return create_response(
                    400,
                    {
                        "error": "Invalid parameter",
                        "message": f"time_range must be one of: {', '.join(valid_time_ranges)}",
                        "valid_values": valid_time_ranges,
                    },
                )

            # Route based on path
            logger.debug(
                f"PerformanceHandler: Routing request - path: {path}, query_params: {query_params}"
            )

            if path.endswith("/services") or path.endswith("/service-breakdown"):
                # Service breakdown endpoint
                logger.info(
                    f"PerformanceHandler: Routing to service breakdown endpoint with time_range: {time_range}"
                )
                result = get_service_breakdown(time_range)

                if "error" in result:
                    status_code = 500 if result["error"] == "Internal error" else 400
                    logger.error(
                        f"PerformanceHandler: Service breakdown returned error: {result}"
                    )
                    return create_response(status_code, result)

                logger.info(
                    "PerformanceHandler: Service breakdown completed successfully"
                )
                return create_response(200, result)

            elif path.endswith("/current") or (
                not query_params and path.endswith("/performance")
            ):
                # Current metrics endpoint
                logger.info("PerformanceHandler: Routing to current metrics endpoint")
                result = get_current_metrics()

                if "error" in result:
                    status_code = 500 if result["error"] == "Internal error" else 400
                    logger.error(
                        f"PerformanceHandler: Current metrics returned error: {result}"
                    )
                    return create_response(status_code, result)

                logger.info(
                    "PerformanceHandler: Current metrics completed successfully"
                )
                return create_response(200, result)

            else:
                # Historical metrics endpoint (default)
                logger.info(
                    f"PerformanceHandler: Routing to historical metrics endpoint with time_range: {time_range}, function_name: {function_name}"
                )
                result = get_historical_metrics(time_range, function_name)

                if "error" in result:
                    status_code = 500 if result["error"] == "Internal error" else 400
                    logger.error(
                        f"PerformanceHandler: Historical metrics returned error: {result}"
                    )
                    return create_response(status_code, result)

                logger.info(
                    "PerformanceHandler: Historical metrics completed successfully"
                )
                return create_response(200, result)
        else:
            logger.warning(
                f"PerformanceHandler: Unsupported method or path: {http_method} {path}"
            )
            return create_response(
                405,
                {
                    "error": "Method not allowed",
                    "message": f"Method {http_method} for path {path} is not supported",
                },
            )

    except Exception as e:
        logger.error(
            f"PerformanceHandler: Unexpected error in lambda_handler: {str(e)}"
        )
        return create_response(
            500,
            {
                "error": "Internal server error",
                "message": "An unexpected error occurred while processing the request",
            },
        )

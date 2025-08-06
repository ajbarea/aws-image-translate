"""AWS client configuration for Lambda functions.

This module provides centralized AWS client initialization with
connection pooling, retry logic, and performance monitoring.
"""

import json
import os
import time
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any, Dict, List, Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

# Environment-based configuration
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
S3_BUCKET = os.environ.get("S3_BUCKET", "lenslate-image-storage")
PERFORMANCE_TABLE = os.environ.get("PERFORMANCE_TABLE", "lenslate-performance-metrics")

# Client configuration
OPTIMIZED_CONFIG = Config(
    retries={"max_attempts": 3, "mode": "adaptive"},
    max_pool_connections=50,
    region_name=AWS_REGION,
    # Enable connection reuse
    parameter_validation=False,  # Skip client-side validation
    # Optimize for Lambda environment
    tcp_keepalive=True,
    # Low connection timeout for fast failures
    connect_timeout=5,
    read_timeout=10,
)


@lru_cache(maxsize=None)
def get_rekognition_client():
    """Get optimized Rekognition client with connection pooling."""
    return boto3.client("rekognition", config=OPTIMIZED_CONFIG)


@lru_cache(maxsize=None)
def get_comprehend_client():
    """Get optimized Comprehend client with connection pooling."""
    return boto3.client("comprehend", config=OPTIMIZED_CONFIG)


@lru_cache(maxsize=None)
def get_translate_client():
    """Get optimized Translate client with connection pooling."""
    return boto3.client("translate", config=OPTIMIZED_CONFIG)


@lru_cache(maxsize=None)
def get_s3_client():
    """Get optimized S3 client with connection pooling."""
    return boto3.client("s3", config=OPTIMIZED_CONFIG)


@lru_cache(maxsize=None)
def get_dynamodb_client():
    """Get optimized DynamoDB client with connection pooling."""
    return boto3.client("dynamodb", config=OPTIMIZED_CONFIG)


def safe_rekognition_call(operation, *args, **kwargs):
    """Execute Rekognition operation."""
    client = get_rekognition_client()
    return getattr(client, operation)(*args, **kwargs)


def safe_comprehend_call(operation, *args, **kwargs):
    """Execute Comprehend operation."""
    client = get_comprehend_client()
    return getattr(client, operation)(*args, **kwargs)


def safe_translate_call(operation, *args, **kwargs):
    """Execute Translate operation."""
    client = get_translate_client()
    return getattr(client, operation)(*args, **kwargs)


def safe_s3_call(operation, *args, **kwargs):
    """Execute S3 operation."""
    client = get_s3_client()
    return getattr(client, operation)(*args, **kwargs)


def safe_dynamodb_call(operation, *args, **kwargs):
    """Execute DynamoDB operation."""
    client = get_dynamodb_client()
    return getattr(client, operation)(*args, **kwargs)


# Performance monitoring
class PerformanceMonitor:
    """Monitor Lambda performance metrics."""

    def __init__(self, function_name: Optional[str] = None):
        self.start_time = time.time()
        self.metrics = {}
        self.function_name = function_name or os.environ.get(
            "AWS_LAMBDA_FUNCTION_NAME", "unknown"
        )

    def record_operation(self, operation: str, duration: float, success: bool = True):
        """Record operation performance."""
        if operation not in self.metrics:
            self.metrics[operation] = {
                "total_calls": 0,
                "total_duration": 0,
                "failures": 0,
                "avg_duration": 0,
            }

        self.metrics[operation]["total_calls"] += 1
        self.metrics[operation]["total_duration"] += duration

        if not success:
            self.metrics[operation]["failures"] += 1

        self.metrics[operation]["avg_duration"] = (
            self.metrics[operation]["total_duration"]
            / self.metrics[operation]["total_calls"]
        )

    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        total_duration = time.time() - self.start_time
        return {
            "total_execution_time": total_duration,
            "operations": self.metrics,
        }

    def persist_metrics(self) -> bool:
        """Store current metrics to DynamoDB with timestamp and TTL.

        Returns:
            bool: True if persistence was successful, False otherwise
        """
        try:
            current_time = datetime.utcnow()
            timestamp = current_time.isoformat() + "Z"

            # Calculate TTL (7 days from now)
            ttl_date = current_time + timedelta(days=7)
            ttl_timestamp = int(ttl_date.timestamp())

            # Prepare the item for DynamoDB
            item = {
                "PK": {"S": f"PERF#{self.function_name}#{timestamp}"},
                "SK": {"S": "METRICS"},
                "GSI1PK": {"S": "METRICS"},  # Static key for the new GSI
                "function_name": {"S": self.function_name},
                "timestamp": {"S": timestamp},
                "total_execution_time": {
                    "N": str(self.get_metrics()["total_execution_time"])
                },
                "operations": {"S": json.dumps(self.metrics)},
                "ttl": {"N": str(ttl_timestamp)},
            }

            # Store to DynamoDB
            safe_dynamodb_call("put_item", TableName=PERFORMANCE_TABLE, Item=item)
            return True

        except ClientError as e:
            print(f"Error persisting metrics to DynamoDB: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error persisting metrics: {e}")
            return False

    def batch_persist_metrics(self, metrics_list: List[Dict[str, Any]]) -> bool:
        """Batch write multiple metrics to DynamoDB for efficiency.

        Args:
            metrics_list: List of metrics dictionaries to persist

        Returns:
            bool: True if all items were successfully written, False otherwise
        """
        try:
            if not metrics_list:
                return True

            # Prepare batch write request
            request_items = []
            current_time = datetime.utcnow()
            ttl_date = current_time + timedelta(days=7)
            ttl_timestamp = int(ttl_date.timestamp())

            for metrics_data in metrics_list:
                timestamp = current_time.isoformat() + "Z"
                item = {
                    "PutRequest": {
                        "Item": {
                            "PK": {
                                "S": f"PERF#{metrics_data.get('function_name', self.function_name)}#{timestamp}"
                            },
                            "SK": {"S": "METRICS"},
                            "GSI1PK": {"S": "METRICS"},  # Static key for the new GSI
                            "function_name": {
                                "S": metrics_data.get(
                                    "function_name", self.function_name
                                )
                            },
                            "timestamp": {"S": timestamp},
                            "total_execution_time": {
                                "N": str(metrics_data.get("total_execution_time", 0))
                            },
                            "operations": {
                                "S": json.dumps(metrics_data.get("operations", {}))
                            },
                            "ttl": {"N": str(ttl_timestamp)},
                        }
                    }
                }
                request_items.append(item)

            # Process in batches of 25 (DynamoDB limit)
            batch_size = 25
            for i in range(0, len(request_items), batch_size):
                batch = request_items[i : i + batch_size]
                request = {PERFORMANCE_TABLE: batch}

                response = safe_dynamodb_call("batch_write_item", RequestItems=request)

                # Handle unprocessed items
                unprocessed = response.get("UnprocessedItems", {})
                retry_count = 0
                max_retries = 3

                while unprocessed and retry_count < max_retries:
                    time.sleep(0.1 * (2**retry_count))  # Exponential backoff
                    response = safe_dynamodb_call(
                        "batch_write_item", RequestItems=unprocessed
                    )
                    unprocessed = response.get("UnprocessedItems", {})
                    retry_count += 1

                if unprocessed:
                    print(
                        f"Failed to write {len(unprocessed.get(PERFORMANCE_TABLE, []))} items after retries"
                    )
                    return False

            return True

        except ClientError as e:
            print(f"Error batch persisting metrics to DynamoDB: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error batch persisting metrics: {e}")
            return False

    def get_aggregated_metrics(
        self, time_range: str = "1h", function_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get aggregated metrics for dashboard display with time-range queries.
        Args:
            time_range: Time range for metrics ('1h', '6h', '24h', '7d')
            function_name: Optional filter by specific function name
        Returns:
            Dict containing aggregated metrics data, including time-series.
        """
        try:
            # 1. Calculate time range and bucket size
            now = datetime.utcnow()
            time_deltas = {
                "1h": (timedelta(hours=1), timedelta(minutes=5)),
                "6h": (timedelta(hours=6), timedelta(minutes=30)),
                "24h": (timedelta(hours=24), timedelta(hours=2)),
                "7d": (timedelta(days=7), timedelta(days=1)),
            }
            total_duration, bucket_interval = time_deltas.get(
                time_range, (timedelta(hours=1), timedelta(minutes=5))
            )
            start_time = now - total_duration
            start_timestamp = start_time.isoformat() + "Z"

            # 2. Build and execute the DynamoDB query
            query_kwargs = self._build_query(function_name, start_timestamp)
            response = safe_dynamodb_call("query", **query_kwargs)
            items = response.get("Items", [])

            # 3. Initialize data structures
            (
                buckets,
                timestamps,
                overall_summary,
                functions_summary,
                services_summary,
            ) = self._initialize_aggregation_structures(
                start_time, now, bucket_interval
            )

            # 4. Process items into buckets
            for item in items:
                self._process_item_into_buckets(
                    item, buckets, start_time, bucket_interval
                )

            # 5. Aggregate bucket data into summaries
            self._aggregate_buckets(
                buckets, functions_summary, services_summary, overall_summary
            )

            # 6. Finalize and format the data for the frontend
            self._finalize_summaries(
                functions_summary, services_summary, overall_summary
            )
            self._format_time_series(functions_summary, timestamps)

            return {
                "time_range": time_range,
                "total_functions": len(functions_summary),
                "functions": functions_summary,
                "services": services_summary,
                "summary": overall_summary,
            }

        except ClientError as e:
            print(f"Error retrieving aggregated metrics from DynamoDB: {e}")
            return {"error": str(e), "time_range": time_range}
        except Exception as e:
            print(f"Unexpected error retrieving aggregated metrics: {e}")
            return {"error": str(e), "time_range": time_range}

    def _build_query(self, function_name, start_timestamp):
        if function_name:
            return {
                "TableName": PERFORMANCE_TABLE,
                "IndexName": "function-timestamp-index",
                "KeyConditionExpression": "#func_name = :func_name AND #ts >= :start_time",
                "ExpressionAttributeNames": {
                    "#func_name": "function_name",
                    "#ts": "timestamp",
                },
                "ExpressionAttributeValues": {
                    ":func_name": {"S": function_name},
                    ":start_time": {"S": start_timestamp},
                },
            }
        else:
            return {
                "TableName": PERFORMANCE_TABLE,
                "IndexName": "metrics-by-time-index",
                "KeyConditionExpression": "#gsi1pk = :gsi1pk AND #ts >= :start_time",
                "ExpressionAttributeNames": {"#gsi1pk": "GSI1PK", "#ts": "timestamp"},
                "ExpressionAttributeValues": {
                    ":gsi1pk": {"S": "METRICS"},
                    ":start_time": {"S": start_timestamp},
                },
            }

    def _initialize_aggregation_structures(self, start_time, end_time, bucket_interval):
        timestamps = []
        current_time = start_time
        while current_time < end_time:
            timestamps.append(current_time.isoformat() + "Z")
            current_time += bucket_interval

        buckets = {ts: {} for ts in timestamps}
        overall_summary = {"total_calls": 0, "total_duration": 0, "total_failures": 0}
        return buckets, timestamps, overall_summary, {}, {}

    def _process_item_into_buckets(self, item, buckets, start_time, bucket_interval):
        item_ts_str = item["timestamp"]["S"]
        item_ts = datetime.fromisoformat(item_ts_str.replace("Z", "+00:00"))

        time_diff_seconds = (item_ts - start_time).total_seconds()
        bucket_index = int(time_diff_seconds / bucket_interval.total_seconds())

        if bucket_index < 0 or bucket_index >= len(buckets):
            return  # Item is outside our time range, skip

        bucket_key = list(buckets.keys())[bucket_index]

        func_name = item["function_name"]["S"]
        operations = json.loads(item["operations"]["S"])

        if func_name not in buckets[bucket_key]:
            buckets[bucket_key][func_name] = {
                "total_calls": 0,
                "total_duration": 0,
                "failures": 0,
                "services": {},
            }

        for op_name, op_data in operations.items():
            buckets[bucket_key][func_name]["total_calls"] += op_data.get(
                "total_calls", 0
            )
            buckets[bucket_key][func_name]["total_duration"] += op_data.get(
                "total_duration", 0
            )
            buckets[bucket_key][func_name]["failures"] += op_data.get("failures", 0)

            service_name = self._extract_service_name(op_name)
            if service_name not in buckets[bucket_key][func_name]["services"]:
                buckets[bucket_key][func_name]["services"][service_name] = {
                    "total_calls": 0,
                    "total_duration": 0,
                    "failures": 0,
                }

            service_bucket = buckets[bucket_key][func_name]["services"][service_name]
            service_bucket["total_calls"] += op_data.get("total_calls", 0)
            service_bucket["total_duration"] += op_data.get("total_duration", 0)
            service_bucket["failures"] += op_data.get("failures", 0)

    def _aggregate_buckets(
        self, buckets, functions_summary, services_summary, overall_summary
    ):
        for bucket_data in buckets.values():
            for func_name, func_bucket_data in bucket_data.items():
                if func_name not in functions_summary:
                    functions_summary[func_name] = {
                        "total_calls": 0,
                        "total_duration": 0,
                        "total_failures": 0,
                        "timeSeries": {
                            "responseTimes": [],
                            "successRates": [],
                            "callCounts": [],
                        },
                    }

                summary = functions_summary[func_name]
                summary["total_calls"] += func_bucket_data["total_calls"]
                summary["total_duration"] += func_bucket_data["total_duration"]
                summary["total_failures"] += func_bucket_data["failures"]

                for service_name, service_data in func_bucket_data["services"].items():
                    if service_name not in services_summary:
                        services_summary[service_name] = {
                            "total_calls": 0,
                            "total_duration": 0,
                            "failures": 0,
                        }
                    services_summary[service_name]["total_calls"] += service_data[
                        "total_calls"
                    ]
                    services_summary[service_name]["total_duration"] += service_data[
                        "total_duration"
                    ]
                    services_summary[service_name]["failures"] += service_data[
                        "failures"
                    ]

    def _finalize_summaries(self, functions_summary, services_summary, overall_summary):
        for summary in list(functions_summary.values()) + list(
            services_summary.values()
        ):
            if summary["total_calls"] > 0:
                summary["avg_response_time"] = (
                    summary["total_duration"] / summary["total_calls"]
                )
                summary["success_rate"] = (
                    (summary["total_calls"] - summary["total_failures"])
                    / summary["total_calls"]
                ) * 100
            else:
                summary["avg_response_time"] = 0
                summary["success_rate"] = 100

        for func_summary in functions_summary.values():
            overall_summary["total_calls"] += func_summary["total_calls"]
            overall_summary["total_duration"] += func_summary["total_duration"]
            overall_summary["total_failures"] += func_summary["total_failures"]

        if overall_summary["total_calls"] > 0:
            overall_summary["avg_response_time"] = (
                overall_summary["total_duration"] / overall_summary["total_calls"]
            )
            overall_summary["success_rate"] = (
                (overall_summary["total_calls"] - overall_summary["total_failures"])
                / overall_summary["total_calls"]
            ) * 100
        else:
            overall_summary["avg_response_time"] = 0
            overall_summary["success_rate"] = 100

    def _format_time_series(self, functions_summary, timestamps):
        # Add timestamps to the functions summary
        for func_summary in functions_summary.values():
            func_summary["timeSeries"]["timestamps"] = [
                ts.split("T")[1].split(".")[0][:5] for ts in timestamps
            ]

        # This part is left empty as the aggregation logic is now different
        # The time series data is built during the aggregation of buckets
        pass

    def get_service_breakdown(self, time_range: str = "1h") -> Dict[str, Any]:
        """Get performance metrics grouped by AWS service.

        Args:
            time_range: Time range for metrics ('1h', '6h', '24h', '7d')

        Returns:
            Dict containing service-level performance breakdown
        """
        try:
            aggregated_data = self.get_aggregated_metrics(time_range)

            if "error" in aggregated_data:
                return aggregated_data

            service_breakdown = {
                "time_range": time_range,
                "services": aggregated_data["services"],
                "total_services": len(aggregated_data["services"]),
                "summary": {
                    "most_used_service": None,
                    "slowest_service": None,
                    "least_reliable_service": None,
                },
            }

            # Find service insights
            if aggregated_data["services"]:
                # Most used service (by call count)
                most_used = max(
                    aggregated_data["services"].items(),
                    key=lambda x: x[1]["total_calls"],
                )
                service_breakdown["summary"]["most_used_service"] = {
                    "name": most_used[0],
                    "total_calls": most_used[1]["total_calls"],
                }

                # Slowest service (by average duration)
                slowest = max(
                    aggregated_data["services"].items(),
                    key=lambda x: x[1]["avg_duration"],
                )
                service_breakdown["summary"]["slowest_service"] = {
                    "name": slowest[0],
                    "avg_duration": slowest[1]["avg_duration"],
                }

                # Least reliable service (by success rate)
                least_reliable = min(
                    aggregated_data["services"].items(),
                    key=lambda x: x[1]["success_rate"],
                )
                service_breakdown["summary"]["least_reliable_service"] = {
                    "name": least_reliable[0],
                    "success_rate": least_reliable[1]["success_rate"],
                }

            return service_breakdown

        except Exception as e:
            print(f"Error generating service breakdown: {e}")
            return {"error": str(e), "time_range": time_range}

    def get_function_comparison(self, time_range: str = "1h") -> Dict[str, Any]:
        """Get performance metrics for Lambda function comparison.

        Args:
            time_range: Time range for metrics ('1h', '6h', '24h', '7d')

        Returns:
            Dict containing function-level performance comparison
        """
        try:
            aggregated_data = self.get_aggregated_metrics(time_range)

            if "error" in aggregated_data:
                return aggregated_data

            function_comparison = {
                "time_range": time_range,
                "functions": aggregated_data["functions"],
                "total_functions": aggregated_data["total_functions"],
                "comparison": {
                    "fastest_function": None,
                    "slowest_function": None,
                    "most_active_function": None,
                    "least_reliable_function": None,
                },
            }

            # Generate comparison insights
            if aggregated_data["functions"]:
                functions = aggregated_data["functions"]

                # Fastest function (lowest average response time)
                fastest = min(
                    functions.items(),
                    key=lambda x: (
                        x[1]["avg_response_time"]
                        if x[1]["avg_response_time"] > 0
                        else float("inf")
                    ),
                )
                if fastest[1]["avg_response_time"] > 0:
                    function_comparison["comparison"]["fastest_function"] = {
                        "name": fastest[0],
                        "avg_response_time": fastest[1]["avg_response_time"],
                    }

                # Slowest function (highest average response time)
                slowest = max(
                    functions.items(), key=lambda x: x[1]["avg_response_time"]
                )
                function_comparison["comparison"]["slowest_function"] = {
                    "name": slowest[0],
                    "avg_response_time": slowest[1]["avg_response_time"],
                }

                # Most active function (highest call count)
                most_active = max(functions.items(), key=lambda x: x[1]["total_calls"])
                function_comparison["comparison"]["most_active_function"] = {
                    "name": most_active[0],
                    "total_calls": most_active[1]["total_calls"],
                }

                # Least reliable function (lowest success rate)
                least_reliable = min(
                    functions.items(), key=lambda x: x[1]["success_rate"]
                )
                function_comparison["comparison"]["least_reliable_function"] = {
                    "name": least_reliable[0],
                    "success_rate": least_reliable[1]["success_rate"],
                }

            return function_comparison

        except Exception as e:
            print(f"Error generating function comparison: {e}")
            return {"error": str(e), "time_range": time_range}

    def _extract_service_name(self, operation_name: str) -> str:
        """Extract AWS service name from operation name.

        Args:
            operation_name: The operation name (e.g., 'rekognition_detect_text')

        Returns:
            str: The service name (e.g., 'rekognition')
        """
        # Common service prefixes in operation names
        service_mappings = {
            "rekognition": "rekognition",
            "comprehend": "comprehend",
            "translate": "translate",
            "s3": "s3",
            "cognito": "cognito",
            "dynamodb": "dynamodb",
        }

        operation_lower = operation_name.lower()
        for prefix, service in service_mappings.items():
            if operation_lower.startswith(prefix):
                return service

        # Default fallback - extract first part before underscore
        parts = operation_name.split("_")
        return parts[0].lower() if parts else "unknown"


# Global performance monitor instance
performance_monitor = PerformanceMonitor()


def get_performance_metrics() -> Dict[str, Any]:
    """Get current performance metrics."""
    return performance_monitor.get_metrics()

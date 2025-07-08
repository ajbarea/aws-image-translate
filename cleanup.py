# pragma: no cover
"""
AWS Resource Cleanup Script

This script helps clean up AWS resources created by the image translation pipeline
to avoid unnecessary costs during development and testing.

Usage:
    python cleanup.py [--dry-run] [--region REGION] [--environment ENV]

Examples:
    python cleanup.py --dry-run                    # Show what would be deleted
    python cleanup.py --environment dev            # Delete dev resources
    python cleanup.py --region us-west-2           # Delete resources in specific region
"""

import argparse
import sys
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError


class AWSResourceCleanup:
    def __init__(self, region: str = "us-east-1", dry_run: bool = False):
        self.region = region
        self.dry_run = dry_run
        self.session = boto3.Session(region_name=region)

        # Initialize clients
        self.dynamodb = self.session.client("dynamodb")
        self.s3 = self.session.client("s3")

        print(f"AWS Cleanup initialized for region: {region}")
        if dry_run:
            print("DRY RUN MODE: No resources will be deleted")

    def list_project_dynamodb_tables(
        self, environment: Optional[str] = None
    ) -> List[str]:
        """List DynamoDB tables related to this project."""
        try:
            response = self.dynamodb.list_tables()
            tables = response.get("TableNames", [])

            # Filter tables related to our project
            project_tables = []
            patterns = ["reddit-ingest", "reddit_ingest"]

            for table in tables:
                if any(pattern in table.lower() for pattern in patterns):
                    if environment is None or environment in table:
                        project_tables.append(table)

            return project_tables
        except ClientError as e:
            print(f"Error listing DynamoDB tables: {e}")
            return []

    def list_project_s3_buckets(self, environment: Optional[str] = None) -> List[str]:
        """List S3 buckets related to this project."""
        try:
            response = self.s3.list_buckets()
            buckets = [bucket["Name"] for bucket in response.get("Buckets", [])]

            # Filter buckets related to our project
            project_buckets = []
            patterns = [
                "ajbarea",
                "image-translate",
                "reddit-image",
                "ajbarea-aws-translate-2025",
            ]

            for bucket in buckets:
                if any(pattern in bucket.lower() for pattern in patterns):
                    if environment is None or environment in bucket:
                        project_buckets.append(bucket)

            return project_buckets
        except ClientError as e:
            print(f"Error listing S3 buckets: {e}")
            return []

    def delete_dynamodb_table(self, table_name: str) -> bool:
        """Delete a DynamoDB table."""
        try:
            if self.dry_run:
                print(f"[DRY RUN] Would delete DynamoDB table: {table_name}")
                return True

            print(f"Deleting DynamoDB table: {table_name}")
            self.dynamodb.delete_table(TableName=table_name)

            # Wait for table to be deleted
            waiter = self.dynamodb.get_waiter("table_not_exists")
            waiter.wait(TableName=table_name)
            print(f"Successfully deleted table: {table_name}")
            return True

        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                print(f"Table {table_name} does not exist")
                return True
            else:
                print(f"Error deleting table {table_name}: {e}")
                return False

    def _dry_run_empty_bucket(self, bucket_name: str) -> bool:
        """Show what would be deleted in dry run mode."""
        response = self.s3.list_objects_v2(Bucket=bucket_name)
        objects = response.get("Contents", [])
        print(
            f"[DRY RUN] Would delete {len(objects)} objects from bucket: {bucket_name}"
        )
        for obj in objects[:5]:  # Show first 5 objects
            print(f"  - {obj['Key']}")
        if len(objects) > 5:
            print(f"  ... and {len(objects) - 5} more objects")
        return True

    def _delete_current_objects(self, bucket_name: str) -> int:
        """Delete all current objects in the bucket."""
        paginator = self.s3.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=bucket_name)

        delete_count = 0
        for page in pages:
            if "Contents" in page:
                objects = [{"Key": obj["Key"]} for obj in page["Contents"]]
                if objects:
                    self.s3.delete_objects(
                        Bucket=bucket_name, Delete={"Objects": objects}
                    )
                    delete_count += len(objects)
        return delete_count

    def _delete_object_versions(self, bucket_name: str) -> None:
        """Delete all object versions and delete markers."""
        paginator = self.s3.get_paginator("list_object_versions")
        pages = paginator.paginate(Bucket=bucket_name)

        for page in pages:
            versions = []
            if "Versions" in page:
                versions.extend(
                    [
                        {"Key": obj["Key"], "VersionId": obj["VersionId"]}
                        for obj in page["Versions"]
                    ]
                )
            if "DeleteMarkers" in page:
                versions.extend(
                    [
                        {"Key": obj["Key"], "VersionId": obj["VersionId"]}
                        for obj in page["DeleteMarkers"]
                    ]
                )

            if versions:
                self.s3.delete_objects(Bucket=bucket_name, Delete={"Objects": versions})

    def empty_s3_bucket(self, bucket_name: str) -> bool:
        """Empty all objects from an S3 bucket."""
        try:
            if self.dry_run:
                return self._dry_run_empty_bucket(bucket_name)

            print(f"Emptying S3 bucket: {bucket_name}")

            # Delete all current objects
            delete_count = self._delete_current_objects(bucket_name)

            # Delete all object versions (if versioning is enabled)
            self._delete_object_versions(bucket_name)

            print(f"Emptied bucket {bucket_name} (deleted {delete_count} objects)")
            return True

        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchBucket":
                print(f"Bucket {bucket_name} does not exist")
                return True
            else:
                print(f"Error emptying bucket {bucket_name}: {e}")
                return False

    def delete_s3_bucket(self, bucket_name: str) -> bool:
        """Delete an S3 bucket (must be empty first)."""
        try:
            if self.dry_run:
                print(f"[DRY RUN] Would delete S3 bucket: {bucket_name}")
                return True

            print(f"Deleting S3 bucket: {bucket_name}")
            self.s3.delete_bucket(Bucket=bucket_name)
            print(f"Successfully deleted bucket: {bucket_name}")
            return True

        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchBucket":
                print(f"Bucket {bucket_name} does not exist")
                return True
            else:
                print(f"Error deleting bucket {bucket_name}: {e}")
                return False

    def _cleanup_dynamodb_tables(
        self, environment: Optional[str], results: Dict[str, Any]
    ) -> None:
        """Clean up DynamoDB tables."""
        print("\n--- DynamoDB Tables ---")
        tables = self.list_project_dynamodb_tables(environment)
        if not tables:
            print("No DynamoDB tables found")
            return

        for table in tables:
            if self.delete_dynamodb_table(table):
                results["dynamodb_tables"]["deleted"].append(table)
            else:
                results["dynamodb_tables"]["failed"].append(table)

    def _cleanup_s3_buckets(
        self, environment: Optional[str], results: Dict[str, Any]
    ) -> None:
        """Clean up S3 buckets."""
        print("\n--- S3 Buckets ---")
        buckets = self.list_project_s3_buckets(environment)
        if not buckets:
            print("No S3 buckets found")
            return

        for bucket in buckets:
            # Empty the bucket but keep the bucket itself
            if self.empty_s3_bucket(bucket):
                results["s3_buckets"]["deleted"].append(bucket)
                print(f"Bucket {bucket} emptied successfully (bucket preserved)")
            else:
                results["s3_buckets"]["failed"].append(bucket)

    def _print_cleanup_summary(self, results: Dict[str, Any]) -> None:
        """Print cleanup summary and failed operations."""
        print("\n=== Cleanup Summary ===")
        print(f"DynamoDB tables deleted: {len(results['dynamodb_tables']['deleted'])}")
        print(f"S3 buckets emptied: {len(results['s3_buckets']['deleted'])}")

        if results["dynamodb_tables"]["failed"] or results["s3_buckets"]["failed"]:
            print("\nFailed operations:")
            for table in results["dynamodb_tables"]["failed"]:
                print(f"  - DynamoDB table deletion failed: {table}")
            for bucket in results["s3_buckets"]["failed"]:
                print(f"  - S3 bucket empty failed: {bucket}")

    def cleanup_all(self, environment: Optional[str] = None) -> Dict[str, Any]:
        """Clean up all project resources."""
        results: Dict[str, Any] = {
            "dynamodb_tables": {"deleted": [], "failed": []},
            "s3_buckets": {"deleted": [], "failed": []},
        }

        print(f"\n=== AWS Resource Cleanup {'(DRY RUN)' if self.dry_run else ''} ===")
        if environment:
            print(f"Environment filter: {environment}")

        self._cleanup_dynamodb_tables(environment, results)
        self._cleanup_s3_buckets(environment, results)
        self._print_cleanup_summary(results)

        return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clean up AWS resources for the image translation project"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )
    parser.add_argument(
        "--region", default="us-east-1", help="AWS region (default: us-east-1)"
    )
    parser.add_argument(
        "--environment", help="Environment filter (e.g., 'dev', 'staging', 'prod')"
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Skip confirmation prompt (use with caution)",
    )

    args = parser.parse_args()

    # Safety confirmation
    if not args.dry_run and not args.confirm:
        # Get counts of resources that would be affected
        cleanup_preview = AWSResourceCleanup(region=args.region, dry_run=True)
        tables = cleanup_preview.list_project_dynamodb_tables(args.environment)
        buckets = cleanup_preview.list_project_s3_buckets(args.environment)

        env_text = f" for environment '{args.environment}'" if args.environment else ""
        confirm = input(
            f"This will delete {len(tables)} DynamoDB tables and empty {len(buckets)} S3 buckets{env_text} in region {args.region}. "
            f"Are you sure? (type 'yes' to confirm): "
        )
        if confirm.lower() != "yes":
            print("Cleanup cancelled.")
            sys.exit(0)

    # Run cleanup
    cleanup = AWSResourceCleanup(region=args.region, dry_run=args.dry_run)
    results = cleanup.cleanup_all(environment=args.environment)

    # Exit with appropriate code
    failed_count = len(results["dynamodb_tables"]["failed"]) + len(
        results["s3_buckets"]["failed"]
    )
    sys.exit(1 if failed_count > 0 else 0)


if __name__ == "__main__":
    main()

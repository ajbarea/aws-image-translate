"""
Generates unique AWS resource names for developer environment isolation.
"""

import hashlib
import re
from typing import Any, Dict

from .progress_indicator import ProgressIndicator


class ResourceNameGenerator:
    """
    Generate unique resource names for developer isolation.
    Uses AWS account ID, region, and timestamp to ensure uniqueness.
    """

    def __init__(
        self,
        aws_account_id: str,
        aws_region: str,
        progress_indicator: ProgressIndicator,
    ):
        self.aws_account_id = aws_account_id
        self.aws_region = aws_region
        self.progress = progress_indicator
        self._unique_suffix = None

    def generate_unique_suffix(self) -> str:
        """
        Generate unique suffix for resources using AWS account ID and region.
        Returns a short, URL-safe suffix that ensures uniqueness per AWS account.
        This is stable across deployments for the same account/region.
        """
        if self._unique_suffix is None:
            # Create a deterministic identifier based on account and region only
            # This ensures the same suffix is used for the same AWS account/region
            # making it easier to find and destroy resources
            hash_input = f"{self.aws_account_id}-{self.aws_region}"
            hash_object = hashlib.sha256(hash_input.encode())

            # Take first 8 characters of hex digest for uniqueness while keeping names manageable
            self._unique_suffix = hash_object.hexdigest()[:8]

            self.progress.info(
                f"Generated unique resource suffix: {self._unique_suffix}"
            )

        return self._unique_suffix

    def get_s3_bucket_name(self, base_name: str) -> str:
        """
        Generate unique S3 bucket name that complies with AWS naming requirements.
        S3 bucket names must be globally unique and follow specific rules.
        """
        suffix = self.generate_unique_suffix()

        # S3 bucket naming rules:
        # - 3-63 characters long
        # - Only lowercase letters, numbers, and hyphens
        # - Must start and end with letter or number
        # - No consecutive hyphens
        # - No uppercase letters or underscores

        # Clean base name to comply with S3 rules
        clean_base = base_name.lower().replace("_", "-")
        clean_base = re.sub(r"[^a-z0-9-]", "", clean_base)
        clean_base = re.sub(r"-+", "-", clean_base)  # Remove consecutive hyphens
        clean_base = clean_base.strip("-")  # Remove leading/trailing hyphens

        # Construct bucket name with account ID for additional uniqueness
        bucket_name = f"{clean_base}-{self.aws_account_id[:8]}-{suffix}"

        # Ensure total length is within S3 limits (63 characters max)
        if len(bucket_name) > 63:
            # Truncate base name if needed
            max_base_length = 63 - len(f"-{self.aws_account_id[:8]}-{suffix}")
            clean_base = clean_base[:max_base_length]
            bucket_name = f"{clean_base}-{self.aws_account_id[:8]}-{suffix}"

        # Ensure it starts and ends with alphanumeric character
        if not bucket_name[0].isalnum():
            bucket_name = f"a{bucket_name[1:]}"
        if not bucket_name[-1].isalnum():
            bucket_name = f"{bucket_name[:-1]}a"

        return bucket_name

    def get_dynamodb_table_name(self, base_name: str) -> str:
        """
        Generate unique DynamoDB table name.
        DynamoDB table names have fewer restrictions than S3 buckets.
        """
        suffix = self.generate_unique_suffix()

        # DynamoDB naming rules are more flexible:
        # - 3-255 characters
        # - Letters, numbers, underscores, hyphens, and periods
        # - Case sensitive

        return f"{base_name}-{self.aws_account_id}-{suffix}"

    def get_terraform_backend_names(self) -> Dict[str, str]:
        """
        Generate unique names for Terraform backend resources (state bucket and lock table).
        These need to be unique per developer to avoid conflicts.
        """
        return {
            "state_bucket": self.get_s3_bucket_name("lenslate-terraform-state"),
            "lock_table": self.get_dynamodb_table_name("lenslate-terraform-lock"),
        }

    def update_terraform_vars(self, vars_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update Terraform variables dictionary with unique resource names.
        Removes any hardcoded resource names and replaces with generated ones.
        """
        updated_vars = vars_dict.copy()

        # Generate unique names for DynamoDB tables
        suffix = self.generate_unique_suffix()

        # Update DynamoDB table names to be unique per developer
        table_mappings = {
            "dynamodb_table_name": f"lenslate-state-{self.aws_account_id}-{suffix}",
            "translation_history_table": f"lenslate-translation-history-{self.aws_account_id}-{suffix}",
            "translations_table": f"lenslate-translations-{self.aws_account_id}-{suffix}",
        }

        for var_name, unique_name in table_mappings.items():
            updated_vars[var_name] = unique_name

        # Remove any hardcoded S3 bucket names - these should be generated by Terraform
        # using the random_id resource and locals
        hardcoded_s3_vars = ["s3_bucket_name", "frontend_bucket_name"]
        for var_name in hardcoded_s3_vars:
            if var_name in updated_vars:
                del updated_vars[var_name]
                self.progress.info(
                    f"Removed hardcoded {var_name} - will be auto-generated"
                )

        return updated_vars

    def validate_resource_names(self) -> bool:
        """
        Validate that generated resource names meet AWS requirements.
        """
        try:
            # Test S3 bucket name generation
            test_bucket = self.get_s3_bucket_name("test-bucket")
            if not self._validate_s3_bucket_name(test_bucket):
                self.progress.error(
                    f"Generated S3 bucket name is invalid: {test_bucket}"
                )
                return False

            # Test DynamoDB table name generation
            test_table = self.get_dynamodb_table_name("test-table")
            if not self._validate_dynamodb_table_name(test_table):
                self.progress.error(
                    f"Generated DynamoDB table name is invalid: {test_table}"
                )
                return False

            # Test backend resource names
            backend_names = self.get_terraform_backend_names()
            if not self._validate_s3_bucket_name(backend_names["state_bucket"]):
                self.progress.error(
                    f"Generated state bucket name is invalid: {backend_names['state_bucket']}"
                )
                return False

            if not self._validate_dynamodb_table_name(backend_names["lock_table"]):
                self.progress.error(
                    f"Generated lock table name is invalid: {backend_names['lock_table']}"
                )
                return False

            self.progress.success("Resource name generation validation passed")
            self.progress.info(f"State bucket: {backend_names['state_bucket']}")
            self.progress.info(f"Lock table: {backend_names['lock_table']}")
            return True

        except Exception as e:
            self.progress.error(f"Error validating resource names: {e}")
            return False

    def _validate_s3_bucket_name(self, bucket_name: str) -> bool:
        """Validate S3 bucket name against AWS rules"""
        if not (3 <= len(bucket_name) <= 63):
            return False
        if not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$", bucket_name):
            return False
        if "--" in bucket_name:
            return False
        return True

    def _validate_dynamodb_table_name(self, table_name: str) -> bool:
        """Validate DynamoDB table name against AWS rules"""
        if not (3 <= len(table_name) <= 255):
            return False
        if not re.match(r"^[a-zA-Z0-9_.-]+$", table_name):
            return False
        return True

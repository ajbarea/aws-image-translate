"""
Unit tests for the ResourceNameGenerator class.
"""

from unittest.mock import MagicMock

import pytest

from deployment_logic.progress_indicator import ProgressIndicator
from deployment_logic.resource_naming import ResourceNameGenerator


@pytest.fixture
def mock_progress_indicator():
    """Fixture to create a mock ProgressIndicator."""
    return MagicMock(spec=ProgressIndicator)


@pytest.fixture
def resource_generator(mock_progress_indicator):
    """Fixture to create a ResourceNameGenerator instance."""
    return ResourceNameGenerator(
        aws_account_id="123456789012",
        aws_region="us-east-1",
        progress_indicator=mock_progress_indicator,
    )


class TestResourceNameGenerator:
    """Tests for the ResourceNameGenerator class."""

    def test_generate_unique_suffix(self, resource_generator):
        """Test that the unique suffix is generated correctly and is deterministic."""
        suffix1 = resource_generator.generate_unique_suffix()
        suffix2 = resource_generator.generate_unique_suffix()

        assert isinstance(suffix1, str)
        assert len(suffix1) == 8
        assert suffix1 == suffix2  # Should be the same for the same instance

    def test_get_s3_bucket_name(self, resource_generator):
        """Test S3 bucket name generation."""
        base_name = "MyTestBucket"
        bucket_name = resource_generator.get_s3_bucket_name(base_name)

        assert bucket_name.startswith("mytestbucket-")
        assert resource_generator._validate_s3_bucket_name(bucket_name)

    def test_get_s3_bucket_name_with_invalid_chars(self, resource_generator):
        """Test that invalid characters are stripped from S3 bucket names."""
        base_name = "My_Invalid!Bucket@Name"
        bucket_name = resource_generator.get_s3_bucket_name(base_name)
        assert "!" not in bucket_name
        assert "@" not in bucket_name
        assert "_" not in bucket_name
        assert bucket_name.startswith("my-invalidbucketname-")

    def test_get_s3_bucket_name_length_limit(self, resource_generator):
        """Test that S3 bucket names are truncated to 63 characters."""
        long_base_name = "a" * 70
        bucket_name = resource_generator.get_s3_bucket_name(long_base_name)
        assert len(bucket_name) <= 63

    def test_get_dynamodb_table_name(self, resource_generator):
        """Test DynamoDB table name generation."""
        base_name = "MyTestTable"
        table_name = resource_generator.get_dynamodb_table_name(base_name)
        assert table_name.startswith(f"{base_name}-")
        assert resource_generator._validate_dynamodb_table_name(table_name)

    def test_get_terraform_backend_names(self, resource_generator):
        """Test generation of Terraform backend resource names."""
        backend_names = resource_generator.get_terraform_backend_names()
        assert "state_bucket" in backend_names
        assert "lock_table" in backend_names
        assert resource_generator._validate_s3_bucket_name(
            backend_names["state_bucket"]
        )
        assert resource_generator._validate_dynamodb_table_name(
            backend_names["lock_table"]
        )

    def test_update_terraform_vars(self, resource_generator):
        """Test updating Terraform variables with unique names."""
        initial_vars = {
            "region": "us-east-1",
            "s3_bucket_name": "hardcoded-bucket",
            "frontend_bucket_name": "hardcoded-frontend-bucket",
        }
        updated_vars = resource_generator.update_terraform_vars(initial_vars)

        assert "s3_bucket_name" not in updated_vars
        assert "frontend_bucket_name" not in updated_vars
        assert "dynamodb_table_name" in updated_vars
        assert "translation_history_table" in updated_vars
        assert "translations_table" in updated_vars
        assert updated_vars["region"] == "us-east-1"

    def test_validate_resource_names(self, resource_generator):
        """Test the validation of all generated resource names."""
        assert resource_generator.validate_resource_names() is True

    def test_validate_s3_bucket_name_private(self, resource_generator):
        """Test the private S3 bucket name validation method."""
        assert resource_generator._validate_s3_bucket_name("valid-bucket-name") is True
        assert resource_generator._validate_s3_bucket_name("a" * 63) is True
        assert resource_generator._validate_s3_bucket_name("a" * 2) is False
        assert resource_generator._validate_s3_bucket_name("a" * 64) is False
        assert (
            resource_generator._validate_s3_bucket_name("Invalid-Bucket-Name") is False
        )
        assert (
            resource_generator._validate_s3_bucket_name("invalid_bucket_name") is False
        )
        assert resource_generator._validate_s3_bucket_name("bucket--name") is False
        assert resource_generator._validate_s3_bucket_name("-bucket-name") is False
        assert resource_generator._validate_s3_bucket_name("bucket-name-") is False

    def test_validate_dynamodb_table_name_private(self, resource_generator):
        """Test the private DynamoDB table name validation method."""
        assert (
            resource_generator._validate_dynamodb_table_name("Valid.Table-Name_1")
            is True
        )
        assert resource_generator._validate_dynamodb_table_name("a" * 255) is True
        assert resource_generator._validate_dynamodb_table_name("a" * 2) is False
        assert resource_generator._validate_dynamodb_table_name("a" * 256) is False
        assert (
            resource_generator._validate_dynamodb_table_name("invalid-table-name!")
            is False
        )

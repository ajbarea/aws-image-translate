"""
Resource tracker for deployment - tracks all created AWS resources for easy cleanup.
"""

import datetime
import json
from pathlib import Path
from typing import Dict, List


class ResourceTracker:
    """
    Tracks all AWS resources created during deployment.
    Creates a manifest file that can be used for cleanup operations.
    """

    def __init__(self, root_dir: Path, aws_account_id: str, aws_region: str):
        self.root_dir = root_dir
        self.aws_account_id = aws_account_id
        self.aws_region = aws_region
        self.deployment_dir = root_dir / "your_deployment"

        # Ensure deployment directory exists
        self.deployment_dir.mkdir(exist_ok=True)

        self.manifest_file = self.deployment_dir / "deployed_resources.json"
        self.resources = {
            "deployment_info": {
                "aws_account_id": aws_account_id,
                "aws_region": aws_region,
                "deployment_timestamp": datetime.datetime.now().isoformat(),
                "unique_suffix": None,  # Will be set when available
            },
            "s3_buckets": [],
            "dynamodb_tables": [],
            "lambda_functions": [],
            "cloudformation_stacks": [],
            "cognito_resources": [],
            "api_gateway": [],
            "cloudfront_distributions": [],
            "iam_roles": [],
            "other_resources": [],
        }

    def set_unique_suffix(self, suffix: str):
        """Set the unique suffix used for resource naming"""
        self.resources["deployment_info"]["unique_suffix"] = suffix

    def add_s3_bucket(self, bucket_name: str, purpose: str = ""):
        """Track an S3 bucket"""
        self.resources["s3_buckets"].append(
            {
                "name": bucket_name,
                "purpose": purpose,
                "created_at": datetime.datetime.now().isoformat(),
            }
        )

    def add_dynamodb_table(self, table_name: str, purpose: str = ""):
        """Track a DynamoDB table"""
        self.resources["dynamodb_tables"].append(
            {
                "name": table_name,
                "purpose": purpose,
                "created_at": datetime.datetime.now().isoformat(),
            }
        )

    def add_lambda_function(self, function_name: str, purpose: str = ""):
        """Track a Lambda function"""
        self.resources["lambda_functions"].append(
            {
                "name": function_name,
                "purpose": purpose,
                "created_at": datetime.datetime.now().isoformat(),
            }
        )

    def add_cloudformation_stack(self, stack_name: str, purpose: str = ""):
        """Track a CloudFormation stack"""
        self.resources["cloudformation_stacks"].append(
            {
                "name": stack_name,
                "purpose": purpose,
                "created_at": datetime.datetime.now().isoformat(),
            }
        )

    def add_cognito_resource(
        self, resource_id: str, resource_type: str, purpose: str = ""
    ):
        """Track Cognito resources (user pools, identity pools, etc.)"""
        self.resources["cognito_resources"].append(
            {
                "id": resource_id,
                "type": resource_type,
                "purpose": purpose,
                "created_at": datetime.datetime.now().isoformat(),
            }
        )

    def add_api_gateway(self, api_id: str, api_name: str, purpose: str = ""):
        """Track API Gateway resources"""
        self.resources["api_gateway"].append(
            {
                "id": api_id,
                "name": api_name,
                "purpose": purpose,
                "created_at": datetime.datetime.now().isoformat(),
            }
        )

    def add_cloudfront_distribution(
        self, distribution_id: str, domain: str = "", purpose: str = ""
    ):
        """Track CloudFront distributions"""
        self.resources["cloudfront_distributions"].append(
            {
                "id": distribution_id,
                "domain": domain,
                "purpose": purpose,
                "created_at": datetime.datetime.now().isoformat(),
            }
        )

    def add_iam_role(self, role_name: str, purpose: str = ""):
        """Track IAM roles"""
        self.resources["iam_roles"].append(
            {
                "name": role_name,
                "purpose": purpose,
                "created_at": datetime.datetime.now().isoformat(),
            }
        )

    def add_other_resource(
        self,
        resource_type: str,
        resource_id: str,
        resource_name: str = "",
        purpose: str = "",
    ):
        """Track any other AWS resource"""
        self.resources["other_resources"].append(
            {
                "type": resource_type,
                "id": resource_id,
                "name": resource_name,
                "purpose": purpose,
                "created_at": datetime.datetime.now().isoformat(),
            }
        )

    def track_terraform_backend_resources(self, state_bucket: str, lock_table: str):
        """Track Terraform backend resources"""
        self.add_s3_bucket(state_bucket, "Terraform state storage")
        self.add_dynamodb_table(lock_table, "Terraform state locking")

    def track_predicted_resources(self, resource_name_generator):
        """
        Track resources that will be created based on the resource naming patterns.
        This helps create a complete manifest even before Terraform runs.
        """
        suffix = resource_name_generator.generate_unique_suffix()
        self.set_unique_suffix(suffix)

        # Track backend resources
        backend_names = resource_name_generator.get_terraform_backend_names()
        self.track_terraform_backend_resources(
            backend_names["state_bucket"], backend_names["lock_table"]
        )

        # Track predicted DynamoDB tables from resource naming
        predicted_tables = [
            f"lenslate-state-{self.aws_account_id}-{suffix}",
            f"lenslate-translation-history-{self.aws_account_id}-{suffix}",
            f"lenslate-translations-{self.aws_account_id}-{suffix}",
        ]

        for table_name in predicted_tables:
            if "state" in table_name:
                purpose = "Application state storage"
            elif "history" in table_name:
                purpose = "Translation history storage"
            elif "translations" in table_name:
                purpose = "Translations data storage"
            else:
                purpose = "Application data"

            self.add_dynamodb_table(table_name, purpose)

        # Track predicted S3 buckets (these will have random suffixes from Terraform)
        self.add_other_resource(
            "s3_bucket_pattern",
            f"lenslate-*-{self.aws_account_id}-*",
            "Frontend assets bucket",
            "Static website hosting and assets",
        )

        self.add_other_resource(
            "s3_bucket_pattern",
            f"lenslate-images-*-{self.aws_account_id}-*",
            "Images storage bucket",
            "User uploaded images and processed images",
        )

    def save_manifest(self):
        """Save the resource manifest to file"""
        try:
            with open(self.manifest_file, "w", encoding="utf-8") as f:
                json.dump(self.resources, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving resource manifest: {e}")
            return False

    def load_manifest(self) -> bool:
        """Load existing resource manifest"""
        try:
            if self.manifest_file.exists():
                with open(self.manifest_file, "r", encoding="utf-8") as f:
                    self.resources = json.load(f)
                return True
            return False
        except Exception as e:
            print(f"Error loading resource manifest: {e}")
            return False

    def get_all_resource_names(self) -> Dict[str, List[str]]:
        """Get all resource names organized by type"""
        result = {}

        # S3 buckets
        result["s3_buckets"] = [
            bucket["name"] for bucket in self.resources["s3_buckets"]
        ]

        # DynamoDB tables
        result["dynamodb_tables"] = [
            table["name"] for table in self.resources["dynamodb_tables"]
        ]

        # Lambda functions
        result["lambda_functions"] = [
            func["name"] for func in self.resources["lambda_functions"]
        ]

        # CloudFormation stacks
        result["cloudformation_stacks"] = [
            stack["name"] for stack in self.resources["cloudformation_stacks"]
        ]

        # Other resources
        result["cognito_resources"] = [
            res["id"] for res in self.resources["cognito_resources"]
        ]
        result["api_gateway"] = [api["id"] for api in self.resources["api_gateway"]]
        result["cloudfront_distributions"] = [
            dist["id"] for dist in self.resources["cloudfront_distributions"]
        ]
        result["iam_roles"] = [role["name"] for role in self.resources["iam_roles"]]

        return result

    def generate_cleanup_script(self) -> str:
        """Generate a cleanup script based on tracked resources"""
        script_lines = [
            "#!/usr/bin/env python3",
            '"""',
            "Generated cleanup script for deployed resources",
            f"Generated on: {datetime.datetime.now().isoformat()}",
            f"AWS Account: {self.aws_account_id}",
            f"AWS Region: {self.aws_region}",
            '"""',
            "",
            "import boto3",
            "from botocore.exceptions import ClientError",
            "",
            "def cleanup_resources():",
            '    """Clean up all tracked resources"""',
            "    print('🧹 Cleaning up tracked resources...')",
            "    ",
        ]

        # Add S3 bucket cleanup
        if self.resources["s3_buckets"]:
            script_lines.extend(
                [
                    "    # S3 Buckets",
                    "    s3_client = boto3.client('s3')",
                    "    buckets_to_delete = [",
                ]
            )
            for bucket in self.resources["s3_buckets"]:
                script_lines.append(
                    f'        "{bucket["name"]}",  # {bucket["purpose"]}'
                )
            script_lines.extend(
                [
                    "    ]",
                    "    ",
                    "    for bucket_name in buckets_to_delete:",
                    "        try:",
                    "            print(f'Deleting S3 bucket: {bucket_name}')",
                    "            # Empty bucket first",
                    "            paginator = s3_client.get_paginator('list_object_versions')",
                    "            pages = paginator.paginate(Bucket=bucket_name)",
                    "            for page in pages:",
                    "                if 'Versions' in page:",
                    "                    objects = [{'Key': obj['Key'], 'VersionId': obj['VersionId']} for obj in page['Versions']]",
                    "                    if objects:",
                    "                        s3_client.delete_objects(Bucket=bucket_name, Delete={'Objects': objects})",
                    "                if 'DeleteMarkers' in page:",
                    "                    objects = [{'Key': obj['Key'], 'VersionId': obj['VersionId']} for obj in page['DeleteMarkers']]",
                    "                    if objects:",
                    "                        s3_client.delete_objects(Bucket=bucket_name, Delete={'Objects': objects})",
                    "            s3_client.delete_bucket(Bucket=bucket_name)",
                    "            print(f'✅ Deleted S3 bucket: {bucket_name}')",
                    "        except ClientError as e:",
                    "            if e.response['Error']['Code'] != 'NoSuchBucket':",
                    "                print(f'❌ Error deleting bucket {bucket_name}: {e}')",
                    "    ",
                ]
            )

        # Add DynamoDB table cleanup
        if self.resources["dynamodb_tables"]:
            script_lines.extend(
                [
                    "    # DynamoDB Tables",
                    "    dynamodb_client = boto3.client('dynamodb')",
                    "    tables_to_delete = [",
                ]
            )
            for table in self.resources["dynamodb_tables"]:
                script_lines.append(f'        "{table["name"]}",  # {table["purpose"]}')
            script_lines.extend(
                [
                    "    ]",
                    "    ",
                    "    for table_name in tables_to_delete:",
                    "        try:",
                    "            print(f'Deleting DynamoDB table: {table_name}')",
                    "            dynamodb_client.delete_table(TableName=table_name)",
                    "            print(f'✅ Deleted DynamoDB table: {table_name}')",
                    "        except ClientError as e:",
                    "            if e.response['Error']['Code'] != 'ResourceNotFoundException':",
                    "                print(f'❌ Error deleting table {table_name}: {e}')",
                    "    ",
                ]
            )

        # Add Lambda function cleanup
        if self.resources["lambda_functions"]:
            script_lines.extend(
                [
                    "    # Lambda Functions",
                    "    lambda_client = boto3.client('lambda')",
                    "    functions_to_delete = [",
                ]
            )
            for func in self.resources["lambda_functions"]:
                script_lines.append(f'        "{func["name"]}",  # {func["purpose"]}')
            script_lines.extend(
                [
                    "    ]",
                    "    ",
                    "    for function_name in functions_to_delete:",
                    "        try:",
                    "            print(f'Deleting Lambda function: {function_name}')",
                    "            lambda_client.delete_function(FunctionName=function_name)",
                    "            print(f'✅ Deleted Lambda function: {function_name}')",
                    "        except ClientError as e:",
                    "            if e.response['Error']['Code'] != 'ResourceNotFoundException':",
                    "                print(f'❌ Error deleting function {function_name}: {e}')",
                    "    ",
                ]
            )

        script_lines.extend(
            [
                "",
                "if __name__ == '__main__':",
                "    cleanup_resources()",
                "    print('🎉 Cleanup completed!')",
            ]
        )

        return "\n".join(script_lines)

    def create_human_readable_summary(self) -> str:
        """Create a human-readable summary of deployed resources"""
        lines = [
            "# Deployed Resources Summary",
            "",
            f"**Deployment Date:** {self.resources['deployment_info']['deployment_timestamp']}",
            f"**AWS Account:** {self.aws_account_id}",
            f"**AWS Region:** {self.aws_region}",
            f"**Unique Suffix:** {self.resources['deployment_info'].get('unique_suffix', 'N/A')}",
            "",
            "## Resources Created",
            "",
        ]

        # S3 Buckets
        if self.resources["s3_buckets"]:
            lines.extend(["### S3 Buckets", ""])
            for bucket in self.resources["s3_buckets"]:
                lines.append(f"- **{bucket['name']}** - {bucket['purpose']}")
            lines.append("")

        # DynamoDB Tables
        if self.resources["dynamodb_tables"]:
            lines.extend(["### DynamoDB Tables", ""])
            for table in self.resources["dynamodb_tables"]:
                lines.append(f"- **{table['name']}** - {table['purpose']}")
            lines.append("")

        # Lambda Functions
        if self.resources["lambda_functions"]:
            lines.extend(["### Lambda Functions", ""])
            for func in self.resources["lambda_functions"]:
                lines.append(f"- **{func['name']}** - {func['purpose']}")
            lines.append("")

        # Other resources
        for resource_type in [
            "cognito_resources",
            "api_gateway",
            "cloudfront_distributions",
            "iam_roles",
        ]:
            if self.resources[resource_type]:
                title = resource_type.replace("_", " ").title()
                lines.extend([f"### {title}", ""])
                for resource in self.resources[resource_type]:
                    if "name" in resource:
                        lines.append(
                            f"- **{resource['name']}** - {resource.get('purpose', 'N/A')}"
                        )
                    elif "id" in resource:
                        lines.append(
                            f"- **{resource['id']}** - {resource.get('purpose', 'N/A')}"
                        )
                lines.append("")

        lines.extend(
            [
                "## Cleanup Instructions",
                "",
                "To destroy these resources:",
                "",
                "1. **Automated cleanup:** Run `python cleanup_resources.py` (generated script)",
                "2. **Manual cleanup:** Use the AWS Console to delete resources listed above",
                "3. **Terraform destroy:** Run `python deploy.py --destroy` (if Terraform state is intact)",
                "",
                "⚠️ **Important:** Always verify resources are deleted to avoid ongoing charges!",
            ]
        )

        return "\n".join(lines)

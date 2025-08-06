#!/usr/bin/env python3
"""
Complete deployment cleanup script - removes all deployment artifacts for a fresh start
"""
import glob
import json
import os
import shutil
import subprocess

import boto3
from botocore.exceptions import ClientError


def clean_terraform_files():
    """Remove .terraform directories, tfplan files, tfstate files, and .terraform.lock.hcl files"""
    print("🧹 Cleaning Terraform state files...")

    deleted_count = 0

    # Remove .terraform directories
    terraform_dirs = glob.glob("**/.terraform", recursive=True)
    for terraform_dir in terraform_dirs:
        try:
            if os.path.isdir(terraform_dir):
                shutil.rmtree(terraform_dir)
                print(f"   ✅ Deleted {terraform_dir}")
                deleted_count += 1
        except Exception as e:
            print(f"   ❌ Error deleting {terraform_dir}: {e}")

    # Remove tfplan files
    tfplan_files = glob.glob("**/*.tfplan", recursive=True)
    for tfplan_file in tfplan_files:
        try:
            if os.path.isfile(tfplan_file):
                os.remove(tfplan_file)
                print(f"   ✅ Deleted {tfplan_file}")
                deleted_count += 1
        except Exception as e:
            print(f"   ❌ Error deleting {tfplan_file}: {e}")

    # Remove tfplan files without extension
    tfplan_files_no_ext = glob.glob("**/tfplan", recursive=True)
    for tfplan_file in tfplan_files_no_ext:
        try:
            if os.path.isfile(tfplan_file):
                os.remove(tfplan_file)
                print(f"   ✅ Deleted {tfplan_file}")
                deleted_count += 1
        except Exception as e:
            print(f"   ❌ Error deleting {tfplan_file}: {e}")

    # Also specifically target the known tfplan files
    specific_tfplan_files = [
        "terraform/app-stack/tfplan",
        "terraform/data-stack/tfplan",
    ]
    for tfplan_file in specific_tfplan_files:
        try:
            if os.path.isfile(tfplan_file):
                os.remove(tfplan_file)
                print(f"   ✅ Deleted {tfplan_file}")
                deleted_count += 1
        except Exception as e:
            if "No such file or directory" not in str(e):
                print(f"   ❌ Error deleting {tfplan_file}: {e}")

    # Remove terraform.tfstate files
    tfstate_files = glob.glob("**/terraform.tfstate*", recursive=True)
    for tfstate_file in tfstate_files:
        try:
            if os.path.isfile(tfstate_file):
                os.remove(tfstate_file)
                print(f"   ✅ Deleted {tfstate_file}")
                deleted_count += 1
        except Exception as e:
            print(f"   ❌ Error deleting {tfstate_file}: {e}")

    # Remove .terraform.lock.hcl files
    lock_files = glob.glob("**/.terraform.lock.hcl", recursive=True)
    for lock_file in lock_files:
        try:
            if os.path.isfile(lock_file):
                os.remove(lock_file)
                print(f"   ✅ Deleted {lock_file}")
                deleted_count += 1
        except Exception as e:
            print(f"   ❌ Error deleting {lock_file}: {e}")

    # Also specifically target the known lock files
    specific_lock_files = [
        "terraform/app-stack/.terraform.lock.hcl",
        "terraform/data-stack/.terraform.lock.hcl",
    ]
    for lock_file in specific_lock_files:
        try:
            if os.path.isfile(lock_file):
                os.remove(lock_file)
                print(f"   ✅ Deleted {lock_file}")
                deleted_count += 1
        except Exception as e:
            if "No such file or directory" not in str(e):
                print(f"   ❌ Error deleting {lock_file}: {e}")

    if deleted_count == 0:
        print("   📂 No Terraform state files found")
    else:
        print(f"   ✅ Cleaned {deleted_count} Terraform state files")

    return True


def clean_zip_files():
    """Remove all ZIP files from terraform directories"""
    print("🧹 Cleaning ZIP files...")

    deleted_count = 0

    # Look for zip files in terraform directories and build folders
    zip_patterns = ["terraform/**/*.zip", "lambda_functions/build/*.zip", "*.zip"]

    for pattern in zip_patterns:
        zip_files = glob.glob(pattern, recursive=True)
        for zip_file in zip_files:
            try:
                if os.path.isfile(zip_file):
                    os.remove(zip_file)
                    print(f"   ✅ Deleted {zip_file}")
                    deleted_count += 1
            except Exception as e:
                print(f"   ❌ Error deleting {zip_file}: {e}")

    if deleted_count == 0:
        print("   📂 No ZIP files found")
    else:
        print(f"   ✅ Cleaned {deleted_count} ZIP files")

    return True


def get_all_s3_buckets():
    """Get all S3 buckets that belong to this project"""
    s3_client = boto3.client("s3")
    project_buckets = []

    try:
        response = s3_client.list_buckets()
        for bucket in response["Buckets"]:
            bucket_name = bucket["Name"]
            # Check if this bucket belongs to lenslate project
            if "lenslate" in bucket_name.lower():
                project_buckets.append(bucket_name)
    except ClientError as e:
        print(f"❌ Error listing buckets: {e}")

    return project_buckets


def empty_and_delete_bucket(bucket_name):
    """Empty and delete a single S3 bucket"""
    s3_client = boto3.client("s3")

    try:
        print(f"   🧹 Emptying bucket: {bucket_name}")

        # Delete all objects (including versioned objects)
        paginator = s3_client.get_paginator("list_object_versions")
        pages = paginator.paginate(Bucket=bucket_name)

        objects_to_delete = []
        total_count = 0

        for page in pages:
            # Delete regular objects
            if "Versions" in page:
                for obj in page["Versions"]:
                    objects_to_delete.append(
                        {"Key": obj["Key"], "VersionId": obj["VersionId"]}
                    )
                    total_count += 1

            # Delete delete markers
            if "DeleteMarkers" in page:
                for obj in page["DeleteMarkers"]:
                    objects_to_delete.append(
                        {"Key": obj["Key"], "VersionId": obj["VersionId"]}
                    )
                    total_count += 1

            # Delete in batches of 1000 (AWS limit)
            if len(objects_to_delete) >= 1000:
                s3_client.delete_objects(
                    Bucket=bucket_name, Delete={"Objects": objects_to_delete}
                )
                print(f"      Deleted {len(objects_to_delete)} objects...")
                objects_to_delete = []

        # Delete remaining objects
        if objects_to_delete:
            s3_client.delete_objects(
                Bucket=bucket_name, Delete={"Objects": objects_to_delete}
            )
            print(f"      Deleted {len(objects_to_delete)} objects...")

        print(f"   📊 Total objects deleted from {bucket_name}: {total_count}")

        # Now delete the bucket itself
        print(f"   🗑️  Deleting bucket: {bucket_name}")
        s3_client.delete_bucket(Bucket=bucket_name)
        print(f"   ✅ Successfully deleted bucket: {bucket_name}")

        return True

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code == "NoSuchBucket":
            print(f"   ⚠️  Bucket {bucket_name} does not exist")
            return True
        else:
            print(f"   ❌ Error with bucket {bucket_name}: {e}")
            return False
    except Exception as e:
        print(f"   ❌ Unexpected error with bucket {bucket_name}: {e}")
        return False


def clean_all_s3_buckets():
    """Find and delete all project S3 buckets"""
    print("🧹 Finding and cleaning all project S3 buckets...")

    buckets = get_all_s3_buckets()

    if not buckets:
        print("   📂 No project buckets found")
        return True

    print(f"   📋 Found {len(buckets)} project buckets:")
    for bucket in buckets:
        print(f"      - {bucket}")

    print()
    success_count = 0

    for bucket_name in buckets:
        if empty_and_delete_bucket(bucket_name):
            success_count += 1

    if success_count == len(buckets):
        print(f"✅ Successfully cleaned {success_count} S3 buckets")
        return True
    else:
        print(f"⚠️ Cleaned {success_count}/{len(buckets)} S3 buckets with some errors")
        return False


def clean_all_dynamodb_tables():
    """Find and delete all project DynamoDB tables"""
    print("🧹 Finding and cleaning all project DynamoDB tables...")

    dynamodb = boto3.client("dynamodb")
    project_tables = []

    try:
        # List all tables and filter for project tables
        paginator = dynamodb.get_paginator("list_tables")
        pages = paginator.paginate()

        for page in pages:
            for table_name in page["TableNames"]:
                if "lenslate" in table_name.lower():
                    project_tables.append(table_name)

        if not project_tables:
            print("   📂 No project DynamoDB tables found")
            return True

        print(f"   📋 Found {len(project_tables)} project tables:")
        for table in project_tables:
            print(f"      - {table}")

        print()
        success_count = 0

        for table_name in project_tables:
            try:
                print(f"   🗑️  Deleting table: {table_name}")
                dynamodb.delete_table(TableName=table_name)
                print(f"   ✅ Successfully deleted table: {table_name}")
                success_count += 1
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                if error_code == "ResourceNotFoundException":
                    print(f"   ⚠️  Table {table_name} does not exist")
                    success_count += 1
                else:
                    print(f"   ❌ Error deleting table {table_name}: {e}")
            except Exception as e:
                print(f"   ❌ Unexpected error deleting table {table_name}: {e}")

        if success_count == len(project_tables):
            print(f"✅ Successfully cleaned {success_count} DynamoDB tables")
            return True
        else:
            print(
                f"⚠️ Cleaned {success_count}/{len(project_tables)} DynamoDB tables with some errors"
            )
            return False

    except ClientError as e:
        print(f"❌ Error listing DynamoDB tables: {e}")
        return False


def clean_lambda_functions():
    """Clean Lambda functions associated with the project"""
    print("🧹 Finding and cleaning Lambda functions...")

    lambda_client = boto3.client("lambda")
    project_functions = []

    try:
        # List all functions and filter for project functions
        paginator = lambda_client.get_paginator("list_functions")
        pages = paginator.paginate()

        for page in pages:
            for function in page["Functions"]:
                function_name = function["FunctionName"]
                if "lenslate" in function_name.lower():
                    project_functions.append(function_name)

        if not project_functions:
            print("   📂 No project Lambda functions found")
            return True

        print(f"   📋 Found {len(project_functions)} project functions:")
        for func in project_functions:
            print(f"      - {func}")

        print()
        success_count = 0

        for function_name in project_functions:
            try:
                print(f"   🗑️  Deleting function: {function_name}")
                lambda_client.delete_function(FunctionName=function_name)
                print(f"   ✅ Successfully deleted function: {function_name}")
                success_count += 1
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                if error_code == "ResourceNotFoundException":
                    print(f"   ⚠️  Function {function_name} does not exist")
                    success_count += 1
                else:
                    print(f"   ❌ Error deleting function {function_name}: {e}")
            except Exception as e:
                print(f"   ❌ Unexpected error deleting function {function_name}: {e}")

        if success_count == len(project_functions):
            print(f"✅ Successfully cleaned {success_count} Lambda functions")
            return True
        else:
            print(
                f"⚠️ Cleaned {success_count}/{len(project_functions)} Lambda functions with some errors"
            )
            return False

    except ClientError as e:
        print(f"❌ Error listing Lambda functions: {e}")
        return False


def clean_cloudformation_stacks():
    """Clean CloudFormation stacks associated with the project"""
    print("🧹 Finding and cleaning CloudFormation stacks...")

    cf_client = boto3.client("cloudformation")
    project_stacks = []

    try:
        # List all stacks and filter for project stacks
        paginator = cf_client.get_paginator("list_stacks")
        pages = paginator.paginate(
            StackStatusFilter=[
                "CREATE_COMPLETE",
                "UPDATE_COMPLETE",
                "CREATE_FAILED",
                "UPDATE_FAILED",
                "ROLLBACK_COMPLETE",
                "ROLLBACK_FAILED",
            ]
        )

        for page in pages:
            for stack in page["StackSummaries"]:
                stack_name = stack["StackName"]
                if "lenslate" in stack_name.lower():
                    project_stacks.append(stack_name)

        if not project_stacks:
            print("   📂 No project CloudFormation stacks found")
            return True

        print(f"   📋 Found {len(project_stacks)} project stacks:")
        for stack in project_stacks:
            print(f"      - {stack}")

        print()
        success_count = 0

        for stack_name in project_stacks:
            try:
                print(f"   🗑️  Deleting stack: {stack_name}")
                cf_client.delete_stack(StackName=stack_name)
                print(f"   ✅ Successfully deleted stack: {stack_name}")
                success_count += 1
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                if error_code in ["ValidationError", "ResourceNotFound"]:
                    print(f"   ⚠️  Stack {stack_name} does not exist")
                    success_count += 1
                else:
                    print(f"   ❌ Error deleting stack {stack_name}: {e}")
            except Exception as e:
                print(f"   ❌ Unexpected error deleting stack {stack_name}: {e}")

        if success_count == len(project_stacks):
            print(f"✅ Successfully cleaned {success_count} CloudFormation stacks")
            return True
        else:
            print(
                f"⚠️ Cleaned {success_count}/{len(project_stacks)} CloudFormation stacks with some errors"
            )
            return False

    except ClientError as e:
        print(f"❌ Error listing CloudFormation stacks: {e}")
        return False


def execute_terraform_stack_destruction():
    """Destroy Terraform stacks using multiple strategies"""
    print("🧹 Performing Terraform destroy...")

    # Check if terraform is available
    try:
        result = subprocess.run(
            ["terraform", "version"], capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            print("   ⚠️  Terraform not available - skipping terraform destroy")
            return True
    except Exception:
        print("   ⚠️  Terraform not available - skipping terraform destroy")
        return True

    # Define stack directories
    stacks = [
        {"name": "app-stack", "path": "terraform/app-stack"},
        {"name": "data-stack", "path": "terraform/data-stack"},
    ]

    success_count = 0

    for stack in stacks:
        if _destroy_single_terraform_stack(stack["name"], stack["path"]):
            success_count += 1

    if success_count == len(stacks):
        print("✅ Successfully destroyed all Terraform stacks")
        return True
    else:
        print(f"⚠️ Destroyed {success_count}/{len(stacks)} Terraform stacks")
        return success_count > 0


def _destroy_single_terraform_stack(stack_name, stack_path):
    """Destroy a single Terraform stack with multiple fallback strategies"""
    import os

    if not os.path.exists(stack_path):
        print(f"   ⚠️  Stack directory {stack_path} not found")
        return True

    print(f"   🗑️  Destroying {stack_name}...")

    try:
        # Strategy 1: Normal terraform destroy
        result = subprocess.run(
            ["terraform", "destroy", "-auto-approve"],
            cwd=stack_path,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
        )

        if result.returncode == 0:
            print(f"   ✅ Successfully destroyed {stack_name}")
            return True
        else:
            # Strategy 2: Refresh state and retry
            refresh_result = subprocess.run(
                ["terraform", "refresh"],
                cwd=stack_path,
                capture_output=True,
                text=True,
                timeout=300,
            )

            if refresh_result.returncode == 0:
                retry_result = subprocess.run(
                    ["terraform", "destroy", "-auto-approve"],
                    cwd=stack_path,
                    capture_output=True,
                    text=True,
                    timeout=600,
                )

                if retry_result.returncode == 0:
                    print(f"   ✅ Successfully destroyed {stack_name} after refresh")
                    return True

            print(f"   ❌ Terraform destroy failed for {stack_name}")
            if result.stderr:
                print(f"        Error: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        print(f"   ❌ Terraform destroy timed out for {stack_name}")
        return False
    except Exception as e:
        print(f"   ❌ Error destroying {stack_name}: {e}")
        return False


def load_tracked_resources():
    """Load tracked resources from deployment files"""
    tracked_resources = {
        "s3_buckets": [],
        "dynamodb_tables": [],
        "lambda_functions": [],
        "cloudformation_stacks": [],
    }

    # Try to load from deployed_resources.json
    try:
        if os.path.exists("deployed_resources.json"):
            with open("deployed_resources.json", "r") as f:
                data = json.load(f)

            # Extract resource names from the JSON structure
            for resource_type, resources in data.get("resources", {}).items():
                if resource_type == "s3_bucket" and isinstance(resources, list):
                    tracked_resources["s3_buckets"].extend(
                        [r.get("name") for r in resources if r.get("name")]
                    )
                elif resource_type == "dynamodb_table" and isinstance(resources, list):
                    tracked_resources["dynamodb_tables"].extend(
                        [r.get("name") for r in resources if r.get("name")]
                    )
                elif resource_type == "lambda_function" and isinstance(resources, list):
                    tracked_resources["lambda_functions"].extend(
                        [r.get("name") for r in resources if r.get("name")]
                    )

            print(
                f"   📋 Loaded {sum(len(v) for v in tracked_resources.values())} tracked resources"
            )

    except Exception as e:
        print(f"   ⚠️  Could not load tracked resources: {e}")

    return tracked_resources


def clean_tracked_resources():
    """Clean resources from tracking files first, then do cleanup"""
    print("🧹 Cleaning tracked resources...")

    tracked = load_tracked_resources()
    success = True

    # Clean tracked S3 buckets first
    if tracked["s3_buckets"]:
        print(f"   📋 Cleaning {len(tracked['s3_buckets'])} tracked S3 buckets...")
        for bucket_name in tracked["s3_buckets"]:
            if not empty_and_delete_bucket(bucket_name):
                success = False

    # Clean tracked DynamoDB tables
    if tracked["dynamodb_tables"]:
        print(
            f"   📋 Cleaning {len(tracked['dynamodb_tables'])} tracked DynamoDB tables..."
        )
        dynamodb = boto3.client("dynamodb")
        for table_name in tracked["dynamodb_tables"]:
            try:
                dynamodb.delete_table(TableName=table_name)
                print(f"   ✅ Deleted tracked table: {table_name}")
            except ClientError as e:
                if (
                    e.response.get("Error", {}).get("Code")
                    != "ResourceNotFoundException"
                ):
                    print(f"   ❌ Error deleting tracked table {table_name}: {e}")
                    success = False
                else:
                    print(f"   ⚠️  Tracked table {table_name} already deleted")

    # Clean tracked Lambda functions
    if tracked["lambda_functions"]:
        print(
            f"   📋 Cleaning {len(tracked['lambda_functions'])} tracked Lambda functions..."
        )
        lambda_client = boto3.client("lambda")
        for function_name in tracked["lambda_functions"]:
            try:
                lambda_client.delete_function(FunctionName=function_name)
                print(f"   ✅ Deleted tracked function: {function_name}")
            except ClientError as e:
                if (
                    e.response.get("Error", {}).get("Code")
                    != "ResourceNotFoundException"
                ):
                    print(f"   ❌ Error deleting tracked function {function_name}: {e}")
                    success = False
                else:
                    print(f"   ⚠️  Tracked function {function_name} already deleted")

    return success


def clean_api_gateway():
    """Clean API Gateway REST APIs and WebSocket APIs associated with the project"""
    print("🧹 Finding and cleaning API Gateway APIs...")

    # Clean REST APIs
    apigateway_client = boto3.client("apigateway")
    project_rest_apis = []

    try:
        # List all REST APIs and filter for project APIs
        paginator = apigateway_client.get_paginator("get_rest_apis")
        pages = paginator.paginate()

        for page in pages:
            for api in page["items"]:
                api_name = api.get("name", "").lower()
                api_description = api.get("description", "").lower()
                if "lenslate" in api_name or "lenslate" in api_description:
                    project_rest_apis.append(
                        {"id": api["id"], "name": api.get("name", ""), "type": "REST"}
                    )

        # Clean WebSocket APIs (API Gateway v2)
        apigatewayv2_client = boto3.client("apigatewayv2")
        project_websocket_apis = []

        paginator_v2 = apigatewayv2_client.get_paginator("get_apis")
        pages_v2 = paginator_v2.paginate()

        for page in pages_v2:
            for api in page["Items"]:
                api_name = api.get("Name", "").lower()
                api_description = api.get("Description", "").lower()
                if "lenslate" in api_name or "lenslate" in api_description:
                    project_websocket_apis.append(
                        {
                            "id": api["ApiId"],
                            "name": api.get("Name", ""),
                            "type": api.get("ProtocolType", "WebSocket"),
                        }
                    )

        all_apis = project_rest_apis + project_websocket_apis

        if not all_apis:
            print("   📂 No project API Gateway APIs found")
            return True

        print(f"   📋 Found {len(all_apis)} project APIs:")
        for api in all_apis:
            print(f"      - {api['name']} ({api['type']}) - {api['id']}")

        print()
        success_count = 0

        # Delete REST APIs
        for api in project_rest_apis:
            try:
                print(f"   🗑️  Deleting REST API: {api['name']} ({api['id']})")
                apigateway_client.delete_rest_api(restApiId=api["id"])
                print(f"   ✅ Successfully deleted REST API: {api['name']}")
                success_count += 1
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                if error_code == "NotFoundException":
                    print(f"   ⚠️  REST API {api['name']} does not exist")
                    success_count += 1
                else:
                    print(f"   ❌ Error deleting REST API {api['name']}: {e}")
            except Exception as e:
                print(f"   ❌ Unexpected error deleting REST API {api['name']}: {e}")

        # Delete WebSocket APIs
        for api in project_websocket_apis:
            try:
                print(f"   🗑️  Deleting {api['type']} API: {api['name']} ({api['id']})")
                apigatewayv2_client.delete_api(ApiId=api["id"])
                print(f"   ✅ Successfully deleted {api['type']} API: {api['name']}")
                success_count += 1
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                if error_code == "NotFoundException":
                    print(f"   ⚠️  {api['type']} API {api['name']} does not exist")
                    success_count += 1
                else:
                    print(f"   ❌ Error deleting {api['type']} API {api['name']}: {e}")
            except Exception as e:
                print(
                    f"   ❌ Unexpected error deleting {api['type']} API {api['name']}: {e}"
                )

        if success_count == len(all_apis):
            print(f"✅ Successfully cleaned {success_count} API Gateway APIs")
            return True
        else:
            print(
                f"⚠️ Cleaned {success_count}/{len(all_apis)} API Gateway APIs with some errors"
            )
            return False

    except ClientError as e:
        print(f"❌ Error listing API Gateway APIs: {e}")
        return False


def clean_all_cognito_domains(cognito_idp_client):
    """Delete ALL Cognito domains to prevent domain-related deletion errors"""
    # First, get all user pools to check for associated domains
    domain_user_pool_mapping = {}

    try:
        paginator = cognito_idp_client.get_paginator("list_user_pools")
        pages = paginator.paginate(MaxResults=60)

        for page in pages:
            for pool in page["UserPools"]:
                pool_name = pool.get("Name", "").lower()
                if "lenslate" in pool_name:
                    pool_id = pool["Id"]

                    # Method 1: Check the user pool directly for its domain
                    try:
                        pool_details = cognito_idp_client.describe_user_pool(
                            UserPoolId=pool_id
                        )
                        domain = pool_details.get("UserPool", {}).get("Domain")
                        if domain:
                            domain_user_pool_mapping[domain] = pool_id
                            print(
                                f"   🔍 Found domain {domain} for User Pool {pool_id}"
                            )
                    except ClientError:
                        pass

                    # Method 2: Generate potential domain patterns based on pool ID
                    if "_" in pool_id:
                        suffix = pool_id.split("_")[1]
                        potential_domains = [
                            f"lenslate-auth-dev-{suffix}",
                            f"lenslate-auth-{suffix}",
                            f"lenslate-dev-{suffix}",
                        ]

                        # Check which domains actually exist for this user pool
                        for domain in potential_domains:
                            if (
                                domain not in domain_user_pool_mapping
                            ):  # Don't duplicate
                                try:
                                    domain_response = (
                                        cognito_idp_client.describe_user_pool_domain(
                                            Domain=domain
                                        )
                                    )
                                    if domain_response.get("DomainDescription"):
                                        domain_user_pool_mapping[domain] = pool_id
                                        print(
                                            f"   🔍 Found domain {domain} for User Pool {pool_id}"
                                        )
                                except ClientError:
                                    # Domain doesn't exist for this user pool, continue
                                    continue
    except Exception as e:
        print(f"   ⚠️  Could not scan user pools for domains: {e}")

    # Now delete all found domains
    domains_deleted = 0
    for domain, user_pool_id in domain_user_pool_mapping.items():
        try:
            print(f"   🗑️  Deleting domain: {domain}")
            cognito_idp_client.delete_user_pool_domain(
                Domain=domain, UserPoolId=user_pool_id
            )
            print(f"   ✅ Successfully deleted domain: {domain}")
            domains_deleted += 1

            # Wait for domain deletion to propagate
            import time

            time.sleep(3)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code in ["ResourceNotFoundException", "InvalidParameterException"]:
                # Domain doesn't exist, continue
                continue
            else:
                print(f"   ⚠️  Could not delete domain {domain}: {e}")
        except Exception as e:
            print(f"   ❌ Unexpected error with domain {domain}: {e}")

    if domains_deleted > 0:
        print(f"   ✅ Deleted {domains_deleted} Cognito domains")
        print("   ⏳ Waiting for domain deletions to fully propagate...")
        import time

        time.sleep(10)  # Extra wait for all domains to be fully deleted
    else:
        print("   📂 No Cognito domains found")


def clean_cognito_resources():
    """Clean Cognito User Pools and Identity Pools associated with the project"""
    print("🧹 Finding and cleaning Cognito resources...")

    cognito_idp_client = boto3.client("cognito-idp")
    cognito_identity_client = boto3.client("cognito-identity")

    project_user_pools = []
    project_identity_pools = []

    try:
        # Delete ALL Cognito domains (to prevent the domain deletion error)
        clean_all_cognito_domains(cognito_idp_client)

        # Clean User Pools
        paginator = cognito_idp_client.get_paginator("list_user_pools")
        pages = paginator.paginate(MaxResults=60)

        for page in pages:
            for pool in page["UserPools"]:
                pool_name = pool.get("Name", "").lower()
                if "lenslate" in pool_name:
                    project_user_pools.append(
                        {"id": pool["Id"], "name": pool.get("Name", "")}
                    )

        # Clean Identity Pools
        paginator_identity = cognito_identity_client.get_paginator(
            "list_identity_pools"
        )
        pages_identity = paginator_identity.paginate(MaxResults=60)

        for page in pages_identity:
            for pool in page["IdentityPools"]:
                pool_name = pool.get("IdentityPoolName", "").lower()
                if "lenslate" in pool_name:
                    project_identity_pools.append(
                        {
                            "id": pool["IdentityPoolId"],
                            "name": pool.get("IdentityPoolName", ""),
                        }
                    )

        all_pools = project_user_pools + project_identity_pools

        if not all_pools:
            print("   📂 No project Cognito pools found")
            return True

        print(
            f"   📋 Found {len(project_user_pools)} user pools and {len(project_identity_pools)} identity pools:"
        )
        for pool in project_user_pools:
            print(f"      - User Pool: {pool['name']} ({pool['id']})")
        for pool in project_identity_pools:
            print(f"      - Identity Pool: {pool['name']} ({pool['id']})")

        print()
        success_count = 0

        # Delete User Pools
        for pool in project_user_pools:
            try:
                print(f"   🗑️  Deleting User Pool: {pool['name']} ({pool['id']})")
                cognito_idp_client.delete_user_pool(UserPoolId=pool["id"])
                print(f"   ✅ Successfully deleted User Pool: {pool['name']}")
                success_count += 1
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                if error_code == "ResourceNotFoundException":
                    print(f"   ⚠️  User Pool {pool['name']} does not exist")
                    success_count += 1
                else:
                    print(f"   ❌ Error deleting User Pool {pool['name']}: {e}")
            except Exception as e:
                print(f"   ❌ Unexpected error deleting User Pool {pool['name']}: {e}")

        # Delete Identity Pools
        for pool in project_identity_pools:
            try:
                print(f"   🗑️  Deleting Identity Pool: {pool['name']} ({pool['id']})")
                cognito_identity_client.delete_identity_pool(IdentityPoolId=pool["id"])
                print(f"   ✅ Successfully deleted Identity Pool: {pool['name']}")
                success_count += 1
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                if error_code == "ResourceNotFoundException":
                    print(f"   ⚠️  Identity Pool {pool['name']} does not exist")
                    success_count += 1
                else:
                    print(f"   ❌ Error deleting Identity Pool {pool['name']}: {e}")
            except Exception as e:
                print(
                    f"   ❌ Unexpected error deleting Identity Pool {pool['name']}: {e}"
                )

        if success_count == len(all_pools):
            print(f"✅ Successfully cleaned {success_count} Cognito pools")
            return True
        else:
            print(
                f"⚠️ Cleaned {success_count}/{len(all_pools)} Cognito pools with some errors"
            )
            return False

    except ClientError as e:
        print(f"❌ Error listing Cognito resources: {e}")
        return False


def clean_ec2_instances():
    """Clean EC2 instances associated with the project"""
    print("🧹 Finding and cleaning EC2 instances...")

    ec2_client = boto3.client("ec2")
    project_instances = []

    try:
        # List all instances and filter for project instances
        paginator = ec2_client.get_paginator("describe_instances")
        pages = paginator.paginate()

        for page in pages:
            for reservation in page["Reservations"]:
                for instance in reservation["Instances"]:
                    # Skip terminated instances
                    if instance["State"]["Name"] == "terminated":
                        continue

                    instance_id = instance["InstanceId"]
                    instance_name = ""

                    # Check tags for project name
                    is_project_instance = False
                    for tag in instance.get("Tags", []):
                        if tag["Key"] == "Name":
                            instance_name = tag["Value"]
                        if "lenslate" in tag.get("Value", "").lower():
                            is_project_instance = True

                    # Also check if instance name contains project name
                    if "lenslate" in instance_name.lower():
                        is_project_instance = True

                    if is_project_instance:
                        project_instances.append(
                            {
                                "id": instance_id,
                                "name": instance_name,
                                "state": instance["State"]["Name"],
                                "type": instance["InstanceType"],
                            }
                        )

        if not project_instances:
            print("   📂 No project EC2 instances found")
            return True

        print(f"   📋 Found {len(project_instances)} project instances:")
        for instance in project_instances:
            print(
                f"      - {instance['name']} ({instance['id']}) - {instance['state']} ({instance['type']})"
            )

        print()
        success_count = 0

        for instance in project_instances:
            try:
                instance_id = instance["id"]
                instance_name = instance["name"]
                current_state = instance["state"]

                if current_state in ["running", "stopped", "stopping"]:
                    print(
                        f"   🗑️  Terminating instance: {instance_name} ({instance_id})"
                    )
                    ec2_client.terminate_instances(InstanceIds=[instance_id])
                    print(
                        f"   ✅ Successfully initiated termination for: {instance_name}"
                    )
                    success_count += 1
                elif current_state == "shutting-down":
                    print(f"   ⏳ Instance {instance_name} is already shutting down")
                    success_count += 1
                else:
                    print(
                        f"   ⚠️  Instance {instance_name} is in state '{current_state}' - skipping"
                    )
                    success_count += 1

            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                if error_code == "InvalidInstanceID.NotFound":
                    print(f"   ⚠️  Instance {instance['name']} does not exist")
                    success_count += 1
                else:
                    print(f"   ❌ Error terminating instance {instance['name']}: {e}")
            except Exception as e:
                print(
                    f"   ❌ Unexpected error terminating instance {instance['name']}: {e}"
                )

        if success_count == len(project_instances):
            print(f"✅ Successfully processed {success_count} EC2 instances")
            if any(i["state"] in ["running", "stopped"] for i in project_instances):
                print(
                    "ℹ️  Note: Instance termination may take a few minutes. Check AWS Console for status."
                )
            return True
        else:
            print(
                f"⚠️ Processed {success_count}/{len(project_instances)} EC2 instances with some errors"
            )
            return False

    except ClientError as e:
        print(f"❌ Error listing EC2 instances: {e}")
        return False


def clean_cloudwatch_logs():
    """Clean CloudWatch log groups associated with the project"""
    print("🧹 Finding and cleaning CloudWatch log groups...")

    logs_client = boto3.client("logs")
    project_log_groups = []

    try:
        # List all log groups and filter for project log groups
        paginator = logs_client.get_paginator("describe_log_groups")
        pages = paginator.paginate()

        for page in pages:
            for log_group in page["logGroups"]:
                log_group_name = log_group["logGroupName"]
                # Check if this log group belongs to lenslate project
                if (
                    "lenslate" in log_group_name.lower()
                    or "/aws/lambda/lenslate" in log_group_name.lower()
                ):
                    project_log_groups.append(
                        {
                            "name": log_group_name,
                            "size": log_group.get("storedBytes", 0),
                            "retention": log_group.get("retentionInDays", "Never"),
                        }
                    )

        if not project_log_groups:
            print("   📂 No project CloudWatch log groups found")
            return True

        print(f"   📋 Found {len(project_log_groups)} project log groups:")
        for log_group in project_log_groups:
            size_mb = log_group["size"] / (1024 * 1024) if log_group["size"] > 0 else 0
            print(
                f"      - {log_group['name']} ({size_mb:.2f} MB, retention: {log_group['retention']})"
            )

        print()
        success_count = 0

        for log_group in project_log_groups:
            try:
                log_group_name = log_group["name"]
                print(f"   🗑️  Deleting log group: {log_group_name}")
                logs_client.delete_log_group(logGroupName=log_group_name)
                print(f"   ✅ Successfully deleted log group: {log_group_name}")
                success_count += 1
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                if error_code == "ResourceNotFoundException":
                    print(f"   ⚠️  Log group {log_group_name} does not exist")
                    success_count += 1
                else:
                    print(f"   ❌ Error deleting log group {log_group_name}: {e}")
            except Exception as e:
                print(
                    f"   ❌ Unexpected error deleting log group {log_group_name}: {e}"
                )

        if success_count == len(project_log_groups):
            print(f"✅ Successfully cleaned {success_count} CloudWatch log groups")
            return True
        else:
            print(
                f"⚠️ Cleaned {success_count}/{len(project_log_groups)} CloudWatch log groups with some errors"
            )
            return False

    except ClientError as e:
        print(f"❌ Error listing CloudWatch log groups: {e}")
        return False


def clean_codepipeline_resources():
    """Clean CodePipeline pipelines and CodeBuild projects associated with the project"""
    print("🧹 Finding and cleaning CodePipeline resources...")

    # Clean CodePipeline pipelines
    codepipeline_client = boto3.client("codepipeline")
    codebuild_client = boto3.client("codebuild")

    project_pipelines = []
    project_builds = []

    try:
        # List all pipelines and filter for project pipelines
        paginator = codepipeline_client.get_paginator("list_pipelines")
        pages = paginator.paginate()

        for page in pages:
            for pipeline in page["pipelines"]:
                pipeline_name = pipeline["name"].lower()
                if "lenslate" in pipeline_name:
                    project_pipelines.append(
                        {
                            "name": pipeline["name"],
                            "version": pipeline.get("version", 1),
                            "created": pipeline.get("created", "Unknown"),
                            "updated": pipeline.get("updated", "Unknown"),
                        }
                    )

        # List all CodeBuild projects and filter for project builds
        paginator_build = codebuild_client.get_paginator("list_projects")
        pages_build = paginator_build.paginate()

        for page in pages_build:
            for project_name in page["projects"]:
                if "lenslate" in project_name.lower():
                    project_builds.append(project_name)

        all_resources = project_pipelines + [
            {"name": build, "type": "CodeBuild"} for build in project_builds
        ]

        if not all_resources:
            print("   📂 No project CodePipeline/CodeBuild resources found")
            return True

        print(
            f"   📋 Found {len(project_pipelines)} pipelines and {len(project_builds)} build projects:"
        )
        for pipeline in project_pipelines:
            print(f"      - Pipeline: {pipeline['name']} (v{pipeline['version']})")
        for build in project_builds:
            print(f"      - Build Project: {build}")

        print()
        success_count = 0

        # Delete CodePipeline pipelines
        for pipeline in project_pipelines:
            try:
                pipeline_name = pipeline["name"]
                print(f"   🗑️  Deleting pipeline: {pipeline_name}")
                codepipeline_client.delete_pipeline(name=pipeline_name)
                print(f"   ✅ Successfully deleted pipeline: {pipeline_name}")
                success_count += 1
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                if error_code == "PipelineNotFoundException":
                    print(f"   ⚠️  Pipeline {pipeline_name} does not exist")
                    success_count += 1
                else:
                    print(f"   ❌ Error deleting pipeline {pipeline_name}: {e}")
            except Exception as e:
                print(f"   ❌ Unexpected error deleting pipeline {pipeline_name}: {e}")

        # Delete CodeBuild projects
        for build_name in project_builds:
            try:
                print(f"   🗑️  Deleting build project: {build_name}")
                codebuild_client.delete_project(name=build_name)
                print(f"   ✅ Successfully deleted build project: {build_name}")
                success_count += 1
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                if error_code == "ResourceNotFoundException":
                    print(f"   ⚠️  Build project {build_name} does not exist")
                    success_count += 1
                else:
                    print(f"   ❌ Error deleting build project {build_name}: {e}")
            except Exception as e:
                print(
                    f"   ❌ Unexpected error deleting build project {build_name}: {e}"
                )

        total_resources = len(project_pipelines) + len(project_builds)
        if success_count == total_resources:
            print(
                f"✅ Successfully cleaned {success_count} CodePipeline/CodeBuild resources"
            )
            return True
        else:
            print(
                f"⚠️ Cleaned {success_count}/{total_resources} CodePipeline/CodeBuild resources with some errors"
            )
            return False

    except ClientError as e:
        print(f"❌ Error listing CodePipeline/CodeBuild resources: {e}")
        return False


def clean_cloudfront_distributions():
    """Clean CloudFront distributions associated with the project"""
    print("🧹 Finding and cleaning CloudFront distributions...")

    cf_client = boto3.client("cloudfront")
    project_distributions = []

    try:
        # List all distributions and filter for project distributions
        paginator = cf_client.get_paginator("list_distributions")
        pages = paginator.paginate()

        for page in pages:
            if "Items" in page["DistributionList"]:
                for distribution in page["DistributionList"]["Items"]:
                    distribution_id = distribution["Id"]
                    # Check if this distribution belongs to lenslate project
                    # We can check the comment, origins, or tags, or specific known IDs
                    try:
                        # Get detailed info about the distribution
                        detail_response = cf_client.get_distribution(Id=distribution_id)
                        distribution_config = detail_response["Distribution"][
                            "DistributionConfig"
                        ]

                        # Check comment for project name
                        comment = distribution_config.get("Comment", "").lower()

                        # Check origins for S3 buckets that might contain project name
                        origins_match = False
                        for origin in distribution_config["Origins"]["Items"]:
                            origin_domain = origin["DomainName"].lower()
                            if "lenslate" in origin_domain:
                                origins_match = True
                                break

                        # Also check for known distribution IDs
                        known_distribution_ids = [
                            "E2NOVZN5F0GP7Y"
                        ]  # Add known project distribution IDs here

                        if (
                            "lenslate" in comment
                            or origins_match
                            or distribution_id in known_distribution_ids
                        ):
                            project_distributions.append(
                                {
                                    "Id": distribution_id,
                                    "Comment": distribution_config.get("Comment", ""),
                                    "Status": distribution["Status"],
                                    "ETag": detail_response["ETag"],
                                }
                            )
                    except ClientError as e:
                        # If we can't get details, skip this distribution
                        print(
                            f"   ⚠️  Could not get details for distribution {distribution_id}: {e}"
                        )
                        continue

        if not project_distributions:
            print("   📂 No project CloudFront distributions found")
            return True

        print(f"   📋 Found {len(project_distributions)} project distributions:")
        for dist in project_distributions:
            print(f"      - {dist['Id']} ({dist['Comment']})")

        print()
        success_count = 0
        has_enabled_distributions = False

        for distribution in project_distributions:
            distribution_id = distribution["Id"]

            try:
                # First, disable the distribution if it's enabled
                print(f"   🔄 Checking status of distribution: {distribution_id}")

                # Get current distribution config
                response = cf_client.get_distribution_config(Id=distribution_id)
                config = response["DistributionConfig"]
                current_etag = response["ETag"]

                if config["Enabled"]:
                    has_enabled_distributions = True
                    print(f"   🔄 Disabling distribution: {distribution_id}")
                    config["Enabled"] = False

                    # Update the distribution to disable it
                    cf_client.update_distribution(
                        Id=distribution_id,
                        DistributionConfig=config,
                        IfMatch=current_etag,
                    )

                    print(
                        f"   ⏳ Distribution {distribution_id} is being disabled. This may take several minutes..."
                    )
                    print(
                        "   ℹ️  You may need to wait for the distribution to be disabled before it can be deleted."
                    )
                    print(
                        "   ℹ️  Status will change from 'Deployed' to 'Disabled' - you can check AWS Console."
                    )
                    success_count += 1
                else:
                    print(
                        f"   🗑️  Distribution {distribution_id} is already disabled, attempting deletion..."
                    )

                    # Try to delete the disabled distribution
                    try:
                        cf_client.delete_distribution(
                            Id=distribution_id, IfMatch=current_etag
                        )
                        print(
                            f"   ✅ Successfully deleted distribution: {distribution_id}"
                        )
                        success_count += 1
                    except ClientError as delete_error:
                        delete_error_code = delete_error.response.get("Error", {}).get(
                            "Code", "Unknown"
                        )
                        if delete_error_code == "DistributionNotDisabled":
                            print(
                                f"   ⚠️  Distribution {distribution_id} is still being disabled. Please wait and try again later."
                            )
                            success_count += 1  # Count as success since we initiated the disable process
                        else:
                            print(
                                f"   ❌ Error deleting distribution {distribution_id}: {delete_error}"
                            )

            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                if error_code == "NoSuchDistribution":
                    print(f"   ⚠️  Distribution {distribution_id} does not exist")
                    success_count += 1
                else:
                    print(f"   ❌ Error with distribution {distribution_id}: {e}")
            except Exception as e:
                print(
                    f"   ❌ Unexpected error with distribution {distribution_id}: {e}"
                )

        if success_count == len(project_distributions):
            print(f"✅ Successfully processed {success_count} CloudFront distributions")
            if has_enabled_distributions:
                print(
                    "ℹ️  Note: Some distributions may still be disabling. Check AWS Console and re-run cleanup if needed."
                )
            return True
        else:
            print(
                f"⚠️ Processed {success_count}/{len(project_distributions)} CloudFront distributions with some errors"
            )
            return False

    except ClientError as e:
        print(f"❌ Error listing CloudFront distributions: {e}")
        return False


if __name__ == "__main__":
    print("🚨 COMPLETE DEPLOYMENT CLEANUP")
    print("=" * 60)
    print("This will delete:")
    print("  • All .terraform directories and state files")
    print("  • All .tfplan files")
    print("  • All ZIP files (Lambda packages)")
    print("  • Terraform destroy (app-stack and data-stack)")
    print("  • ALL CodePipeline pipelines and CodeBuild projects")
    print("  • ALL CloudFront distributions")
    print("  • ALL API Gateway APIs")
    print("  • ALL Lambda functions")
    print("  • ALL Cognito user and identity pools")
    print("  • ALL S3 buckets (emptied and deleted)")
    print("  • ALL DynamoDB tables")
    print("  • ALL EC2 instances")
    print("  • ALL CloudWatch log groups")
    print("  • ALL CloudFormation stacks")
    print("  • ALL project AWS resources")
    print()
    print("⚠️  WARNING: This action cannot be undone!")
    print("⚠️  This will completely reset your deployment!")
    print("⚠️  You will need to redeploy everything from scratch!")

    print("\nOptions:")
    print("1. FULL CLEANUP (terraform destroy + AWS cleanup - recommended)")
    print("2. Local files only (Terraform state, ZIP files)")
    print("3. AWS resources only (terraform destroy + S3, DynamoDB, Lambda, etc.)")
    print("4. Cancel")

    choice = input("\nEnter your choice (1/2/3/4): ").strip()

    if choice == "1":
        print("\n🧹 Starting FULL cleanup...")
        print("⚠️  Last chance to cancel - this will delete EVERYTHING!")
        final_confirm = input("Type 'DELETE EVERYTHING' to proceed: ")

        if final_confirm == "DELETE EVERYTHING":
            print("\n🧹 Starting complete cleanup process...")

            # Clean local files first
            print("\n📁 CLEANING LOCAL FILES...")
            terraform_success = clean_terraform_files()
            zip_success = clean_zip_files()

            # Terraform destroy before AWS resource cleanup
            print("\n🏗️  TERRAFORM DESTROY...")
            terraform_destroy_success = execute_terraform_stack_destruction()

            # Clean tracked resources first (more targeted)
            print("\n📋 CLEANING TRACKED RESOURCES...")
            tracked_success = clean_tracked_resources()

            # Clean remaining AWS resources
            print("\n☁️  CLEANING REMAINING AWS RESOURCES...")
            # 1. CodePipeline and CodeBuild (should be cleaned early)
            codepipeline_success = clean_codepipeline_resources()

            # 2. CloudFront (needs to be disabled first, takes time)
            cloudfront_success = clean_cloudfront_distributions()

            # 3. API Gateway
            api_gateway_success = clean_api_gateway()

            # 4. Lambda functions
            lambda_success = clean_lambda_functions()

            # 5. Cognito (user and identity pools)
            cognito_success = clean_cognito_resources()

            # 6. S3 buckets
            s3_success = clean_all_s3_buckets()

            # 7. DynamoDB tables
            db_success = clean_all_dynamodb_tables()

            # 8. EC2 instances
            ec2_success = clean_ec2_instances()

            # 9. CloudWatch log groups
            cloudwatch_success = clean_cloudwatch_logs()

            # Clean CloudFormation stacks last (may contain other resources)
            cf_success = clean_cloudformation_stacks()

            print("\n" + "=" * 60)
            if all(
                [
                    terraform_success,
                    zip_success,
                    terraform_destroy_success,
                    tracked_success,
                    codepipeline_success,
                    cloudfront_success,
                    api_gateway_success,
                    lambda_success,
                    cognito_success,
                    s3_success,
                    db_success,
                    ec2_success,
                    cloudwatch_success,
                    cf_success,
                ]
            ):
                print("🎉 FULL CLEANUP COMPLETED SUCCESSFULLY!")
                print("Your deployment environment is now completely clean.")
                print("You can now run a fresh deployment from scratch.")
            else:
                print("⚠️ Cleanup completed with some errors. Check the logs above.")
        else:
            print("❌ Full cleanup cancelled.")

    elif choice == "2":
        print("\n🧹 Starting local files cleanup...")

        terraform_success = clean_terraform_files()
        zip_success = clean_zip_files()

        if terraform_success and zip_success:
            print("\n🎉 Local files cleanup completed successfully!")
        else:
            print("\n⚠️ Local files cleanup completed with some errors.")

    elif choice == "3":
        print("\n🧹 Starting AWS resources cleanup...")
        print("⚠️  This will delete all AWS resources for the project!")
        confirm = input("Type 'DELETE AWS' to proceed: ")

        if confirm == "DELETE AWS":
            # Terraform destroy first
            print("\n🏗️  TERRAFORM DESTROY...")
            terraform_destroy_success = execute_terraform_stack_destruction()

            # Clean tracked resources
            print("\n📋 CLEANING TRACKED RESOURCES...")
            tracked_success = clean_tracked_resources()

            # AWS cleanup
            print("\n☁️  CLEANING REMAINING AWS RESOURCES...")

            # 1. CodePipeline and CodeBuild (should be cleaned early)
            codepipeline_success = clean_codepipeline_resources()

            # 2. CloudFront (needs to be disabled first, takes time)
            cloudfront_success = clean_cloudfront_distributions()

            # 3. API Gateway
            api_gateway_success = clean_api_gateway()

            # 4. Lambda functions
            lambda_success = clean_lambda_functions()

            # 5. Cognito (user and identity pools)
            cognito_success = clean_cognito_resources()

            # 6. S3 buckets
            s3_success = clean_all_s3_buckets()

            # 7. DynamoDB tables
            db_success = clean_all_dynamodb_tables()

            # 8. EC2 instances
            ec2_success = clean_ec2_instances()

            # 9. CloudWatch log groups
            cloudwatch_success = clean_cloudwatch_logs()

            # Clean CloudFormation stacks last (may contain other resources)
            cf_success = clean_cloudformation_stacks()

            if all(
                [
                    terraform_destroy_success,
                    tracked_success,
                    codepipeline_success,
                    cloudfront_success,
                    api_gateway_success,
                    lambda_success,
                    cognito_success,
                    s3_success,
                    db_success,
                    ec2_success,
                    cloudwatch_success,
                    cf_success,
                ]
            ):
                print("\n🎉 AWS resources cleanup completed successfully!")
            else:
                print("\n⚠️ AWS resources cleanup completed with some errors.")
        else:
            print("❌ AWS resources cleanup cancelled.")

    else:
        print("❌ Cleanup cancelled.")

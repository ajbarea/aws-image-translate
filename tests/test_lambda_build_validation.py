#!/usr/bin/env python3
"""
Test module for Lambda build validation.
This validates that all Lambda function zip files are built correctly and in the right locations.
"""

from pathlib import Path

import pytest


class TestLambdaBuildValidation:
    """Test class for validating Lambda function build outputs."""

    @pytest.fixture(scope="class")
    def terraform_paths(self):
        """Fixture providing terraform directory paths."""
        project_root = Path(__file__).parent.parent
        terraform_root = project_root / "terraform"
        terraform_app_stack = terraform_root / "app-stack"

        return {
            "terraform_root": terraform_root,
            "terraform_app_stack": terraform_app_stack,
        }

    @pytest.fixture(scope="class")
    def expected_functions(self):
        """Fixture providing the expected Lambda functions and their locations."""
        return {
            "app_stack_functions": [
                "image_processor",
                "gallery_lister",
                "cognito_triggers",
                "user_manager",
                "mmid_populator",
            ],
            "root_functions": ["reddit_populator"],
        }

    def test_terraform_directories_exist(self, terraform_paths):
        """Test that required terraform directories exist."""
        assert terraform_paths[
            "terraform_root"
        ].exists(), "terraform/ directory should exist"
        assert terraform_paths[
            "terraform_app_stack"
        ].exists(), "terraform/app-stack/ directory should exist"

    def test_app_stack_lambda_zips_exist(self, terraform_paths, expected_functions):
        """Test that all app-stack Lambda zip files exist and are valid."""
        terraform_app_stack = terraform_paths["terraform_app_stack"]

        for function_name in expected_functions["app_stack_functions"]:
            zip_path = terraform_app_stack / f"{function_name}.zip"

            assert (
                zip_path.exists()
            ), f"Lambda zip file should exist: terraform/app-stack/{function_name}.zip"

            # Check that the file is not empty
            assert (
                zip_path.stat().st_size > 0
            ), f"Lambda zip file should not be empty: {function_name}.zip"

            # Check minimum reasonable size (1KB)
            assert (
                zip_path.stat().st_size >= 1024
            ), f"Lambda zip file suspiciously small: {function_name}.zip ({zip_path.stat().st_size} bytes)"

    def test_root_lambda_zips_exist(self, terraform_paths, expected_functions):
        """Test that root-level Lambda zip files exist and are valid."""
        terraform_root = terraform_paths["terraform_root"]

        for function_name in expected_functions["root_functions"]:
            zip_path = terraform_root / f"{function_name}.zip"

            assert (
                zip_path.exists()
            ), f"Lambda zip file should exist: terraform/{function_name}.zip"

            # Check that the file is not empty
            assert (
                zip_path.stat().st_size > 0
            ), f"Lambda zip file should not be empty: {function_name}.zip"

            # reddit_populator should be larger due to dependencies
            if function_name == "reddit_populator":
                assert (
                    zip_path.stat().st_size >= 100000
                ), f"reddit_populator.zip should be substantial due to dependencies ({zip_path.stat().st_size} bytes)"

    def test_all_expected_lambda_functions_built(
        self, terraform_paths, expected_functions
    ):
        """Test that all expected Lambda functions have been built."""
        terraform_root = terraform_paths["terraform_root"]
        terraform_app_stack = terraform_paths["terraform_app_stack"]

        all_functions = (
            expected_functions["app_stack_functions"]
            + expected_functions["root_functions"]
        )
        built_functions = []
        missing_functions = []

        # Check app-stack functions
        for function_name in expected_functions["app_stack_functions"]:
            zip_path = terraform_app_stack / f"{function_name}.zip"
            if zip_path.exists():
                built_functions.append(f"terraform/app-stack/{function_name}.zip")
            else:
                missing_functions.append(f"terraform/app-stack/{function_name}.zip")

        # Check root functions
        for function_name in expected_functions["root_functions"]:
            zip_path = terraform_root / f"{function_name}.zip"
            if zip_path.exists():
                built_functions.append(f"terraform/{function_name}.zip")
            else:
                missing_functions.append(f"terraform/{function_name}.zip")

        # Assertions with detailed error messages
        assert (
            len(missing_functions) == 0
        ), f"Missing Lambda zip files: {missing_functions}"
        assert len(built_functions) == len(
            all_functions
        ), f"Expected {len(all_functions)} functions, found {len(built_functions)}"

    def test_lambda_zip_file_integrity(self, terraform_paths, expected_functions):
        """Test the integrity and contents of Lambda zip files."""
        import zipfile

        terraform_root = terraform_paths["terraform_root"]
        terraform_app_stack = terraform_paths["terraform_app_stack"]

        # Test app-stack functions
        for function_name in expected_functions["app_stack_functions"]:
            zip_path = terraform_app_stack / f"{function_name}.zip"
            if zip_path.exists():
                # Test that zip file is valid
                try:
                    with zipfile.ZipFile(zip_path, "r") as zf:
                        # Test zip file integrity
                        bad_file = zf.testzip()
                        assert (
                            bad_file is None
                        ), f"Corrupted file in {function_name}.zip: {bad_file}"

                        # Check that it contains Python files
                        files = zf.namelist()
                        python_files = [f for f in files if f.endswith(".py")]
                        assert (
                            len(python_files) > 0
                        ), f"No Python files found in {function_name}.zip"

                        # Check for required files
                        expected_main_file = f"{function_name}.py"
                        assert (
                            expected_main_file in files
                        ), f"Main handler file {expected_main_file} not found in zip"
                        assert (
                            "aws_clients.py" in files
                        ), f"aws_clients.py not found in {function_name}.zip"

                except zipfile.BadZipFile:
                    pytest.fail(f"Invalid zip file: {function_name}.zip")

        # Test root functions
        for function_name in expected_functions["root_functions"]:
            zip_path = terraform_root / f"{function_name}.zip"
            if zip_path.exists():
                try:
                    with zipfile.ZipFile(zip_path, "r") as zf:
                        bad_file = zf.testzip()
                        assert (
                            bad_file is None
                        ), f"Corrupted file in {function_name}.zip: {bad_file}"

                        files = zf.namelist()
                        python_files = [f for f in files if f.endswith(".py")]
                        assert (
                            len(python_files) > 0
                        ), f"No Python files found in {function_name}.zip"

                        # reddit_populator has specific file requirements
                        if function_name == "reddit_populator":
                            assert (
                                "reddit_populator_sync.py" in files
                            ), "reddit_populator_sync.py not found"
                            assert (
                                "reddit_scraper_sync.py" in files
                            ), "reddit_scraper_sync.py not found"
                            assert (
                                "aws_clients.py" in files
                            ), "aws_clients.py not found in reddit_populator.zip"

                            # Should contain dependencies
                            dependency_files = [
                                f
                                for f in files
                                if not f.endswith(".py") and not f.endswith("/")
                            ]
                            assert (
                                len(dependency_files) > 0
                            ), "reddit_populator.zip should contain dependency files"

                except zipfile.BadZipFile:
                    pytest.fail(f"Invalid zip file: {function_name}.zip")

    @pytest.mark.integration
    def test_lambda_build_summary_report(self, terraform_paths, expected_functions):
        """Generate a summary report of all Lambda builds (integration test)."""
        terraform_root = terraform_paths["terraform_root"]
        terraform_app_stack = terraform_paths["terraform_app_stack"]

        print("\n" + "=" * 60)
        print("Lambda Build Validation Summary")
        print("=" * 60)

        total_functions = 0
        total_size = 0

        # Report app-stack functions
        print("\n📁 App-Stack Functions (terraform/app-stack/):")
        for function_name in expected_functions["app_stack_functions"]:
            zip_path = terraform_app_stack / f"{function_name}.zip"
            if zip_path.exists():
                size = zip_path.stat().st_size
                print(f"  ✅ {function_name}.zip ({size:,} bytes)")
                total_functions += 1
                total_size += size
            else:
                print(f"  ❌ {function_name}.zip (MISSING)")

        # Report root functions
        print("\n📁 Root Functions (terraform/):")
        for function_name in expected_functions["root_functions"]:
            zip_path = terraform_root / f"{function_name}.zip"
            if zip_path.exists():
                size = zip_path.stat().st_size
                print(f"  ✅ {function_name}.zip ({size:,} bytes)")
                total_functions += 1
                total_size += size
            else:
                print(f"  ❌ {function_name}.zip (MISSING)")

        print("\n📊 Summary:")
        print(
            f"  Total Functions: {total_functions}/{len(expected_functions['app_stack_functions']) + len(expected_functions['root_functions'])}"
        )
        print(f"  Total Size: {total_size:,} bytes ({total_size / 1024 / 1024:.2f} MB)")
        print("=" * 60)

        # This test passes if we reach here without assertions failing
        assert total_functions > 0, "At least some Lambda functions should be built"

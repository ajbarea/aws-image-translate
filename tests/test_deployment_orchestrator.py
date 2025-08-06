import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, call, mock_open, patch

import pytest

from deployment_logic.deployment_orchestrator import DeploymentOrchestrator
from deployment_logic.progress_indicator import ProgressIndicator
from deployment_logic.resource_naming import ResourceNameGenerator


# Mock ProgressIndicator to avoid printing to console during tests
@pytest.fixture(autouse=True)
def mock_progress_indicator():
    with patch(
        "deployment_logic.deployment_orchestrator.ProgressIndicator",
        spec=ProgressIndicator,
    ) as mock_pi:
        yield mock_pi


@pytest.fixture
def orchestrator():
    """Fixture for a DeploymentOrchestrator instance."""
    # We patch Path.absolute() in the __init__ call to avoid filesystem access upon instantiation.
    with patch.object(Path, "absolute", return_value=Path("/fake/project/root")):
        orc = DeploymentOrchestrator(ci_mode=True)

    # Override paths for test predictability
    orc.root_dir = Path("/fake/project/root")
    orc.terraform_dir = orc.root_dir / "terraform" / "app-stack"
    orc.data_stack_dir = orc.root_dir / "terraform" / "data-stack"
    orc.lambda_dir = orc.root_dir / "lambda_functions"
    orc.env_file = orc.root_dir / ".env.local"
    orc.backup_dir = orc.root_dir / "terraform" / "backups"

    # Assign mock commands
    orc.python_cmd = "python"
    orc.terraform_cmd = "terraform"
    orc.aws_cmd = "aws"

    # Mock resource name generator
    mock_resource_generator = MagicMock(spec=ResourceNameGenerator)
    mock_backend_names = {
        "state_bucket": "lenslate-terraform-state-123456-abc123",
        "lock_table": "lenslate-terraform-lock-123456-abc123",
    }
    mock_resource_generator.get_terraform_backend_names.return_value = (
        mock_backend_names
    )
    orc.resource_name_generator = mock_resource_generator

    return orc


@pytest.fixture
def mock_subprocess_success():
    """Fixture for successful subprocess.run calls."""
    return MagicMock(returncode=0, stdout="Success", stderr="")


@pytest.fixture
def mock_subprocess_failure():
    """Fixture for failed subprocess.run calls."""
    return MagicMock(returncode=1, stdout="", stderr="Error occurred")


def test_init(orchestrator):
    """Test that the orchestrator initializes with correct default values."""
    assert orchestrator.ci_mode is True
    assert orchestrator.root_dir == Path("/fake/project/root")
    assert orchestrator.terraform_dir == Path("/fake/project/root/terraform/app-stack")
    assert orchestrator.deployment_started is False
    assert orchestrator.resources_created == []


@patch("platform.system")
def test_detect_platform(mock_system, orchestrator):
    """Test platform detection for various operating systems."""
    test_cases = {
        "Windows": "windows",
        "Darwin": "darwin",
        "Linux": "linux",
        "Java": "unknown",  # Example of an unknown system
    }
    for system_name, expected in test_cases.items():
        mock_system.return_value = system_name
        assert orchestrator.detect_platform() == expected


@patch("shutil.which")
def test_check_command_exists(mock_which, orchestrator):
    """Test the check for command existence."""
    mock_which.return_value = "/path/to/command"
    assert orchestrator.check_command_exists("some_command") is True
    mock_which.assert_called_with("some_command")

    mock_which.return_value = None
    assert orchestrator.check_command_exists("another_command") is False
    mock_which.assert_called_with("another_command")


def test_get_platform_install_instructions(orchestrator):
    """Test that correct, platform-specific instructions are returned."""
    orchestrator.platform = "windows"
    assert "winget" in orchestrator.get_platform_install_instructions("terraform")

    orchestrator.platform = "darwin"
    assert "brew" in orchestrator.get_platform_install_instructions("aws")

    orchestrator.platform = "linux"
    assert "package manager" in orchestrator.get_platform_install_instructions("python")
    assert "apt" in orchestrator.get_platform_install_instructions("aws")

    orchestrator.platform = "unknown"
    assert "Please install foo" in orchestrator.get_platform_install_instructions("foo")


@patch("subprocess.run")
def test_validate_terraform_version_success(mock_run, orchestrator):
    """Test successful validation of a compliant Terraform version."""
    mock_run.return_value = MagicMock(
        returncode=0, stdout=json.dumps({"terraform_version": "1.8.5"})
    )
    assert orchestrator.validate_terraform_version() is True
    mock_run.assert_called_once_with(
        ["terraform", "version", "-json"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


@patch("subprocess.run")
def test_validate_terraform_version_too_old(mock_run, orchestrator):
    """Test detection of an outdated Terraform version."""
    mock_run.return_value = MagicMock(
        returncode=0, stdout=json.dumps({"terraform_version": "1.7.9"})
    )
    assert orchestrator.validate_terraform_version() is False


@patch("subprocess.run")
def test_validate_terraform_version_json_fails_fallback_succeeds(
    mock_run, orchestrator
):
    """Test fallback to text-based version check when JSON output fails."""
    mock_run.side_effect = [
        MagicMock(returncode=1, stdout="error"),  # Fails JSON check
        MagicMock(returncode=0, stdout="Terraform v1.8.0"),  # Succeeds text check
    ]
    assert orchestrator.validate_terraform_version() is True
    assert mock_run.call_count == 2
    calls = [
        call(
            ["terraform", "version", "-json"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        ),
        call(["terraform", "version"], capture_output=True, text=True, timeout=10),
    ]
    mock_run.assert_has_calls(calls)


@patch("pathlib.Path.exists", return_value=False)
def test_handle_missing_env_file_in_ci_mode(mock_exists, orchestrator):
    """Test that a minimal .env.local is created in CI mode when none exists."""
    orchestrator.ci_mode = True
    m = mock_open()
    with patch("builtins.open", m):
        assert orchestrator._handle_missing_env_file() is True

    mock_exists.assert_called()
    m.assert_called_once_with(orchestrator.env_file, "w", encoding="utf-8")
    handle = m()
    # Check that some content was written
    assert len(handle.write.call_args[0][0]) > 0
    assert "Minimal Configuration" in handle.write.call_args[0][0]


@patch("builtins.input", return_value="1")
@patch(
    "pathlib.Path.exists",
    side_effect=[False, True],  # .env.local missing, .env.example exists
)
def test_handle_missing_env_file_with_user_prompt_continue(
    mock_exists, mock_input, orchestrator
):
    """Test user choosing to continue without optional features."""
    orchestrator.ci_mode = False
    m = mock_open()
    with patch("builtins.open", m):
        assert orchestrator._prompt_for_optional_features() is True

    mock_input.assert_called_once()
    m.assert_called_once_with(orchestrator.env_file, "w", encoding="utf-8")


@patch("builtins.input", return_value="2")
@patch("shutil.copy2")
@patch(
    "pathlib.Path.exists",
    side_effect=[True, True],  # .env.example exists, .env.local exists after copy
)
def test_handle_missing_env_file_with_user_prompt_configure(
    mock_exists, mock_copy, mock_input, orchestrator
):
    """Test user choosing to configure optional features."""
    orchestrator.ci_mode = False
    # Mock file content for the copied .env.local
    m = mock_open(read_data="REDDIT_CLIENT_ID=")
    with patch("builtins.open", m):
        # Mock _handle_existing_env_file to avoid its side effects
        with patch.object(
            orchestrator, "_handle_existing_env_file", return_value=True
        ) as mock_handle_existing:
            assert orchestrator._configure_optional_features() is True
            mock_handle_existing.assert_called_once()

    mock_copy.assert_called_once_with(
        orchestrator.root_dir / ".env.example", orchestrator.env_file
    )
    mock_input.assert_called_once()


@patch("pathlib.Path.exists", return_value=True)
def test_handle_existing_env_file(mock_exists, orchestrator):
    """Test handling of an existing .env.local file."""
    m = mock_open(
        read_data="REDDIT_CLIENT_ID=some_id\nREDDIT_CLIENT_SECRET=some_secret"
    )
    with patch("builtins.open", m):
        with patch.object(orchestrator, "validate_env_file_content", return_value=True):
            assert orchestrator._handle_existing_env_file() is True


@patch("subprocess.run")
def test_build_lambda_functions_success(mock_run, orchestrator):
    """Test a successful Lambda build process."""
    mock_run.return_value = MagicMock(returncode=0, stdout="Build successful")
    with patch("pathlib.Path.exists", return_value=True):
        assert orchestrator.build_lambda_functions() is True

    mock_run.assert_called_once()
    args, kwargs = mock_run.call_args
    assert args[0] == [
        orchestrator.python_cmd,
        str(orchestrator.lambda_dir / "build_all.py"),
    ]
    assert kwargs["cwd"] == str(orchestrator.lambda_dir)


@patch("subprocess.run")
def test_build_lambda_functions_failure(mock_run, orchestrator):
    """Test a failed Lambda build process and error analysis."""
    mock_run.return_value = MagicMock(
        returncode=1, stderr="Build failed: some error", stdout=""
    )
    with patch("pathlib.Path.exists", return_value=True):
        with patch.object(orchestrator, "_analyze_lambda_build_error") as mock_analyze:
            assert orchestrator.build_lambda_functions() is False
            mock_analyze.assert_called_once_with("Build failed: some error", "")


@patch("deployment_logic.deployment_orchestrator.PythonDetector")
@patch.object(DeploymentOrchestrator, "check_command_exists")
@patch.object(DeploymentOrchestrator, "_handle_environment_file")
@patch.object(DeploymentOrchestrator, "_verify_and_fix_configuration")
@patch.object(DeploymentOrchestrator, "validate_terraform_configuration")
@patch("pathlib.Path.exists")
def test_validate_prerequisites_success(
    mock_path_exists,
    mock_validate_tf_config,
    mock_verify_fix,
    mock_handle_env,
    mock_check_cmd,
    mock_py_detector,
    orchestrator,
):
    """Test a successful prerequisite validation flow."""
    # Mock all checks to return success
    mock_py_detector.return_value.detect_and_validate.return_value = (True, "python3")
    mock_check_cmd.side_effect = [True, True]  # terraform, aws
    orchestrator.validate_terraform_version = MagicMock(return_value=True)
    mock_handle_env.return_value = True
    mock_verify_fix.return_value = True
    mock_validate_tf_config.return_value = True
    mock_path_exists.return_value = True  # For post-deploy script and lambda files

    assert orchestrator.validate_prerequisites() is True
    assert orchestrator.python_cmd == "python3"
    assert orchestrator.terraform_cmd == "terraform"
    assert orchestrator.aws_cmd == "aws"


@patch("deployment_logic.deployment_orchestrator.PythonDetector")
def test_validate_prerequisites_python_fails(mock_py_detector, orchestrator):
    """Test prerequisite validation failure when Python is not found."""
    mock_py_detector.return_value.detect_and_validate.return_value = (False, None)
    assert orchestrator.validate_prerequisites() is False


@patch("deployment_logic.deployment_orchestrator.PythonDetector")
@patch.object(DeploymentOrchestrator, "check_command_exists", return_value=False)
def test_validate_prerequisites_terraform_fails(
    mock_check_cmd, mock_py_detector, orchestrator
):
    """Test prerequisite validation failure when Terraform is not found."""
    mock_py_detector.return_value.detect_and_validate.return_value = (True, "python3")
    assert orchestrator.validate_prerequisites() is False
    # check_command_exists is called for terraform first
    mock_check_cmd.assert_called_with("terraform")


@patch.object(DeploymentOrchestrator, "_deploy_terraform_stack")
@patch.object(DeploymentOrchestrator, "_generate_terraform_vars", return_value=True)
@patch.object(DeploymentOrchestrator, "validate_prerequisites", return_value=True)
@patch.object(DeploymentOrchestrator, "build_lambda_functions", return_value=True)
@patch.object(DeploymentOrchestrator, "validate_lambda_zip_files", return_value=True)
@patch.object(
    DeploymentOrchestrator, "_create_terraform_state_bucket", return_value=True
)
@patch.object(DeploymentOrchestrator, "_create_terraform_lock_table", return_value=True)
@patch.object(
    DeploymentOrchestrator, "_update_app_stack_data_bucket_reference", return_value=True
)
def test_run_method_dual_stack_deployment_success(
    mock_update_ref,
    mock_create_lock_table,
    mock_create_bucket,
    mock_validate_zip,
    mock_build_lambda,
    mock_validate_prereq,
    mock_generate_vars,
    mock_deploy_stack,
    orchestrator,
):
    """Test that run method deploys both stacks in correct order."""
    # Mock successful deployment for both stacks
    mock_deploy_stack.return_value = True

    result = orchestrator.run()

    assert result is True
    # Verify _deploy_terraform_stack was called twice with correct parameters
    assert mock_deploy_stack.call_count == 2
    expected_calls = [
        call("data-stack", orchestrator.data_stack_dir),
        call("app-stack", orchestrator.terraform_dir),
    ]
    mock_deploy_stack.assert_has_calls(expected_calls, any_order=False)


@patch.object(DeploymentOrchestrator, "_deploy_terraform_stack")
@patch.object(DeploymentOrchestrator, "_generate_terraform_vars", return_value=True)
@patch.object(DeploymentOrchestrator, "validate_prerequisites", return_value=True)
@patch.object(DeploymentOrchestrator, "build_lambda_functions", return_value=True)
@patch.object(DeploymentOrchestrator, "validate_lambda_zip_files", return_value=True)
@patch.object(
    DeploymentOrchestrator, "_create_terraform_state_bucket", return_value=True
)
@patch.object(DeploymentOrchestrator, "_create_terraform_lock_table", return_value=True)
def test_run_method_data_stack_failure_stops_deployment(
    mock_create_lock_table,
    mock_create_bucket,
    mock_validate_zip,
    mock_build_lambda,
    mock_validate_prereq,
    mock_generate_vars,
    mock_deploy_stack,
    orchestrator,
):
    """Test that data-stack failure stops deployment before app-stack."""
    # Mock data-stack failure
    mock_deploy_stack.return_value = False

    result = orchestrator.run()

    assert result is False
    # Verify _deploy_terraform_stack was called only once (data-stack failed)
    assert mock_deploy_stack.call_count == 1
    mock_deploy_stack.assert_called_with("data-stack", orchestrator.data_stack_dir)


@patch.object(DeploymentOrchestrator, "_deploy_terraform_stack")
@patch.object(DeploymentOrchestrator, "_generate_terraform_vars", return_value=True)
@patch.object(DeploymentOrchestrator, "validate_prerequisites", return_value=True)
@patch.object(DeploymentOrchestrator, "build_lambda_functions", return_value=True)
@patch.object(DeploymentOrchestrator, "validate_lambda_zip_files", return_value=True)
@patch.object(
    DeploymentOrchestrator, "_create_terraform_state_bucket", return_value=True
)
@patch.object(DeploymentOrchestrator, "_create_terraform_lock_table", return_value=True)
@patch.object(
    DeploymentOrchestrator, "_update_app_stack_data_bucket_reference", return_value=True
)
def test_run_method_app_stack_failure_after_data_stack_success(
    mock_update_ref,
    mock_create_lock_table,
    mock_create_bucket,
    mock_validate_zip,
    mock_build_lambda,
    mock_validate_prereq,
    mock_generate_vars,
    mock_deploy_stack,
    orchestrator,
):
    """Test that app-stack failure is reported after successful data-stack deployment."""
    # Mock data-stack success, app-stack failure
    mock_deploy_stack.side_effect = [True, False]

    result = orchestrator.run()

    assert result is False
    # Verify _deploy_terraform_stack was called twice (both stacks attempted)
    assert mock_deploy_stack.call_count == 2
    expected_calls = [
        call("data-stack", orchestrator.data_stack_dir),
        call("app-stack", orchestrator.terraform_dir),
    ]
    mock_deploy_stack.assert_has_calls(expected_calls, any_order=False)


# Tests for _deploy_terraform_stack method
@patch("subprocess.run")
def test_deploy_terraform_stack_success(
    mock_run, orchestrator, mock_subprocess_success
):
    """Test successful deployment of a single terraform stack."""
    mock_run.side_effect = [
        mock_subprocess_success,  # plan
        mock_subprocess_success,  # apply
    ]

    result = orchestrator._deploy_terraform_stack(
        "data-stack", orchestrator.data_stack_dir
    )

    assert result is True
    # Verify terraform commands called in correct order
    expected_calls = [
        call(
            ["terraform", "plan", "-out=tfplan"],
            cwd=str(orchestrator.data_stack_dir),
            capture_output=True,
            text=True,
            timeout=300,
        ),
        call(
            ["terraform", "apply", "-auto-approve", "tfplan"],
            cwd=str(orchestrator.data_stack_dir),
            capture_output=True,
            text=True,
            timeout=1800,
        ),
    ]
    mock_run.assert_has_calls(expected_calls)
    assert mock_run.call_count == 2


@patch("subprocess.run")
def test_deploy_terraform_stack_plan_failure(mock_run, orchestrator):
    """Test deployment failure during terraform plan."""
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Plan failed")

    result = orchestrator._deploy_terraform_stack(
        "data-stack", orchestrator.data_stack_dir
    )

    assert result is False
    # Verify plan was called, but not apply
    assert mock_run.call_count == 1
    expected_calls = [
        call(
            ["terraform", "plan", "-out=tfplan"],
            cwd=str(orchestrator.data_stack_dir),
            capture_output=True,
            text=True,
            timeout=300,
        ),
    ]
    mock_run.assert_has_calls(expected_calls)


@patch("subprocess.run")
def test_deploy_terraform_stack_apply_failure(mock_run, orchestrator):
    """Test deployment failure during terraform apply."""
    mock_run.side_effect = [
        MagicMock(returncode=0, stdout="Plan success", stderr=""),
        MagicMock(returncode=1, stdout="", stderr="Apply failed"),
    ]

    result = orchestrator._deploy_terraform_stack(
        "app-stack", orchestrator.terraform_dir
    )

    assert result is False
    # Verify both commands were called
    assert mock_run.call_count == 2
    expected_calls = [
        call(
            ["terraform", "plan", "-out=tfplan"],
            cwd=str(orchestrator.terraform_dir),
            capture_output=True,
            text=True,
            timeout=300,
        ),
        call(
            ["terraform", "apply", "-auto-approve", "tfplan"],
            cwd=str(orchestrator.terraform_dir),
            capture_output=True,
            text=True,
            timeout=1800,
        ),
    ]
    mock_run.assert_has_calls(expected_calls)


@patch("subprocess.run")
def test_deploy_terraform_stack_timeout_handling(mock_run, orchestrator):
    """Test handling of terraform command timeouts."""
    mock_run.side_effect = subprocess.TimeoutExpired("terraform", 300)

    result = orchestrator._deploy_terraform_stack(
        "data-stack", orchestrator.data_stack_dir
    )

    assert result is False
    # Verify plan was attempted
    mock_run.assert_called_once()


@patch("subprocess.run")
def test_deploy_terraform_stack_working_directory_verification(
    mock_run, orchestrator, mock_subprocess_success
):
    """Test that correct working directory is used for terraform commands."""
    mock_run.return_value = mock_subprocess_success

    # Test with data-stack directory
    orchestrator._deploy_terraform_stack("data-stack", orchestrator.data_stack_dir)

    # Verify all calls used the correct working directory
    for call_args in mock_run.call_args_list:
        assert call_args.kwargs["cwd"] == str(orchestrator.data_stack_dir)

    mock_run.reset_mock()

    # Test with app-stack directory
    orchestrator._deploy_terraform_stack("app-stack", orchestrator.terraform_dir)

    # Verify all calls used the correct working directory
    for call_args in mock_run.call_args_list:
        assert call_args.kwargs["cwd"] == str(orchestrator.terraform_dir)


@patch("subprocess.run")
def test_deploy_terraform_stack_exception_handling(mock_run, orchestrator):
    """Test handling of unexpected exceptions during deployment."""
    mock_run.side_effect = Exception("Unexpected error")

    result = orchestrator._deploy_terraform_stack(
        "data-stack", orchestrator.data_stack_dir
    )

    assert result is False
    mock_run.assert_called_once()


# Additional tests for dual-stack deployment in run method
@patch.object(DeploymentOrchestrator, "_deploy_terraform_stack")
@patch.object(DeploymentOrchestrator, "_generate_terraform_vars", return_value=True)
@patch.object(DeploymentOrchestrator, "validate_prerequisites", return_value=True)
@patch.object(DeploymentOrchestrator, "build_lambda_functions", return_value=True)
@patch.object(DeploymentOrchestrator, "validate_lambda_zip_files", return_value=True)
@patch.object(
    DeploymentOrchestrator, "_create_terraform_state_bucket", return_value=True
)
@patch.object(DeploymentOrchestrator, "_create_terraform_lock_table", return_value=True)
@patch.object(
    DeploymentOrchestrator, "_update_app_stack_data_bucket_reference", return_value=True
)
def test_run_method_dual_stack_call_order_verification(
    mock_update_ref,
    mock_create_lock_table,
    mock_create_bucket,
    mock_validate_zip,
    mock_build_lambda,
    mock_validate_prereq,
    mock_generate_vars,
    mock_deploy_stack,
    orchestrator,
):
    """Test that run method calls _deploy_terraform_stack in correct order with proper arguments."""
    # Mock successful deployment for both stacks
    mock_deploy_stack.return_value = True

    result = orchestrator.run()

    assert result is True
    # Verify call order using mock.call_args_list
    call_args_list = mock_deploy_stack.call_args_list
    assert len(call_args_list) == 2

    # First call should be data-stack
    first_call = call_args_list[0]
    assert first_call == call("data-stack", orchestrator.data_stack_dir)

    # Second call should be app-stack
    second_call = call_args_list[1]
    assert second_call == call("app-stack", orchestrator.terraform_dir)


@patch.object(DeploymentOrchestrator, "_deploy_terraform_stack")
@patch.object(DeploymentOrchestrator, "_generate_terraform_vars", return_value=True)
@patch.object(DeploymentOrchestrator, "validate_prerequisites", return_value=True)
@patch.object(DeploymentOrchestrator, "build_lambda_functions", return_value=True)
@patch.object(DeploymentOrchestrator, "validate_lambda_zip_files", return_value=True)
@patch.object(
    DeploymentOrchestrator, "_create_terraform_state_bucket", return_value=True
)
@patch.object(DeploymentOrchestrator, "_create_terraform_lock_table", return_value=True)
def test_run_method_data_stack_failure_prevents_app_stack_deployment(
    mock_create_lock_table,
    mock_create_bucket,
    mock_validate_zip,
    mock_build_lambda,
    mock_validate_prereq,
    mock_generate_vars,
    mock_deploy_stack,
    orchestrator,
):
    """Test that data-stack failure stops deployment and prevents app-stack deployment using side_effect."""
    # Use side_effect to simulate data-stack failure
    mock_deploy_stack.side_effect = [False]  # First call (data-stack) fails

    result = orchestrator.run()

    assert result is False
    # Verify only one call was made (data-stack)
    assert mock_deploy_stack.call_count == 1
    call_args_list = mock_deploy_stack.call_args_list
    assert len(call_args_list) == 1
    assert call_args_list[0] == call("data-stack", orchestrator.data_stack_dir)


@patch.object(DeploymentOrchestrator, "_deploy_terraform_stack")
@patch.object(DeploymentOrchestrator, "_generate_terraform_vars", return_value=True)
@patch.object(DeploymentOrchestrator, "validate_prerequisites", return_value=True)
@patch.object(DeploymentOrchestrator, "build_lambda_functions", return_value=True)
@patch.object(DeploymentOrchestrator, "validate_lambda_zip_files", return_value=True)
@patch.object(
    DeploymentOrchestrator, "_create_terraform_state_bucket", return_value=True
)
@patch.object(DeploymentOrchestrator, "_create_terraform_lock_table", return_value=True)
@patch.object(
    DeploymentOrchestrator, "_update_app_stack_data_bucket_reference", return_value=True
)
def test_run_method_app_stack_failure_after_data_stack_success_verification(
    mock_update_ref,
    mock_create_lock_table,
    mock_create_bucket,
    mock_validate_zip,
    mock_build_lambda,
    mock_validate_prereq,
    mock_generate_vars,
    mock_deploy_stack,
    orchestrator,
):
    """Test app-stack failure after successful data-stack deployment with call verification."""
    # Use side_effect to simulate data-stack success, app-stack failure
    mock_deploy_stack.side_effect = [True, False]  # First call succeeds, second fails

    result = orchestrator.run()

    assert result is False
    # Verify both calls were made in correct order
    assert mock_deploy_stack.call_count == 2
    call_args_list = mock_deploy_stack.call_args_list
    assert len(call_args_list) == 2

    # Verify call order and arguments using assert patterns
    assert call_args_list[0] == call("data-stack", orchestrator.data_stack_dir)
    assert call_args_list[1] == call("app-stack", orchestrator.terraform_dir)


# Integration test for complete dual-stack deployment workflow
@patch("subprocess.run")
@patch("pathlib.Path.exists", return_value=True)
@patch.object(DeploymentOrchestrator, "_deploy_terraform_stack", return_value=True)
@patch.object(
    DeploymentOrchestrator, "_update_app_stack_data_bucket_reference", return_value=True
)
def test_complete_dual_stack_deployment_workflow(
    mock_update_ref, mock_deploy_stack, mock_exists, mock_run, orchestrator
):
    """Test complete dual-stack deployment workflow with mocking."""
    # Mock successful subprocess.run for all terraform commands
    mock_run.return_value = MagicMock(returncode=0, stdout="Success", stderr="")

    # Mock all prerequisite methods using patch.object
    with patch.object(
        orchestrator, "validate_prerequisites", return_value=True
    ) as mock_validate_prereq:
        with patch.object(
            orchestrator, "build_lambda_functions", return_value=True
        ) as mock_build_lambda:
            with patch.object(
                orchestrator, "validate_lambda_zip_files", return_value=True
            ) as mock_validate_zip:
                with patch.object(
                    orchestrator, "_create_terraform_state_bucket", return_value=True
                ) as mock_create_bucket:
                    with patch.object(
                        orchestrator, "_create_terraform_lock_table", return_value=True
                    ) as mock_create_lock_table:
                        with patch.object(
                            orchestrator, "_generate_terraform_vars", return_value=True
                        ) as mock_generate_vars:
                            # Execute the full run() method
                            result = orchestrator.run()

    # Verify overall success
    assert result is True

    # Verify all prerequisite methods were called
    mock_validate_prereq.assert_called_once()
    mock_build_lambda.assert_called_once()
    mock_validate_zip.assert_called_once()
    mock_create_bucket.assert_called_once()
    mock_create_lock_table.assert_called_once()

    # Verify _generate_terraform_vars was called for both stacks
    assert mock_generate_vars.call_count == 2
    expected_generate_calls = [
        call(orchestrator.data_stack_dir),
        call(orchestrator.terraform_dir),
    ]
    mock_generate_vars.assert_has_calls(expected_generate_calls, any_order=False)

    # Verify both stacks were deployed
    assert mock_deploy_stack.call_count == 2
    expected_deploy_calls = [
        call("data-stack", orchestrator.data_stack_dir),
        call("app-stack", orchestrator.terraform_dir),
    ]
    mock_deploy_stack.assert_has_calls(expected_deploy_calls, any_order=False)

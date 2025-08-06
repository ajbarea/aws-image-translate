#!/usr/bin/env python3
"""
Lenslate Automated Deployment Script

This script serves as the entry point for the deployment process.
It initializes and runs the main deployment orchestrator.
"""

import argparse
import os
import subprocess
import sys

from deployment_logic.deployment_orchestrator import DeploymentOrchestrator
from deployment_logic.progress_indicator import Colors


def _offer_full_cleanup(ci_mode):
    """
    Offer to run full_cleanup.py after successful destroy operation.
    """
    if ci_mode:
        # In CI mode, don't prompt for additional cleanup
        return

    print(f"\n{Colors.OKGREEN}Infrastructure destroyed successfully!{Colors.ENDC}")
    print(f"\n{Colors.WARNING}Additional Cleanup Available:{Colors.ENDC}")
    print(
        "The destroy operation removed Terraform-managed resources, but there may be:"
    )
    print("  • Remaining AWS resources not managed by Terraform")
    print("  • Local Terraform state files and build artifacts")
    print("  • CloudWatch log groups, S3 bucket contents, etc.")
    print()
    print("You can run the full cleanup script to remove ALL remaining resources.")
    print(
        f"{Colors.WARNING}WARNING: This will delete EVERYTHING and cannot be undone!{Colors.ENDC}"
    )

    try:
        response = (
            input("\nWould you like to run full cleanup now? (y/N): ").strip().lower()
        )

        if response in ["y", "Y", "yes"]:
            print(f"\n{Colors.OKBLUE}Starting full cleanup...{Colors.ENDC}")

            # Check if full_cleanup.py exists
            if not os.path.exists("full_cleanup.py"):
                print(
                    f"{Colors.FAIL}Error: full_cleanup.py not found in current directory.{Colors.ENDC}"
                )
                return

            try:
                # Run full_cleanup.py
                result = subprocess.run(
                    [sys.executable, "full_cleanup.py"], check=False, text=True
                )

                if result.returncode == 0:
                    print(
                        f"\n{Colors.OKGREEN}Full cleanup completed successfully!{Colors.ENDC}"
                    )
                else:
                    print(
                        f"\n{Colors.WARNING}Full cleanup completed with some issues. Check the output above.{Colors.ENDC}"
                    )

            except subprocess.SubprocessError as e:
                print(f"{Colors.FAIL}Error running full cleanup: {e}{Colors.ENDC}")
            except KeyboardInterrupt:
                print(f"\n{Colors.WARNING}Full cleanup cancelled by user.{Colors.ENDC}")
        else:
            print(f"\n{Colors.OKBLUE}Skipping full cleanup.{Colors.ENDC}")
            print("You can run it manually later with: python full_cleanup.py")

    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}Cleanup prompt cancelled by user.{Colors.ENDC}")


def main():
    """
    Main function to parse arguments and run the deployment.
    """
    parser = argparse.ArgumentParser(
        description="Lenslate Automated Deployment Script",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--ci-mode",
        action="store_true",
        help="Run in non-interactive CI/CD mode.",
    )
    parser.add_argument(
        "--destroy",
        action="store_true",
        help="Destroy all deployed resources.",
    )
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Automatically approve Terraform apply (used in CI mode).",
    )
    parser.add_argument(
        "--force-unlock",
        action="store_true",
        help="Force bypass Terraform state locks using -lock=false (use with caution). "
        "Only use this option if you're certain no other Terraform processes are running.",
    )

    args = parser.parse_args()

    try:
        orchestrator = DeploymentOrchestrator(
            ci_mode=args.ci_mode, force_unlock=args.force_unlock
        )

        if args.destroy:
            if not orchestrator.destroy_infrastructure(auto_approve=args.auto_approve):
                sys.exit(1)

            # After successful destroy, offer to run full cleanup
            _offer_full_cleanup(args.ci_mode)
        else:
            if not orchestrator.run():
                sys.exit(1)

    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}Operation cancelled by user.{Colors.ENDC}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.FAIL}An unexpected error occurred: {e}{Colors.ENDC}")
        sys.exit(1)


if __name__ == "__main__":
    main()

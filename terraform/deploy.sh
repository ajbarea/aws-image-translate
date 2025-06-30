#!/bin/bash
# Simplified Terraform deployment script for AWS Image Translation Pipeline

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ACTION=""
TERRAFORM_DIR="terraform"
TERRAFORM_CMD="C:/terraform/terraform.exe"
AWS_CMD="C:/Program Files/Amazon/AWSCLIV2/aws.exe"

# Functions
print_usage() {
    echo "Usage: $0 ACTION"
    echo ""
    echo "Actions:"
    echo "  init      Initialize Terraform"
    echo "  plan      Plan infrastructure changes"
    echo "  apply     Apply infrastructure changes"
    echo "  destroy   Destroy all infrastructure"
    echo "  output    Show Terraform outputs"
    echo ""
    echo "Examples:"
    echo "  $0 init                 # Initialize Terraform"
    echo "  $0 plan                 # Plan changes"
    echo "  $0 apply                # Apply changes"
    echo "  $0 destroy              # Destroy infrastructure"
}

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_requirements() {
    # Check if terraform is installed
    if ! "$TERRAFORM_CMD" version &> /dev/null; then
        log_error "Terraform is not found at $TERRAFORM_CMD"
        exit 1
    else
        log_success "Terraform found: $($TERRAFORM_CMD version | head -n1)"
    fi

    # Check if AWS CLI is configured
    if ! "$AWS_CMD" sts get-caller-identity &> /dev/null; then
        log_error "AWS CLI is not configured. Run 'aws configure' first."
        exit 1
    else
        log_success "AWS CLI is configured and working"
    fi

    # Check if terraform directory exists
    if [ ! -d "$TERRAFORM_DIR" ]; then
        log_error "Terraform directory not found: $TERRAFORM_DIR"
        exit 1
    fi

    # Check if terraform.tfvars exists
    if [ ! -f "$TERRAFORM_DIR/terraform.tfvars" ]; then
        log_warning "terraform.tfvars not found. Make sure to create it and set your values."
    fi
}

init_terraform() {
    log_info "Initializing Terraform..."
    cd "$TERRAFORM_DIR"
    "$TERRAFORM_CMD" init
    log_success "Terraform initialized successfully"
}

plan_terraform() {
    log_info "Planning Terraform changes..."
    cd "$TERRAFORM_DIR"
    "$TERRAFORM_CMD" plan
}

apply_terraform() {
    log_info "Applying Terraform changes..."
    cd "$TERRAFORM_DIR"
    "$TERRAFORM_CMD" apply

    if [ $? -eq 0 ]; then
        log_success "Infrastructure deployed successfully!"
        log_info "Run '$0 output' to see the resource details."
    fi
}

destroy_terraform() {
    log_warning "This will destroy ALL infrastructure!"
    read -p "Are you sure you want to continue? (type 'yes' to confirm): " confirm

    if [ "$confirm" != "yes" ]; then
        log_info "Deployment cancelled."
        exit 0
    fi

    log_info "Destroying Terraform infrastructure..."
    cd "$TERRAFORM_DIR"
    "$TERRAFORM_CMD" destroy

    if [ $? -eq 0 ]; then
        log_success "Infrastructure destroyed successfully!"
    fi
}

show_outputs() {
    log_info "Terraform outputs:"
    cd "$TERRAFORM_DIR"
    "$TERRAFORM_CMD" output
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        init|plan|apply|destroy|output)
            ACTION="$1"
            shift
            ;;
        -h|--help)
            print_usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            print_usage
            exit 1
            ;;
    esac
done

# Validate action
if [ -z "$ACTION" ]; then
    log_error "No action specified."
    print_usage
    exit 1
fi

# Main execution
log_info "AWS Image Translation Pipeline - Terraform Script"
log_info "Action: $ACTION"

# Check requirements for all actions except init
if [ "$ACTION" != "init" ]; then
    check_requirements
fi

case $ACTION in
    init)
        init_terraform
        ;;
    plan)
        plan_terraform
        ;;
    apply)
        apply_terraform
        ;;
    destroy)
        destroy_terraform
        ;;
    output)
        show_outputs
        ;;
esac

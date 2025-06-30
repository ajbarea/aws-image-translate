#!/bin/bash
# Python Virtual Environment Setup Script for AWS Image Translation Pipeline

set -e  # Exit on any error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

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

print_usage() {
    echo "Python Virtual Environment Setup Script"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --dev         Install development dependencies (default)"
    echo "  --prod        Install production dependencies only"
    echo "  --clean       Remove existing virtual environment first"
    echo "  --help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                    # Setup with dev dependencies"
    echo "  $0 --prod             # Setup with production dependencies only"
    echo "  $0 --clean --dev      # Clean setup with dev dependencies"
}

# Default values
INSTALL_DEV=true
CLEAN_VENV=false
VENV_DIR=".venv"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dev)
            INSTALL_DEV=true
            shift
            ;;
        --prod)
            INSTALL_DEV=false
            shift
            ;;
        --clean)
            CLEAN_VENV=true
            shift
            ;;
        --help|-h)
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

# Check if Python is available
if ! command -v python &> /dev/null; then
    log_error "Python is not installed or not in PATH"
    exit 1
fi

# Get Python version
PYTHON_VERSION=$(python --version 2>&1 | cut -d' ' -f2)
log_info "Using Python $PYTHON_VERSION"

# Clean existing virtual environment if requested
if [ "$CLEAN_VENV" = true ] && [ -d "$VENV_DIR" ]; then
    log_warning "Removing existing virtual environment..."
    rm -rf "$VENV_DIR"
fi

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    log_info "Creating virtual environment..."
    python -m venv "$VENV_DIR"
    log_success "Virtual environment created successfully"
else
    log_info "Virtual environment already exists"
fi

# Determine activation script based on OS
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" || "$OSTYPE" == "cygwin" ]]; then
    ACTIVATE_SCRIPT="$VENV_DIR/Scripts/activate"
else
    ACTIVATE_SCRIPT="$VENV_DIR/bin/activate"
fi

# Check if activation script exists
if [ ! -f "$ACTIVATE_SCRIPT" ]; then
    log_error "Virtual environment activation script not found: $ACTIVATE_SCRIPT"
    exit 1
fi

# Activate virtual environment and install dependencies
log_info "Activating virtual environment and installing dependencies..."

# Source the activation script
source "$ACTIVATE_SCRIPT"

# Upgrade pip
log_info "Upgrading pip..."
python -m pip install --upgrade pip

# Install dependencies
if [ "$INSTALL_DEV" = true ]; then
    if [ -f "requirements-dev.txt" ]; then
        log_info "Installing development dependencies..."
        pip install -r requirements-dev.txt
        log_success "Development dependencies installed successfully"
    else
        log_warning "requirements-dev.txt not found, installing base requirements only"
        if [ -f "requirements.txt" ]; then
            pip install -r requirements.txt
        else
            log_error "No requirements files found"
            exit 1
        fi
    fi
else
    if [ -f "requirements.txt" ]; then
        log_info "Installing production dependencies..."
        pip install -r requirements.txt
        log_success "Production dependencies installed successfully"
    else
        log_error "requirements.txt not found"
        exit 1
    fi
fi

log_success "Environment setup complete!"
log_info "To activate the virtual environment in the future, run:"
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" || "$OSTYPE" == "cygwin" ]]; then
    echo "  source .venv/Scripts/activate"
else
    echo "  source .venv/bin/activate"
fi

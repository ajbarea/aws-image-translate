#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Run all pre-commit hooks manually
echo "--- Running all pre-commit hooks 🔍 ---"
export HOME="$(cygpath -u "$USERPROFILE")"
pre-commit run --all-files

echo "--- ✅ All checks passed! ---"

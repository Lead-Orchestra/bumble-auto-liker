#!/bin/bash
# Setup script for Bumble auto-liker Python environment using uv

set -e

echo "Setting up Bumble auto-liker Python environment with uv..."

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "Error: uv is not installed."
    echo "Please install uv first:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "  # or"
    echo "  pip install uv"
    exit 1
fi

echo "Found uv: $(uv --version)"

# Create virtual environment
echo "Creating virtual environment..."
uv venv

# Determine Python executable path
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    PYTHON_EXE=".venv/Scripts/python.exe"
else
    PYTHON_EXE=".venv/bin/python"
fi

# Install dependencies
echo "Installing dependencies..."
uv pip install selenium undetected-chromedriver webdriver-manager Pillow beautifulsoup4 lxml

# Install playwright browsers (optional but recommended)
echo "Installing Playwright browsers..."
$PYTHON_EXE -m playwright install chromium 2>/dev/null || echo "Note: Playwright installation skipped (optional)"

echo ""
echo "✅ Setup complete!"
echo "To activate the virtual environment:"
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    echo "  source .venv/Scripts/activate"
else
    echo "  source .venv/bin/activate"
fi


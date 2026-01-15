# Setup script for Bumble auto-liker Python environment using uv (Windows PowerShell)

$ErrorActionPreference = "Stop"

Write-Host "Setting up Bumble auto-liker Python environment with uv..." -ForegroundColor Cyan

# Check if uv is installed
try {
    $uvVersion = uv --version 2>&1
    Write-Host "Found uv: $uvVersion" -ForegroundColor Green
} catch {
    Write-Host "Error: uv is not installed." -ForegroundColor Red
    Write-Host "Please install uv first:" -ForegroundColor Yellow
    Write-Host "  pip install uv" -ForegroundColor Yellow
    Write-Host "  # or visit: https://github.com/astral-sh/uv" -ForegroundColor Yellow
    exit 1
}

# Create virtual environment
Write-Host "Creating virtual environment..." -ForegroundColor Cyan
uv venv

# Install dependencies
Write-Host "Installing dependencies..." -ForegroundColor Cyan
uv pip install selenium undetected-chromedriver webdriver-manager Pillow beautifulsoup4 lxml

# Install playwright browsers (optional but recommended)
Write-Host "Installing Playwright browsers..." -ForegroundColor Cyan
try {
    .venv\Scripts\python.exe -m playwright install chromium 2>&1 | Out-Null
} catch {
    Write-Host "Note: Playwright installation skipped (optional)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "✅ Setup complete!" -ForegroundColor Green
Write-Host "To activate the virtual environment:" -ForegroundColor Cyan
Write-Host "  .venv\Scripts\Activate.ps1" -ForegroundColor Yellow



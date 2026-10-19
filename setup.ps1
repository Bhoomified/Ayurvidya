# One-time setup on Windows (PowerShell). Run from the project folder:  .\setup.ps1
# If scripts are blocked:  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
$ErrorActionPreference = "Stop"
if (-not (Test-Path .venv)) { python -m venv .venv }
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-core.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests
Write-Host "`nSetup OK. Activate the environment with:  .\.venv\Scripts\Activate.ps1"

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
python -B backend\server.py 8000

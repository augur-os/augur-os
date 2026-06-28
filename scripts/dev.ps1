$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
uv run aug dev build @args

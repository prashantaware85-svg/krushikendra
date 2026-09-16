#Requires -Version 5.1
<#
.SYNOPSIS
  Start Krushi Seva backend + frontend for local development (Step 1).
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

Write-Host "Starting backend (FastAPI) ..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$Root\backend'; if (Test-Path '.venv\Scripts\Activate.ps1') { .\.venv\Scripts\Activate.ps1 }; uvicorn app.main:app --reload"

Write-Host "Starting frontend (Next.js) ..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$Root\apps\web'; npm run dev"

Write-Host "Backend: http://localhost:8000/health | Frontend: http://localhost:3000" -ForegroundColor Cyan

# Start Development Environment for dEFEND Project

$scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Get-Location }
$backendPath = Join-Path $scriptDir "backend"
$frontendPath = Join-Path $scriptDir "frontend"
$pythonExe = "c:\Users\soura\Desktop\Fake-News-Detection-System-main\backend\venv310\Scripts\python.exe"

Write-Host "🚀 Starting dEFEND Backend Server on Port 5001..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$backendPath'; & '$pythonExe' app.py"

Start-Sleep -Seconds 4

Write-Host "🎨 Starting dEFEND Frontend Server on Port 3001..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$frontendPath'; npm run dev"

Write-Host "✅ dEFEND System Ready!" -ForegroundColor Green
Write-Host "   Backend API: http://localhost:5001/api/health" -ForegroundColor White
Write-Host "   Frontend UI: http://localhost:3001" -ForegroundColor White

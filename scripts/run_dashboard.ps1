param([int]$Port = 8767)
$projectPath = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectPath '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { $pythonPath = 'python' }
Set-Location -LiteralPath $projectPath
& $pythonPath -m uvicorn app:app --app-dir pose_focus_demo --host 127.0.0.1 --port $Port

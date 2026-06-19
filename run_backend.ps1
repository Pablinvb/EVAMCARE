$ErrorActionPreference = "Stop"

$workspace = $PSScriptRoot
Set-Location -LiteralPath $workspace

$systemPython = Get-Command python -ErrorAction SilentlyContinue
$bundledPython = "C:\Users\Usuario\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$python = if ($systemPython) {
    $systemPython.Source
} elseif (Test-Path -LiteralPath $bundledPython) {
    $bundledPython
} else {
    throw "Python no está instalado o disponible en PATH."
}

& $python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

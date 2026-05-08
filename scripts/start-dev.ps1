param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$PowerShell = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$WindowsTerminal = Get-Command wt.exe -ErrorAction SilentlyContinue

function Quote-Arg {
    param([string]$Value)

    '"' + $Value.Replace('"', '\"') + '"'
}

function New-TabCommand {
    param(
        [string]$Name,
        [string]$WorkingDirectory,
        [string]$ScriptPath
    )

    "new-tab --title $(Quote-Arg $Name) -d $(Quote-Arg $WorkingDirectory) $(Quote-Arg $PowerShell) -NoProfile -NoExit -ExecutionPolicy Bypass -File $(Quote-Arg $ScriptPath)"
}

function New-ServiceScript {
    param(
        [string]$Name,
        [string]$WorkingDirectory,
        [string]$Command
    )

    $scriptPath = Join-Path $env:TEMP "ai-services-$Name.ps1"
    $escapedPath = $WorkingDirectory.Replace("'", "''")
    $content = @"
`$Host.UI.RawUI.WindowTitle = '$Name'
Set-Location -LiteralPath '$escapedPath'
$Command
"@

    Set-Content -LiteralPath $scriptPath -Value $content -Encoding UTF8
    $scriptPath
}

function Start-DevWindow {
    param(
        [string]$Name,
        [string]$WorkingDirectory,
        [string]$Command
    )

    $escapedPath = $WorkingDirectory.Replace("'", "''")
    $escapedName = $Name.Replace("'", "''")
    $windowCommand = @"
`$Host.UI.RawUI.WindowTitle = '$escapedName'
Set-Location -LiteralPath '$escapedPath'
$Command
"@

    Start-Process -FilePath $PowerShell -ArgumentList @(
        "-NoProfile",
        "-NoExit",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        $windowCommand
    )
}

$agentInstall = if ($SkipInstall) {
    ""
} else {
    "if (-not (Test-Path '.venv')) { uv sync --dev }"
}

$nodeInstall = if ($SkipInstall) {
    ""
} else {
    "if (-not (Test-Path 'node_modules')) { npm install }"
}

$agentDir = Join-Path $Root "agent-service"
$gatewayDir = Join-Path $Root "api-gateway"
$frontendDir = Join-Path $Root "frontend"

$agentCommand = @"
`$env:UV_CACHE_DIR = '.uv-cache'
$agentInstall
uv run uvicorn app.main:app --reload --port 8000
"@

$gatewayCommand = @"
$nodeInstall
npm run dev
"@

$frontendCommand = @"
$nodeInstall
npm run dev
"@

if ($WindowsTerminal) {
    $agentScript = New-ServiceScript -Name "agent-service" -WorkingDirectory $agentDir -Command $agentCommand
    $gatewayScript = New-ServiceScript -Name "api-gateway" -WorkingDirectory $gatewayDir -Command $gatewayCommand
    $frontendScript = New-ServiceScript -Name "frontend" -WorkingDirectory $frontendDir -Command $frontendCommand

    $wtCommand = @(
        New-TabCommand -Name "Agent Service :8000" -WorkingDirectory $agentDir -ScriptPath $agentScript
        New-TabCommand -Name "API Gateway :3000" -WorkingDirectory $gatewayDir -ScriptPath $gatewayScript
        New-TabCommand -Name "Frontend :5173" -WorkingDirectory $frontendDir -ScriptPath $frontendScript
    ) -join " ; "

    Start-Process -FilePath $WindowsTerminal.Source -ArgumentList $wtCommand
    Write-Host "Started development services in one Windows Terminal window with three PowerShell tabs."
} else {
    Start-DevWindow `
        -Name "AI Services - Agent Service :8000" `
        -WorkingDirectory $agentDir `
        -Command $agentCommand

    Start-DevWindow `
        -Name "AI Services - API Gateway :3000" `
        -WorkingDirectory $gatewayDir `
        -Command $gatewayCommand

    Start-DevWindow `
        -Name "AI Services - Frontend :5173" `
        -WorkingDirectory $frontendDir `
        -Command $frontendCommand

    Write-Host "Windows Terminal was not found. Started development services in separate PowerShell windows."
}

Write-Host "Agent Service: http://localhost:8000"
Write-Host "API Gateway:   http://localhost:3000"
Write-Host "Frontend:      http://localhost:5173"

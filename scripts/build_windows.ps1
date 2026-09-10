param(
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

python -m pip install -r requirements.txt
pyinstaller --noconfirm cycloid_motion_analyzer.spec

if (-not $SkipInstaller) {
    $iscc = Get-Command ISCC -ErrorAction SilentlyContinue
    if ($iscc) {
        & $iscc.Path installer.iss
    } else {
        Write-Host "Inno Setup compiler (ISCC) not found. Install Inno Setup to build the installer."
    }
}


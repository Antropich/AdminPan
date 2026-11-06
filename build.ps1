$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $root "AdminPanel")
dotnet restore
dotnet publish -c Release -r win-x64 --self-contained false -o (Join-Path $root "publish")
Write-Host "Готово: папка publish. Для создания Setup.exe открой Installer\AdminPanel.iss в Inno Setup Compiler."

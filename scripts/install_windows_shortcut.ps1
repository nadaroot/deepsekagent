# PowerShell script to install NonRoot shortcut and PATH on Windows
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BaseDir = (Resolve-Path "$ScriptDir\..").Path
$AssetsDir = Join-Path $BaseDir "assets"
$IconPath = Join-Path $AssetsDir "app.ico"
$TargetExe = Join-Path $BaseDir "nonroot.py"

# Create NonRoot CLI batch wrapper
$BinDir = Join-Path $env:LOCALAPPDATA "NonRoot\bin"
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
$BatWrapper = Join-Path $BinDir "nonroot.bat"
"@echo off`npython `"$TargetExe`" %*" | Out-File -FilePath $BatWrapper -Encoding ascii

# Add to User PATH if not present
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -notlike "*$BinDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$UserPath;$BinDir", "User")
    Write-Host "[+] Added $BinDir to User PATH"
}

# Create Desktop Shortcut
$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $DesktopPath "NonRoot AI.lnk"
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "python.exe"
$Shortcut.Arguments = "`"$TargetExe`""
$Shortcut.WorkingDirectory = $BaseDir
if (Test-Path $IconPath) {
    $Shortcut.IconLocation = $IconPath
}
$Shortcut.Description = "NonRoot - Autonomous AI Agent"
$Shortcut.Save()

Write-Host "[+] Desktop Shortcut created: $ShortcutPath"
Write-Host "[+] You can now run 'nonroot' from any Windows command prompt or terminal!"

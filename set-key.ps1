$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$EnvPath = Join-Path $Root ".env"

$SecureKey = Read-Host "Paste your Pexels API key" -AsSecureString
$Ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureKey)

try {
    $ApiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Ptr)
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Ptr)
}

if ([string]::IsNullOrWhiteSpace($ApiKey)) {
    throw "No API key entered."
}

$ExistingLines = @()
if (Test-Path $EnvPath) {
    $ExistingLines = Get-Content -Path $EnvPath | Where-Object {
        $_ -notmatch '^\s*PEXELS_API_KEY\s*='
    }
}

$NewLines = @($ExistingLines + "PEXELS_API_KEY=$ApiKey")
$NewLines | Set-Content -Path $EnvPath -Encoding ASCII

Write-Host "Saved API key to $EnvPath"
Write-Host "This file is ignored by .gitignore."

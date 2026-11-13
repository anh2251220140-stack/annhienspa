param(
    [ValidateSet('admin', 'user')]
    [string]$CopyPassword
)

$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
$directory = Join-Path $project '.tmp-review-8002'
$database = Join-Path $directory 'reviews.sqlite3'
$credentials = Join-Path $directory 'credentials.dpapi'
if (Test-Path -LiteralPath $directory) {
    if ((Get-Item -LiteralPath $directory -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw 'The local 8002 directory must not be a link.'
    }
} else {
    $null = New-Item -ItemType Directory -Path $directory
}
if (Test-Path -LiteralPath $credentials) {
    if ((Get-Item -LiteralPath $credentials -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw 'The local 8002 credential file must not be a link.'
    }
}
if ($CopyPassword) {
    if (!(Test-Path -LiteralPath $credentials) -or !(Test-Path -LiteralPath $database)) {
        throw 'Start the 8002 site once before copying a password.'
    }
    $secret = ConvertTo-SecureString (Get-Content -LiteralPath $credentials -Raw).Trim()
    $values = [Net.NetworkCredential]::new('', $secret).Password | ConvertFrom-Json
    Set-Clipboard -Value $values.$CopyPassword
    return
}
$python = Join-Path $project '.venv\Scripts\python.exe'
$launcher = Join-Path $PSScriptRoot 'review_chrome_8002.py'
$env:PYTHONIOENCODING = 'utf-8'
if (Test-Path -LiteralPath $database) {
    & $python -B $launcher serve
    exit $LASTEXITCODE
}
if (Test-Path -LiteralPath $credentials) {
    $secret = ConvertTo-SecureString (Get-Content -LiteralPath $credentials -Raw).Trim()
    $json = [Net.NetworkCredential]::new('', $secret).Password
} else {
    function New-ReviewPassword {
        $bytes = [byte[]]::new(24)
        $random = [Security.Cryptography.RandomNumberGenerator]::Create()
        try { $random.GetBytes($bytes) } finally { $random.Dispose() }
        [Convert]::ToBase64String($bytes)
    }
    $json = @{ admin = (New-ReviewPassword); user = (New-ReviewPassword) } | ConvertTo-Json -Compress
    $json | ConvertTo-SecureString -AsPlainText -Force | ConvertFrom-SecureString |
        Out-File -LiteralPath $credentials -Encoding ascii -NoClobber
}
$json | & $python -B $launcher initialize
exit $LASTEXITCODE

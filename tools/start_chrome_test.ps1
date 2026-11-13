$ErrorActionPreference = 'Stop'
$testRoot = 'D:\AnNhienSpa-MySQL-Test'
$uuidFile = Join-Path $testRoot 'Data\auto.cnf'
$credential = Join-Path $testRoot 'chrome-db-password.dpapi'
$media = Join-Path $testRoot 'chrome-media'
foreach ($path in @($testRoot, (Join-Path $testRoot 'Data'), $uuidFile, $credential, $media)) {
    if ((Get-Item -LiteralPath $path -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw 'Unexpected link in the Chrome test paths.'
    }
}
$expectedUuid = '47c73b62-df2c-11f1-b343-df6f8d76a6e0'
if ((Get-Content -LiteralPath $uuidFile -Raw) -notmatch "(?m)^server-uuid=$expectedUuid\s*$") {
    throw 'Unexpected MySQL test UUID.'
}
$secret = ConvertTo-SecureString (Get-Content -LiteralPath $credential -Raw).Trim()
$env:ANNHIEN_CHROME_MEDIA_ROOT = $media
$env:ANNHIEN_CHROME_DB_PASSWORD = [Net.NetworkCredential]::new('', $secret).Password
$project = Split-Path -Parent $PSScriptRoot
try {
    Push-Location -LiteralPath $project
    try {
        & '.\.venv\Scripts\python.exe' -B 'tools\chrome_test.py' serve
        exit $LASTEXITCODE
    } finally {
        Pop-Location
    }
} finally {
    Remove-Item Env:ANNHIEN_CHROME_DB_PASSWORD -ErrorAction SilentlyContinue
    Remove-Item Env:ANNHIEN_CHROME_MEDIA_ROOT -ErrorAction SilentlyContinue
}

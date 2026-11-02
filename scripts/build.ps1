$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    python -m venv .venv
}

$Python = ".venv\Scripts\python.exe"
& $Python -m pip install --upgrade pip
& $Python -m pip install -e ".[dev]"

if (-not (Test-Path "assets\app.ico")) {
    & $Python scripts\make_icon.py
}

# Directory build is intentional: one-file extraction needs a writable %TEMP%
# and fails for some non-admin Windows profiles.
& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --windowed `
    --name QwenSubtitle `
    --distpath "$Root\dist\portable" `
    --workpath "$Root\build\portable" `
    --icon "$Root\assets\app.ico" `
    --version-file "$Root\assets\version_info.txt" `
    --paths "src" `
    --add-data "$Root\src\qwen_subtitle\resources;qwen_subtitle\resources" `
    --collect-all imageio_ffmpeg `
    run.py

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

$PortableDir = Join-Path $Root "dist\portable\QwenSubtitle"
$Exe = Join-Path $PortableDir "QwenSubtitle.exe"
if (-not (Test-Path $Exe)) {
    throw "Expected $Exe was not produced"
}

Write-Host "Built: $Exe"
# Use the normal system TEMP here: the portable directory build must not need
# a custom temp location to start.
Remove-Item Env:TEMP -ErrorAction SilentlyContinue
Remove-Item Env:TMP -ErrorAction SilentlyContinue
$env:QT_QPA_PLATFORM = "offscreen"
$env:QT_QPA_FONTDIR = "C:\Windows\Fonts"
$SelfTestLog = Join-Path $Root "dist\self-test-error.txt"
Remove-Item $SelfTestLog -Force -ErrorAction SilentlyContinue
$env:QWEN_SUBTITLE_SELF_TEST_LOG = $SelfTestLog
$process = Start-Process -FilePath $Exe -ArgumentList "--self-test" -PassThru -Wait
if ($process.ExitCode -ne 0) {
    if (Test-Path $SelfTestLog) {
        Get-Content $SelfTestLog -Tail 40
    }
    throw "Packaged application self-test failed with exit code $($process.ExitCode)"
}
Write-Host "Packaged self-test: ok"
# The self-test may create portable-data on restricted hosts; never ship logs.
$PortableData = Join-Path $PortableDir "portable-data"
Remove-Item $PortableData -Recurse -Force -ErrorAction SilentlyContinue

$Readme = @(
    'Qwen Subtitle 0.1.0',
    '',
    '1. Double-click QwenSubtitle.exe.',
    '2. Keep the _internal folder in the same directory as QwenSubtitle.exe.',
    '   Do not copy the EXE by itself.',
    '3. Enter your own API key on the Settings page.',
    '4. Python and FFmpeg are not required. Administrator rights are not required.',
    '5. If SmartScreen warns about an unknown publisher, verify the download source and SHA-256.'
)
Set-Content -LiteralPath (Join-Path $PortableDir "README.txt") -Value $Readme -Encoding UTF8

$Zip = Join-Path $Root "dist\QwenSubtitle-portable-0.1.0-win64.zip"
if (Test-Path $Zip) {
    Remove-Item $Zip -Force
}
Compress-Archive -Path $PortableDir -DestinationPath $Zip -CompressionLevel Optimal

$Hash = Get-FileHash -Algorithm SHA256 -Path $Exe
$HashLine = "$($Hash.Hash.ToLower())  QwenSubtitle.exe"
$HashFile = Join-Path $Root "dist\QwenSubtitle-portable.sha256"
Set-Content -Path $HashFile -Value $HashLine -Encoding ascii

$ZipHash = Get-FileHash -Algorithm SHA256 -Path $Zip
$ZipHashLine = "$($ZipHash.Hash.ToLower())  QwenSubtitle-portable-0.1.0-win64.zip"
Set-Content -Path (Join-Path $Root "dist\QwenSubtitle-portable-zip.sha256") -Value $ZipHashLine -Encoding ascii
Write-Host "Portable zip: $Zip"
Write-Host "EXE SHA256: $HashLine"
Write-Host "ZIP SHA256: $ZipHashLine"

param(
    [switch]$CI
)

$ErrorActionPreference = "Stop"
$env:UV_SYSTEM_CERTS = "true"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv was not found in PATH. Install uv from https://docs.astral.sh/uv/."
}

$repoDir = $PSScriptRoot
$env:PYTHONPATH = (Join-Path $repoDir "src")

# Define base paths
$BaseDistPath = Join-Path $repoDir "dist"

# Fetch version number from src/utils/version.py
$VERSION = & uv run --locked --group build --project $repoDir python -c "from utils.version import APP_VERSION; print(APP_VERSION)" |
    ForEach-Object { $_.Trim() }
if ($LASTEXITCODE -ne 0 -or $VERSION -notmatch '^\d+\.\d+\.\d+$') {
    throw "Could not determine the application version."
}

# Keep other builds and previous release versions intact.
$PlatformDistPath = Join-Path $BaseDistPath "windows\NITools_v$VERSION"
$BuildPath = Join-Path $repoDir "build\windows_v$VERSION"
New-Item -ItemType Directory -Path $PlatformDistPath, $BuildPath -Force | Out-Null

# Resolve the locked interpreter before restricting the DLL search path.
# Unrelated native runtimes on PATH can otherwise supply an incompatible UCRT
# to PyInstaller, preventing installed audio plug-ins from initializing.
$BuildPython = (& uv run --locked --group build --project $repoDir python -c "import sys; print(sys.executable)").Trim()
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $BuildPython)) {
    throw "Could not resolve the build interpreter."
}
$OriginalBuildPath = $env:PATH
try {
    $env:PATH = "$(Split-Path -Parent $BuildPython);$env:SystemRoot\System32;$env:SystemRoot"
    # Run PyInstaller to bundle the app as a single Windows .exe
    & $BuildPython -m PyInstaller `
    --clean `
    --noconfirm `
    (Join-Path $repoDir "packaging\nitools.spec") `
    --workpath $BuildPath `
    --distpath $PlatformDistPath
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed."
    }
} finally {
    $env:PATH = $OriginalBuildPath
}

# Generate PDF guide
Copy-Item -LiteralPath (Join-Path $BuildPath 'nitools\runtime-requirements.txt') -Destination $PlatformDistPath -Force
$Compiler = Join-Path $env:SystemRoot 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
& $Compiler /nologo /target:winexe /platform:x64 /reference:System.Windows.Forms.dll /reference:System.Drawing.dll `
    "/win32icon:$repoDir\icons\app.ico" "/out:$PlatformDistPath\NITools.exe" "$repoDir\packaging\windows_launcher.cs"
if ($LASTEXITCODE -ne 0) { throw 'Windows launcher compilation failed.' }
& $BuildPython (Join-Path $repoDir 'packaging\collect_licenses.py') (Join-Path $BuildPath 'nitools') $PlatformDistPath
if ($LASTEXITCODE -ne 0) { throw 'Release inventory or license collection failed.' }
Copy-Item -LiteralPath (Join-Path $repoDir "LICENSE"), (Join-Path $repoDir "THIRD_PARTY_NOTICES.md") -Destination $PlatformDistPath -Force
$GuidePath = Join-Path $PlatformDistPath "nitools-guide.pdf"
& uv run --locked --group build --project $repoDir python (Join-Path $repoDir "packaging\make_guide.py") (Join-Path $repoDir "docs\GUIDE.md") $GuidePath
if ($LASTEXITCODE -ne 0) {
    throw "PDF guide generation failed."
}

# Create the zip file with the version number
$ExpectedFiles = @('NITools.exe', 'NIToolsApp.exe', 'runtime-requirements.txt', 'DEPENDENCIES.json', 'licenses', 'LICENSE', 'THIRD_PARTY_NOTICES.md', 'nitools-guide.pdf')
$UnexpectedFiles = @(Get-ChildItem -LiteralPath $PlatformDistPath -Force | Where-Object { $_.Name -notin $ExpectedFiles })
if ($UnexpectedFiles.Count -gt 0) {
    throw "Unexpected files in package output; move them out before bundling: $($UnexpectedFiles.Name -join ', ')"
}
$ZipName = "NITools_Windows_v$VERSION.zip"
$ZipPath = Join-Path $BaseDistPath $ZipName
Compress-Archive -Path $PlatformDistPath -DestinationPath $ZipPath -Force
& $BuildPython (Join-Path $repoDir 'packaging\verify_package.py') --windows $PlatformDistPath --zip $ZipPath
if ($LASTEXITCODE -ne 0) { throw 'Finished Windows package verification failed.' }

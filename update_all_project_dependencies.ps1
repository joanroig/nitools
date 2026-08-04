[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [switch]$SkipSync
)

$ErrorActionPreference = "Stop"

$repoDir = $PSScriptRoot
$pyprojectPath = Join-Path $repoDir "pyproject.toml"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv was not found in PATH. Install uv from https://docs.astral.sh/uv/."
}

if (-not (Test-Path $pyprojectPath)) {
    throw "pyproject.toml not found in $repoDir"
}

$latestVersionCache = @{}

function Normalize-PyprojectEncoding {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $bytes = [System.IO.File]::ReadAllBytes($Path)
    $hasBom = $bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF

    if (-not $hasBom) {
        return
    }

    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    $text = [System.IO.File]::ReadAllText($Path, [System.Text.UTF8Encoding]::new($true))
    [System.IO.File]::WriteAllText($Path, $text, $utf8NoBom)
}

function Get-CanonicalName {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    return (($Name.ToLowerInvariant()) -replace "[-_.]+", "-")
}

function Get-LatestPyPiVersion {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PackageName
    )

    $canonical = Get-CanonicalName -Name $PackageName
    if ($latestVersionCache.ContainsKey($canonical)) {
        return $latestVersionCache[$canonical]
    }

    $candidates = @($PackageName)
    $dashName = $PackageName -replace "_", "-"
    $underscoreName = $PackageName -replace "-", "_"

    if ($dashName -ne $PackageName) {
        $candidates += $dashName
    }

    if ($underscoreName -ne $PackageName) {
        $candidates += $underscoreName
    }

    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        $url = "https://pypi.org/pypi/$candidate/json"
        try {
            $response = Invoke-RestMethod -Uri $url -Method Get -TimeoutSec 30 -ErrorAction Stop
            $latest = [string]$response.info.version
            if (-not [string]::IsNullOrWhiteSpace($latest)) {
                $latestVersionCache[$canonical] = $latest
                return $latest
            }
        }
        catch {
            continue
        }
    }

    throw "Could not resolve latest PyPI version for package '$PackageName'."
}

function Update-PyprojectFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $lines = Get-Content -LiteralPath $Path
    $updatedLines = [System.Collections.Generic.List[string]]::new()
    $changed = $false

    $section = ""
    $inProjectDependencies = $false
    $inDevDependencies = $false

    foreach ($line in $lines) {
        if ($line -match "^\s*\[(?<section>[^\]]+)\]\s*$") {
            $section = $Matches["section"]
            $inProjectDependencies = $false
            $inDevDependencies = $false
        }

        if (($section -eq "project") -and ($line -match '^\s*dependencies\s*=\s*\[\s*$')) {
            $inProjectDependencies = $true
            $updatedLines.Add($line)
            continue
        }

        if (($section -eq "project.optional-dependencies") -and ($line -match '^\s*dev\s*=\s*\[\s*$')) {
            $inDevDependencies = $true
            $updatedLines.Add($line)
            continue
        }

        if (($inProjectDependencies -or $inDevDependencies) -and ($line -match '^\s*\]\s*$')) {
            $inProjectDependencies = $false
            $inDevDependencies = $false
            $updatedLines.Add($line)
            continue
        }

        if (($inProjectDependencies -or $inDevDependencies) -and ($line -match '^(?<indent>\s*)"(?<name>[A-Za-z0-9_.-]+)(?<ws1>\s*)(?<op>==|>=|<=|~=|>|<)(?<ws2>\s*)(?<version>[^"\s,]+)"(?<tail>\s*,?\s*)$')) {
            $name = $Matches["name"]
            $op = $Matches["op"]
            $currentVersion = $Matches["version"]
            $latestVersion = Get-LatestPyPiVersion -PackageName $name

            if ($currentVersion -ne $latestVersion) {
                $updatedLine = '{0}"{1}{2}{3}{4}{5}"{6}' -f `
                    $Matches["indent"], $name, $Matches["ws1"], $op, $Matches["ws2"], $latestVersion, $Matches["tail"]

                $updatedLines.Add($updatedLine)
                Write-Host ("{0}: {1} {2} -> {3}" -f (Split-Path -Leaf $Path), $name, $currentVersion, $latestVersion)
                $changed = $true
                continue
            }
        }

        $updatedLines.Add($line)
    }

    if ($changed -and $PSCmdlet.ShouldProcess($Path, "Update pyproject dependency versions")) {
        Set-Content -LiteralPath $Path -Value $updatedLines -Encoding UTF8
    }

    return $changed
}

$changed = Update-PyprojectFile -Path $pyprojectPath
Normalize-PyprojectEncoding -Path $pyprojectPath

if ($changed) {
    Write-Host "Dependency manifest updated."
}
else {
    Write-Host "No dependency changes were needed."
}

if (-not $SkipSync) {
    Push-Location $repoDir
    try {
        Write-Host "Syncing the uv environment with the refreshed dependency metadata..."
        & uv sync --upgrade
        if ($LASTEXITCODE -ne 0) {
            throw "uv sync --upgrade failed."
        }
    }
    finally {
        Pop-Location
    }
}

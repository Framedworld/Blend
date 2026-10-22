param(
    [switch]$Sculpt,
    [switch]$CheckOnly,
    [string]$BlenderPath = $env:LANDFALL_BLENDER_EXE
)
$ErrorActionPreference = 'Stop'
$studioWorkspace = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$entryScript = Join-Path $PSScriptRoot 'open_studio.py'
try {
    if ($BlenderPath) {
        if (-not (Test-Path -LiteralPath $BlenderPath -PathType Leaf)) {
            throw "Blender was not found at LANDFALL_BLENDER_EXE: $BlenderPath"
        }
        $resolvedBlender = (Resolve-Path -LiteralPath $BlenderPath).Path
    } else {
        $installedBlender = Join-Path $env:ProgramFiles 'Blender Foundation\Blender 5.2\blender.exe'
        $onPath = Get-Command blender.exe -ErrorAction SilentlyContinue
        if (Test-Path -LiteralPath $installedBlender -PathType Leaf) {
            $resolvedBlender = $installedBlender
        } elseif ($onPath) {
            $resolvedBlender = $onPath.Source
        } else {
            throw 'Blender 5.2 LTS was not found. Install it or set LANDFALL_BLENDER_EXE to your blender.exe path.'
        }
    }
    $requiredFiles = @('Blend\landfall_studio\__init__.py', '.deps\py313\PySide6\__init__.py', '.deps\py313\shiboken6\__init__.py', '.deps\py313\qtpy\__init__.py', '.deps\py313\PIL\__init__.py', 'upstream\tentacle\tentacle\__init__.py', 'upstream\blendertk\blendertk\__init__.py', 'upstream\uitk\uitk\__init__.py', 'upstream\pythontk\pythontk\__init__.py')
    foreach ($required in @($entryScript)+@($requiredFiles | ForEach-Object { Join-Path $studioWorkspace $_ })) {
        if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
            throw "This Studio workspace is incomplete: $required. Keep Blend, upstream and .deps together. See Blend\output\FRIEND_QUICK_START.md."
        }
    }
    $version = (& $resolvedBlender --version 2>&1 | Select-Object -First 1).ToString()
    if ($version -notmatch '^Blender 5\.2\.') {
        throw "This Studio build is validated with Blender 5.2 LTS and Python 3.13. Found: $version. Set LANDFALL_BLENDER_EXE to Blender 5.2's executable."
    }
    $bundledNumpy=Join-Path (Split-Path $resolvedBlender -Parent) '5.2\python\lib\site-packages\numpy\__init__.py'
    if (-not ((Test-Path -LiteralPath $bundledNumpy) -or (Test-Path -LiteralPath (Join-Path $studioWorkspace '.deps\py313\numpy\__init__.py')))) {
        throw 'NumPy is missing from Blender and the local dependencies. Repair the Blender 5.2 installation.'
    }
    $launchInfo = @{ok=$true;blender=$resolvedBlender;version=$version;workspace=$studioWorkspace;sculpt=[bool]$Sculpt;installs_or_downloads=$false}
    if ($CheckOnly) { $launchInfo | ConvertTo-Json; exit 0 }
    $localRoot = Join-Path $studioWorkspace '.landfall_studio'
    $localTemp = Join-Path $localRoot 'temp'
    New-Item -ItemType Directory -Force -Path $localTemp | Out-Null
    $env:TEMP = $localTemp
    $env:TMP = $localTemp
    $env:BLENDER_USER_RESOURCES = Join-Path $localRoot 'blender'
    $env:LANDFALL_STUDIO_DEPS = Join-Path $studioWorkspace '.deps\py313'
    $env:TENTACLE_QT_DEPS = $env:LANDFALL_STUDIO_DEPS
    $env:LANDFALL_STUDIO_UPSTREAM_ROOT = Join-Path $studioWorkspace 'upstream'
    $launchArgs = @('--factory-startup','--python',('"'+$entryScript+'"'))
    if ($Sculpt) { $launchArgs += @('--','--sculpt-demo') }
    # This entry point intentionally opens an interactive, visible Blender window.
    $process = Start-Process -FilePath $resolvedBlender -ArgumentList $launchArgs -WorkingDirectory $studioWorkspace -WindowStyle Normal -PassThru
    Write-Output "Studio is opening in Blender (PID $($process.Id)). Your Blender preferences are isolated in .landfall_studio\blender."
    exit 0
} catch {
    Write-Host "Landfall Studio could not start: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

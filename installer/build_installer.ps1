param(
    [string]$BlenderDir = 'C:\Program Files\Blender Foundation\Blender 5.2',
    [string]$OutDir,
    [switch]$ReusePayload   # rebuild only the setup exe around an existing payload.zip
)
# Builds LandfallStudioSetup.exe: bundled Blender + Studio + trimmed Qt, per-user installer.
# Uses only tools that ship with Windows (.NET Framework csc, System.IO.Compression).
$ErrorActionPreference = 'Stop'
$installerDir = $PSScriptRoot
$studio = Split-Path $installerDir -Parent
$workspace = Split-Path $studio -Parent
if (-not $OutDir) { $OutDir = Join-Path $studio 'output\installer' }
$stage = Join-Path $OutDir 'stage'
$fw = 'C:\Windows\Microsoft.NET\Framework64\v4.0.30319'
$csc = Join-Path $fw 'csc.exe'
$version = (Select-String -Path (Join-Path $installerDir 'Common.cs') -Pattern 'Version = "([^"]+)"').Matches[0].Groups[1].Value
# Common.cs holds the only copy of the version; the exe metadata is stamped from it.
if ($version -notmatch '^(\d+)\.(\d+)\.(\d+)(?:-[a-z]+\.(\d+))?$') { throw "Unexpected version format: $version" }
$numeric = '{0}.{1}.{2}.{3}' -f $Matches[1], $Matches[2], $Matches[3], $(if ($Matches[4]) { $Matches[4] } else { 0 })
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$assemblyInfo = Join-Path $OutDir 'AssemblyInfo.cs'
@"
[assembly: System.Reflection.AssemblyProduct("Landfall Studio")]
[assembly: System.Reflection.AssemblyCompany("Framedworld")]
[assembly: System.Reflection.AssemblyVersion("$numeric")]
[assembly: System.Reflection.AssemblyFileVersion("$numeric")]
[assembly: System.Reflection.AssemblyInformationalVersion("$version")]
"@ | Set-Content -Path $assemblyInfo -Encoding UTF8

$blenderVersion = (& (Join-Path $BlenderDir 'blender.exe') --version 2>&1 | Select-Object -First 1).ToString()
if ($blenderVersion -notmatch '^Blender 5\.2\.') { throw "Expected Blender 5.2 at $BlenderDir, found: $blenderVersion" }

function Copy-Tree($from, $to, [string[]]$excludeDirs = @(), [string[]]$excludeFiles = @()) {
    $roboArgs = @($from, $to, '/E', '/NFL', '/NDL', '/NJH', '/NJS', '/NP', '/R:1', '/W:1')
    if ($excludeDirs.Count) { $roboArgs += '/XD'; $roboArgs += $excludeDirs }
    if ($excludeFiles.Count) { $roboArgs += '/XF'; $roboArgs += $excludeFiles }
    & robocopy @roboArgs | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "Copy failed: $from -> $to (robocopy $LASTEXITCODE)" }
}

$payload = Join-Path $OutDir 'payload.zip'
$icon = Join-Path $OutDir 'landfall.ico'
if (-not ($ReusePayload -and (Test-Path $payload))) {
Write-Host "Staging Landfall Studio $version with $blenderVersion"
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Force -Path $stage | Out-Null

# 1. Blender, without debug symbols and link libraries.
Copy-Tree $BlenderDir (Join-Path $stage 'blender') @() @('*.pdb', '*.lib', 'blender_debug_*.cmd')

# 2. Studio itself: package, entry script, license and docs.
$s = Join-Path $stage 'Blend'
Copy-Tree (Join-Path $studio 'landfall_studio') (Join-Path $s 'landfall_studio') @('__pycache__')
New-Item -ItemType Directory -Force -Path (Join-Path $s 'scripts') | Out-Null
Copy-Item (Join-Path $studio 'scripts\open_studio.py') (Join-Path $s 'scripts')
foreach ($f in 'LICENSE', 'README.md', 'blender_manifest.toml', '__init__.py') { Copy-Item (Join-Path $studio $f) $s }
Copy-Item (Join-Path $installerDir 'READ_ME_FIRST.txt') (Join-Path $stage 'Read Me First.txt')

# 3. Upstream libraries without history, tests or docs.
foreach ($lib in 'blendertk', 'landfall', 'pythontk', 'tentacle', 'uitk') {
    Copy-Tree (Join-Path $workspace "upstream\$lib") (Join-Path $stage "upstream\$lib") @('.git', '.github', 'tests', 'test', 'docs', '__pycache__', '.pytest_cache')
}

# 4. Python dependencies; PySide6 trimmed to the Qt modules Studio uses.
$deps = Join-Path $stage '.deps\py313'
Copy-Tree (Join-Path $workspace '.deps\py313') $deps @('__pycache__', 'doc', 'include', 'qml', 'resources', 'typesystems', 'glue', 'metatypes', 'scripts', 'translations') @('*.pyi')
$pyside = Join-Path $deps 'PySide6'
$unused = 'WebEngine','WebView','WebChannel','WebSockets','Quick','Qml','3D','Pdf','Multimedia','SpatialAudio','Designer','Help','Charts','DataVisualization','Graphs',
          'Location','Positioning','Bluetooth','Nfc','Sensors','SerialBus','SerialPort','RemoteObjects','Scxml','StateMachine','TextToSpeech','VirtualKeyboard',
          'Lottie','Labs','HttpServer','NetworkAuth','CanvasPainter','ShaderTools','Sql','AxContainer','Asyncio','QmlFeatures'
foreach ($name in $unused) {
    Get-ChildItem $pyside -File | Where-Object { $_.Name -like "Qt6$name*.dll" -or $_.Name -like "Qt$name*.pyd" } | Remove-Item -Force
}
Get-ChildItem $pyside -File -Filter '*.exe' | Remove-Item -Force
Get-ChildItem $pyside -File | Where-Object { $_.Name -match '^(avcodec|avformat|avutil|swresample|swscale)-' } | Remove-Item -Force
Get-ChildItem $pyside -Directory | Where-Object { $_.Name -eq 'QtAsyncio' } | Remove-Item -Recurse -Force
foreach ($plugin in 'assetimporters','canbus','designer','geometryloaders','geoservices','multimedia','position','qmltooling','renderers','renderplugins','sceneparsers','scxmldatamodel','sensors','sqldrivers','texttospeech','webview') {
    $p = Join-Path $pyside "plugins\$plugin"; if (Test-Path $p) { Remove-Item $p -Recurse -Force }
}

# 5. Launcher and notices.
& python -c "from PIL import Image; Image.open(r'$studio\docs\landfall-icon.png').convert('RGBA').save(r'$icon', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])"
if (-not (Test-Path $icon)) { throw 'Icon conversion failed' }
& $csc /nologo /target:winexe /optimize+ "/win32icon:$icon" "/out:$(Join-Path $stage 'Landfall Studio.exe')" /r:System.Windows.Forms.dll /r:System.Drawing.dll "/r:$fw\System.IO.Compression.dll" "/r:$fw\System.IO.Compression.FileSystem.dll" (Join-Path $installerDir 'Launcher.cs') (Join-Path $installerDir 'Common.cs') $assemblyInfo
if ($LASTEXITCODE) { throw 'Launcher compile failed' }
$notices = [Collections.Generic.List[string]](Get-Content (Join-Path $installerDir 'THIRD_PARTY_NOTICES.txt'))
$notices.Add(''); $notices.Add("Commits in this build ($version, built $(Get-Date -Format 'yyyy-MM-dd')):")
foreach ($repo in @($studio) + @('landfall', 'tentacle', 'uitk', 'blendertk', 'pythontk' | ForEach-Object { Join-Path $workspace "upstream\$_" })) {
    $changed = @(git -C $repo status --porcelain --untracked-files=no).Count
    $notices.Add(('  {0,-16} {1}{2}' -f (Split-Path $repo -Leaf), (git -C $repo rev-parse HEAD), $(if ($changed) { " plus local changes in $changed file(s), included as source" } else { '' })))
}
$notices.Add("  Blender          $blenderVersion")
$notices | Set-Content -Path (Join-Path $stage 'THIRD_PARTY_NOTICES.txt') -Encoding UTF8

# 6. Precompile Python with Blender's own interpreter for a faster first start.
$py = Get-ChildItem (Join-Path $stage 'blender\5.2\python\bin') -Filter 'python*.exe' | Select-Object -First 1
& $py.FullName -m compileall -q -j 0 (Join-Path $stage 'Blend') (Join-Path $stage 'upstream') | Out-Null

# 7. Payload zip, then setup.exe with the payload appended.
if (Test-Path $payload) { Remove-Item $payload -Force }
Add-Type -AssemblyName System.IO.Compression.FileSystem
Write-Host 'Compressing payload...'
[System.IO.Compression.ZipFile]::CreateFromDirectory($stage, $payload, [System.IO.Compression.CompressionLevel]::Optimal, $false)
}
$stub = Join-Path $OutDir 'setup_stub.exe'
& $csc /nologo /target:winexe /optimize+ "/win32icon:$icon" "/out:$stub" /r:System.Windows.Forms.dll /r:System.Drawing.dll "/r:$fw\System.IO.Compression.dll" "/r:$fw\System.IO.Compression.FileSystem.dll" (Join-Path $installerDir 'Setup.cs') (Join-Path $installerDir 'Common.cs') $assemblyInfo
if ($LASTEXITCODE) { throw 'Setup compile failed' }
$setup = Join-Path $OutDir ("LandfallStudioSetup-$version.exe")
$out = [IO.File]::Create($setup)
try {
    foreach ($part in $stub, $payload) { $in = [IO.File]::OpenRead($part); $in.CopyTo($out); $in.Dispose() }
    $len = (Get-Item $payload).Length
    $trailer = [BitConverter]::GetBytes([long]$len) + [Text.Encoding]::ASCII.GetBytes('LFSTUDIO')
    $out.Write($trailer, 0, $trailer.Length)
} finally { $out.Dispose() }
Remove-Item $stub
$hash = (Get-FileHash $setup -Algorithm SHA256).Hash
"{0}`n  {1:N0} MB, SHA256 {2}" -f $setup, ((Get-Item $setup).Length / 1MB), $hash

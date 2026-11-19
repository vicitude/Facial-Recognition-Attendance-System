param([string]$YoloWeights)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$root = $PSScriptRoot
$yolo = 'runs/detect/train/weights/best.pt'
$yoloHash = '39b18262cd6f6b259790fed3b6421c11f17ced29a8633c899bab2445a1d73ae7'
$antiSpoof = 'research_assets/Silent-Face-Anti-Spoofing'
$upstream = 'https://raw.githubusercontent.com/minivision-ai/Silent-Face-Anti-Spoofing/b6d5f04ad78778917853b25c778acef6d5626d15'

function Install-VerifiedAsset($RelativePath, $Sha256, $Url, $SourcePath, [switch]$WindowsNewlines) {
    $dest = Join-Path $root $RelativePath
    if (Test-Path -LiteralPath $dest) {
        if ((Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash -ne $Sha256) {
            throw "Existing file does not match the expected SHA-256; not overwritten: $RelativePath"
        }
        Write-Output "Verified: $RelativePath"
        return
    }
    $dir = Split-Path -Parent $dest
    New-Item -Path $dir -ItemType Directory -Force | Out-Null
    $temp = Join-Path $dir ("temp_" + [guid]::NewGuid().ToString('N'))
    try {
        if ($SourcePath) {
            Copy-Item -LiteralPath $SourcePath -Destination $temp
        } else {
            Invoke-WebRequest -UseBasicParsing -Uri $Url -OutFile $temp -TimeoutSec 90
        }
        if ($WindowsNewlines) {
            # The runtime hashes the Windows checkout bytes of these upstream Python sources.
            $content = [IO.File]::ReadAllText($temp) -replace '\r?\n', "`r`n"
            [IO.File]::WriteAllText($temp, $content, [Text.UTF8Encoding]::new($false))
        }
        if ((Get-FileHash -LiteralPath $temp -Algorithm SHA256).Hash -ne $Sha256) {
            throw "SHA-256 mismatch: $RelativePath"
        }
        [IO.File]::Move($temp, $dest)
        Write-Output "Ready: $RelativePath"
    } finally {
        if (Test-Path -LiteralPath $temp -PathType Leaf) { Remove-Item -LiteralPath $temp }
    }
}

Install-VerifiedAsset 'facenet/facenet_mobilenet.pth' '0a26260c22c0487a3c06cbff2ed20edfdb214c243953added08f287d3e24c085' 'https://github.com/bubbliiiing/facenet-pytorch/releases/download/v1.0/facenet_mobilenet.pth'
Install-VerifiedAsset "$antiSpoof/src/model_lib/MiniFASNet.py" '6c3159a459838b079c34e3656762549b7375444d994611fac92688259dbe313f' "$upstream/src/model_lib/MiniFASNet.py" -WindowsNewlines
Install-VerifiedAsset "$antiSpoof/src/generate_patches.py" '9fc03bc0da6b22455f93c589be77128b7dd592fed87aa5f843cfa06c6a02ee3c' "$upstream/src/generate_patches.py" -WindowsNewlines
Install-VerifiedAsset "$antiSpoof/resources/anti_spoof_models/2.7_80x80_MiniFASNetV2.pth" 'a5eb02e1843f19b5386b953cc4c9f011c3f985d0ee2bb9819eea9a142099bec0' "$upstream/resources/anti_spoof_models/2.7_80x80_MiniFASNetV2.pth"
Install-VerifiedAsset "$antiSpoof/resources/anti_spoof_models/4_0_0_80x80_MiniFASNetV1SE.pth" '84ee1d37d96894d5e82de5a57df044ef80a58be2b218b5ed7cdfd875ec2f5990' "$upstream/resources/anti_spoof_models/4_0_0_80x80_MiniFASNetV1SE.pth"
if ($YoloWeights) {
    $source = (Resolve-Path -LiteralPath $YoloWeights).ProviderPath
    Install-VerifiedAsset $yolo $yoloHash -SourcePath $source
} elseif (Test-Path -LiteralPath (Join-Path $root $yolo)) {
    Install-VerifiedAsset $yolo $yoloHash
} else {
    throw "Upstream files are ready, but $yolo is still missing. Obtain the original project checkpoint from the maintainer and rerun with -YoloWeights."
}

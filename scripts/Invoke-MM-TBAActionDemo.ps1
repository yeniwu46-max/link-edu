param(
    [Parameter(Mandatory = $true)]
    [string]$VideoPath,

    [string]$OutputPath,

    [ValidateRange(1, 120)]
    [int]$PredictStep = 8,

    [ValidateRange(1, 120)]
    [int]$OutputStep = 4,

    [ValidateRange(1, 60)]
    [int]$OutputFps = 6,

    [ValidateSet('cpu', 'cuda:0')]
    [string]$Device = 'cuda:0'
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$dataRoot = Join-Path $repoRoot 'data\external\MM-TBA\Teacher_Action_Detection\my_mmaction'
$demoScript = 'E:\codex\mm-tba-runtime\demo_spatiotemporal_det_export.py'
$config = Join-Path $dataRoot 'configs\detection\acrn\my-slowfast-acrn_kinetics400-pretrained-r50_8xb8-8x8x1-cosine-20e_ava21-rgb.py'
$actionCheckpoint = Join-Path $dataRoot 'work_dirs\my-slowfast-acrn_kinetics400-pretrained-r50_8xb8-8x8x1-cosine-20e_ava21-rgb\best_mAP_overall_epoch_9.pth'
$detectorConfig = Join-Path $dataRoot 'demo\demo_configs\faster-rcnn_r50_fpn_2x_coco_infer.py'
$detectorCheckpoint = Join-Path $dataRoot 'Checkpionts\mmdetection\faster_rcnn_r50_fpn_2x_coco_bbox_mAP-0.384_20200504_210434-a5d8aa15.pth'
$labelMap = Join-Path $dataRoot 'tools\data\ava\label_map.txt'
$runtimePython = '/root/mm-tba-runtime/.venv-gpu/bin/python'
$runtimeSource = '/root/mm-tba-runtime/mmcv-source/mmcv-2.1.0:/root/mm-tba-runtime/source'

$resolvedVideo = (Resolve-Path -LiteralPath $VideoPath).Path
$durationText = & ffprobe -v error -show_entries format=duration -of csv=p=0 $resolvedVideo
if ($LASTEXITCODE -ne 0) {
    throw "Could not read video duration: $resolvedVideo"
}
$duration = [double]::Parse($durationText.Trim(), [Globalization.CultureInfo]::InvariantCulture)
if ($duration -gt 30) {
    throw 'The upstream demo decodes an entire clip into memory. Split long recordings into clips of 30 seconds or less before running this helper.'
}
if (-not $OutputPath) {
    $outputDirectory = Join-Path $repoRoot 'output\mm-tba'
    $OutputPath = Join-Path $outputDirectory "$( [IO.Path]::GetFileNameWithoutExtension($resolvedVideo) )-action-detected.mp4"
}
$outputDirectory = Split-Path -Parent $OutputPath
New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
$resolvedOutput = Join-Path (Resolve-Path -LiteralPath $outputDirectory).Path (Split-Path -Leaf $OutputPath)

foreach ($requiredPath in @($demoScript, $config, $actionCheckpoint, $detectorConfig, $detectorCheckpoint, $labelMap)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Required MM-TBA file is missing: $requiredPath"
    }
}

function Convert-ToWslPath([string]$Path) {
    $fullPath = [IO.Path]::GetFullPath($Path)
    if ($fullPath -notmatch '^(?<drive>[A-Za-z]):\\(?<rest>.*)$') {
        throw "Expected a drive-letter path that WSL can mount: $fullPath"
    }
    $drive = $Matches.drive.ToLowerInvariant()
    $rest = $Matches.rest.Replace('\', '/')
    return "/mnt/$drive/$rest"
}

$linuxVideo = Convert-ToWslPath $resolvedVideo
$linuxOutput = Convert-ToWslPath $resolvedOutput
$linuxDemo = Convert-ToWslPath $demoScript
$linuxConfig = Convert-ToWslPath $config
$linuxActionCheckpoint = Convert-ToWslPath $actionCheckpoint
$linuxDetectorConfig = Convert-ToWslPath $detectorConfig
$linuxDetectorCheckpoint = Convert-ToWslPath $detectorCheckpoint
$linuxLabelMap = Convert-ToWslPath $labelMap

$wslArgs = @(
    '-d', 'Ubuntu', '--', 'env', "PYTHONPATH=$runtimeSource", $runtimePython,
    $linuxDemo, $linuxVideo, $linuxOutput,
    '--config', $linuxConfig,
    '--checkpoint', $linuxActionCheckpoint,
    '--det-config', $linuxDetectorConfig,
    '--det-checkpoint', $linuxDetectorCheckpoint,
    '--det-score-thr', '0.5',
    '--action-score-thr', '0.5',
    '--predict-stepsize', "$PredictStep",
    '--output-stepsize', "$OutputStep",
    '--output-fps', "$OutputFps",
    '--label-map', $linuxLabelMap,
    '--device', $Device
)

& wsl.exe @wslArgs
if ($LASTEXITCODE -ne 0) {
    throw "MM-TBA action demo exited with code $LASTEXITCODE"
}

Write-Output "Action detection video saved to: $resolvedOutput"

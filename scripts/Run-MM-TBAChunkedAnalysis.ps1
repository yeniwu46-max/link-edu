param(
    [string]$VideoPath = 'D:\大二下学习资料\小学期两门\教技2402 1150424214 高梦琴\3-试讲视频（新压缩）.mp4',
    [string]$OutputDirectory,
    [ValidateRange(10, 60)]
    [int]$CoreSeconds = 20,
    [ValidateRange(1, 5)]
    [int]$ContextSeconds = 2,
    [ValidateSet('cpu', 'cuda:0')]
    [string]$Device = 'cuda:0'
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$modelRoot = Join-Path $repoRoot 'data\external\MM-TBA\Teacher_Action_Detection\my_mmaction'
$exportDemo = 'E:\codex\mm-tba-runtime\demo_spatiotemporal_det_export.py'
$runtimePython = '/root/mm-tba-runtime/.venv-gpu/bin/python'
$runtimeSource = '/root/mm-tba-runtime/mmcv-source/mmcv-2.1.0:/root/mm-tba-runtime/source'
$renderer = Join-Path $PSScriptRoot 'Render-MM-TBAAnnotations.py'

$resolvedVideo = (Resolve-Path -LiteralPath $VideoPath).Path
if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $repoRoot 'output\mm-tba\full-analysis'
}
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$OutputDirectory = (Resolve-Path -LiteralPath $OutputDirectory).Path
$chunksDirectory = Join-Path $OutputDirectory 'chunks'
New-Item -ItemType Directory -Path $chunksDirectory -Force | Out-Null

foreach ($requiredPath in @(
    $exportDemo,
    $renderer,
    (Join-Path $modelRoot 'configs\detection\acrn\my-slowfast-acrn_kinetics400-pretrained-r50_8xb8-8x8x1-cosine-20e_ava21-rgb.py'),
    (Join-Path $modelRoot 'work_dirs\my-slowfast-acrn_kinetics400-pretrained-r50_8xb8-8x8x1-cosine-20e_ava21-rgb\best_mAP_overall_epoch_9.pth'),
    (Join-Path $modelRoot 'demo\demo_configs\faster-rcnn_r50_fpn_2x_coco_infer.py'),
    (Join-Path $modelRoot 'Checkpionts\mmdetection\faster_rcnn_r50_fpn_2x_coco_bbox_mAP-0.384_20200504_210434-a5d8aa15.pth'),
    (Join-Path $modelRoot 'tools\data\ava\label_map.txt')
)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Required MM-TBA file is missing: $requiredPath"
    }
}

function Convert-ToWslPath([string]$Path) {
    $fullPath = [IO.Path]::GetFullPath($Path)
    if ($fullPath -notmatch '^(?<drive>[A-Za-z]):\\(?<rest>.*)$') {
        throw "Expected a drive-letter path mounted in WSL: $fullPath"
    }
    return "/mnt/$($Matches.drive.ToLowerInvariant())/$($Matches.rest.Replace('\', '/'))"
}

$probe = (& ffprobe -v error -show_entries format=duration -show_entries stream=width,height,avg_frame_rate -of json $resolvedVideo) | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) {
    throw "Could not inspect source video: $resolvedVideo"
}
$duration = [double]::Parse($probe.format.duration, [Globalization.CultureInfo]::InvariantCulture)
$videoStream = $probe.streams | Where-Object { $_.width -and $_.height } | Select-Object -First 1
$fpsParts = $videoStream.avg_frame_rate -split '/'
$sourceFps = [double]$fpsParts[0] / [double]$fpsParts[1]
if ($sourceFps -lt 1) {
    throw "Could not determine source frame rate: $($videoStream.avg_frame_rate)"
}

$scriptLinux = Convert-ToWslPath $exportDemo
$configLinux = Convert-ToWslPath (Join-Path $modelRoot 'configs\detection\acrn\my-slowfast-acrn_kinetics400-pretrained-r50_8xb8-8x8x1-cosine-20e_ava21-rgb.py')
$actionCheckpointLinux = Convert-ToWslPath (Join-Path $modelRoot 'work_dirs\my-slowfast-acrn_kinetics400-pretrained-r50_8xb8-8x8x1-cosine-20e_ava21-rgb\best_mAP_overall_epoch_9.pth')
$detectorConfigLinux = Convert-ToWslPath (Join-Path $modelRoot 'demo\demo_configs\faster-rcnn_r50_fpn_2x_coco_infer.py')
$detectorCheckpointLinux = Convert-ToWslPath (Join-Path $modelRoot 'Checkpionts\mmdetection\faster_rcnn_r50_fpn_2x_coco_bbox_mAP-0.384_20200504_210434-a5d8aa15.pth')
$labelMapLinux = Convert-ToWslPath (Join-Path $modelRoot 'tools\data\ava\label_map.txt')

$allEvents = [System.Collections.Generic.List[object]]::new()
$segmentCount = [math]::Ceiling($duration / $CoreSeconds)
$prePad = 1.5

for ($index = 0; $index -lt $segmentCount; $index++) {
    $coreStart = $index * $CoreSeconds
    $coreEnd = [math]::Min($duration, $coreStart + $CoreSeconds)
    $segmentStart = [math]::Max(0, $coreStart - $ContextSeconds)
    $segmentEnd = [math]::Min($duration, $coreEnd + $ContextSeconds)
    $isFirst = $index -eq 0
    $isLast = $index -eq ($segmentCount - 1)
    $segmentPath = Join-Path $chunksDirectory ('segment_{0:D3}.mp4' -f $index)
    $resultPath = Join-Path $chunksDirectory ('segment_{0:D3}.json' -f $index)
    $filterParts = @()
    if ($isFirst) { $filterParts += "start_duration=$prePad`:start_mode=clone" }
    if ($isLast) { $filterParts += "stop_duration=$prePad`:stop_mode=clone" }
    $filter = if ($filterParts.Count) { 'tpad=' + ($filterParts -join ':') } else { $null }

    Write-Host ("[{0}/{1}] Preparing source time {2:N1}-{3:N1}s" -f ($index + 1), $segmentCount, $segmentStart, $segmentEnd)
    $ffmpegArgs = @('-hide_banner', '-loglevel', 'error', '-y', '-ss', "$segmentStart", '-i', $resolvedVideo, '-t', "$($segmentEnd - $segmentStart)")
    if ($filter) { $ffmpegArgs += @('-vf', $filter) }
    if ($isFirst) { $ffmpegArgs += @('-t', "$($segmentEnd - $segmentStart + $prePad)") }
    if ($isLast) { $ffmpegArgs += @('-t', "$($segmentEnd - $segmentStart + $(if ($isFirst) { $prePad } else { 0 }) + $prePad)") }
    $ffmpegArgs += @('-an', '-r', "$sourceFps", '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '22', $segmentPath)
    & ffmpeg @ffmpegArgs
    if ($LASTEXITCODE -ne 0) { throw "Could not prepare segment $index" }

    $segmentOffset = $segmentStart - $(if ($isFirst) { $prePad } else { 0 })
    $linuxVideo = Convert-ToWslPath $segmentPath
    $linuxResult = Convert-ToWslPath $resultPath
    $wslArgs = @(
        '-d', 'Ubuntu', '--', 'env', "PYTHONPATH=$runtimeSource", $runtimePython,
        $scriptLinux, $linuxVideo, '/tmp/mm-tba-segment-preview.mp4',
        '--config', $configLinux,
        '--checkpoint', $actionCheckpointLinux,
        '--det-config', $detectorConfigLinux,
        '--det-checkpoint', $detectorCheckpointLinux,
        '--det-score-thr', '0.5',
        '--action-score-thr', '0.5',
        '--predict-stepsize', '24',
        '--output-stepsize', '8',
        '--output-fps', '3',
        '--label-map', $labelMapLinux,
        '--device', $Device,
        '--result-json', $linuxResult,
        '--source-offset', "$segmentOffset",
        '--source-fps', "$sourceFps"
    )
    & wsl.exe @wslArgs
    if ($LASTEXITCODE -ne 0) { throw "Action inference failed for segment $index" }

    $payload = Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
    foreach ($event in $payload.events) {
        $globalTime = [double]$event.time_seconds
        if ($globalTime -ge ($coreStart - 0.001) -and $globalTime -lt ($coreEnd - 0.001)) {
            $event | Add-Member -NotePropertyName chunk_index -NotePropertyValue $index -Force
            if ($globalTime -lt 0) { $event.time_seconds = 0.0 }
            if ($globalTime -gt $duration) { $event.time_seconds = $duration }
            $allEvents.Add($event)
        }
    }
}

$eventsPath = Join-Path $OutputDirectory 'action-events.json'
$allEvents | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $eventsPath -Encoding utf8
$silentVideo = Join-Path $OutputDirectory 'annotated-silent.mp4'
$finalVideo = Join-Path $OutputDirectory 'classroom-actions-annotated.mp4'
$rendererLinux = Convert-ToWslPath $renderer
$inputLinux = Convert-ToWslPath $resolvedVideo
$eventsLinux = Convert-ToWslPath $eventsPath
$silentLinux = Convert-ToWslPath $silentVideo
$renderArgs = @('-d', 'Ubuntu', '--', '/root/mm-tba-runtime/.venv-gpu/bin/python', $rendererLinux, '--video', $inputLinux, '--events', $eventsLinux, '--output', $silentLinux, '--fps', "$sourceFps")
& wsl.exe @renderArgs
if ($LASTEXITCODE -ne 0) { throw 'Could not render full-length action overlay video' }

& ffmpeg -hide_banner -loglevel error -y -i $silentVideo -i $resolvedVideo -map 0:v:0 -map '1:a?' -c:v libx264 -preset fast -crf 21 -c:a aac -shortest $finalVideo
if ($LASTEXITCODE -ne 0) { throw 'Could not mux the original classroom audio into the annotated video' }

Write-Host "Saved full-length overlay: $finalVideo"
Write-Host "Saved timestamped events: $eventsPath"
Write-Host "Saved event table: $(Join-Path $OutputDirectory 'action-events.csv')"

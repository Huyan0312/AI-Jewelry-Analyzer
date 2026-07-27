$requestPath = "E:\CODE\SciptAuto=AI\AI Super\AI PTS\QA_HANDOFF\request.json"
$lastJobId = ""

Write-Host "[MONITOR] Started monitoring QA_HANDOFF/request.json every 20 seconds..."

while ($true) {
    if (Test-Path $requestPath) {
        try {
            $raw = Get-Content -Path $requestPath -Raw -ErrorAction SilentlyContinue
            if ($raw) {
                $content = $raw | ConvertFrom-Json
                if ($content.state -eq "READY_FOR_TEST" -and $content.job_id -and ($content.job_id -ne "") -and ($content.job_id -ne $lastJobId)) {
                    Write-Host "[NEW_JOB_DETECTED] Found READY_FOR_TEST with job_id: $($content.job_id)"
                    $lastJobId = $content.job_id
                }
            }
        } catch {
            # JSON parsing error during file write, ignore and retry next loop
        }
    }
    Start-Sleep -Seconds 20
}

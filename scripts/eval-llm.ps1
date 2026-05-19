param(
    [switch]$Json,
    [switch]$Verbose,
    [string]$CaseDir,
    [string]$OutputFile
)

$vaultRoot = Split-Path -Parent $PSScriptRoot

# ── Helpers ──────────────────────────────────────────────

function Get-Frontmatter {
    param([string]$Content)
    $fm = @{}
    $lines = $Content -split '\r?\n'
    if ($lines.Count -gt 0 -and $lines[0].Trim() -eq '---') {
        for ($i = 1; $i -lt $lines.Count; $i++) {
            $line = $lines[$i]
            if ($line.Trim() -eq '---') { break }
            if ($line -match '^(\w[\w-]*):\s*(.*)') {
                $key = $matches[1]
                $val = $matches[2].Trim()
                $fm[$key] = if ($val -eq '' -or $val -eq '[]') { '' } else { $val }
            }
        }
    }
    return $fm
}

# ── Validation ───────────────────────────────────────────

function Test-QuestionGenOutput {
    param($Questions, $Expected)

    $results = @()
    $minQ = if ($Expected.minQuestions) { $Expected.minQuestions } else { 1 }
    $maxQ = if ($Expected.maxQuestions) { $Expected.maxQuestions } else { 10 }
    $checks = if ($Expected.checks) { $Expected.checks } else { @{} }

    # Question count
    $count = $Questions.Count
    if ($count -lt $minQ) {
        $results += @{ Pass=$false; Reason="Generated $count questions, minimum $minQ required" }
        return $results
    }
    if ($count -gt $maxQ) {
        $results += @{ Pass=$false; Reason="Generated $count questions, maximum $maxQ allowed" }
        return $results
    }
    $results += @{ Pass=$true; Reason="Question count $count within range [$minQ-$maxQ]" }

    # Per-question checks
    $qIdx = 0
    foreach ($q in $Questions) {
        $qIdx++

        # Required fields
        if ($checks.ContainsKey('requiredFields')) {
            foreach ($field in $checks['requiredFields']) {
                if (-not (Get-Member -InputObject $q -Name $field -MemberType Properties)) {
                    $results += @{ Pass=$false; Reason="Q$qIdx : missing required field '$field'" }
                }
            }
        }

        # Options count
        if ($checks.ContainsKey('optionsCount')) {
            $expectedOpts = $checks['optionsCount']
            $actualOpts = if ($q.options) { $q.options.Count } else { 0 }
            if ($actualOpts -ne $expectedOpts) {
                $results += @{ Pass=$false; Reason="Q$qIdx : expected $expectedOpts options, got $actualOpts" }
            } else {
                $results += @{ Pass=$true; Reason="Q$qIdx : options=$actualOpts OK" }
            }
        }

        # Explanation present
        if ($checks.ContainsKey('hasExplanation') -and $checks['hasExplanation']) {
            if (-not $q.explanation -or $q.explanation.Trim().Length -lt 10) {
                $results += @{ Pass=$false; Reason="Q$qIdx : explanation missing or too short" }
            } else {
                $results += @{ Pass=$true; Reason="Q$qIdx : explanation OK" }
            }
        }

        # Answer in range
        if ($checks.ContainsKey('answerInRange') -and $checks['answerInRange']) {
            $optCount = if ($q.options) { $q.options.Count } else { 0 }
            if ($q.answer -lt 0 -or $q.answer -ge $optCount) {
                $results += @{ Pass=$false; Reason="Q$qIdx : answer index $($q.answer) out of range [0-$($optCount-1)]" }
            } else {
                $results += @{ Pass=$true; Reason="Q$qIdx : answer=$($q.answer) in range OK" }
            }
        }
    }

    return $results
}

# ── Main ─────────────────────────────────────────────────

Write-Host "=== Eval LLM Runner ===" -ForegroundColor Cyan
Write-Host "Vault: $vaultRoot"

if ($CaseDir) {
    $casePath = if (Test-Path $CaseDir) { $CaseDir } else { Join-Path $vaultRoot $CaseDir }
} else {
    $casePath = Join-Path $vaultRoot "evals/cases/question-gen"
}

Write-Host "Cases: $casePath"
Write-Host ""

if (-not (Test-Path $casePath)) {
    Write-Host "ERROR: Case directory not found: $casePath" -ForegroundColor Red
    exit 2
}

$cases = Get-ChildItem -Path $casePath -Directory | Sort-Object Name
$totalCases = 0
$passedCases = 0
$failedCases = 0
$allResults = @()

foreach ($case in $cases) {
    $totalCases++
    $sourceFile = Join-Path $case.FullName "source.md"
    $expectedFile = Join-Path $case.FullName "expected.json"
    $metaFile = Join-Path $case.FullName "meta.json"

    if (-not (Test-Path $expectedFile)) {
        Write-Host "[$($case.Name)] SKIP — no expected.json" -ForegroundColor DarkGray
        continue
    }

    $expected = Get-Content -Path $expectedFile -Raw -Encoding UTF8 | ConvertFrom-Json
    $meta = @{}
    if (Test-Path $metaFile) {
        try { $meta = Get-Content $metaFile -Raw -Encoding UTF8 | ConvertFrom-Json } catch {}
    }
    $expectFail = if ($meta.expectFail) { $meta.expectFail } else { $false }

    # Determine output file
    $outputPath = if ($OutputFile) {
        if (Test-Path $OutputFile) { $OutputFile } else { Join-Path $vaultRoot $OutputFile }
    } else {
        Join-Path $case.FullName "output.json"
    }

    Write-Host "[$($case.Name)] " -NoNewline

    if (-not (Test-Path $outputPath)) {
        Write-Host "SKIP — no output.json (generate questions first, save to $outputPath)" -ForegroundColor DarkGray
        continue
    }

    try {
        $questions = Get-Content -Path $outputPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($questions -isnot [array]) { $questions = @($questions) }
        $checks = Test-QuestionGenOutput -Questions $questions -Expected $expected
        $allPassed = ($checks | Where-Object { -not $_.Pass }).Count -eq 0

        if ($expectFail) {
            if (-not $allPassed) {
                Write-Host "PASS (expected failure)" -ForegroundColor Green
                $passedCases++
            } else {
                Write-Host "FAIL (expected failure but all checks passed)" -ForegroundColor Red
                $failedCases++
            }
        } else {
            if ($allPassed) {
                Write-Host "PASS" -ForegroundColor Green
                $passedCases++
            } else {
                Write-Host "FAIL" -ForegroundColor Red
                $failedCases++
            }
        }

        if ($Verbose) {
            foreach ($c in $checks) {
                $color = if ($c.Pass) { 'DarkGray' } else { 'Red' }
                $tag = if ($c.Pass) { '  OK' } else { '  XX' }
                Write-Host "    $tag $($c.Reason)" -ForegroundColor $color
            }
        }

        $allResults += @{
            case   = $case.Name
            passed = if ($expectFail) { -not $allPassed } else { $allPassed }
            expectFail = $expectFail
            checks = $checks | ForEach-Object { @{ pass = $_.Pass; reason = $_.Reason } }
        }
    } catch {
        Write-Host "FAIL — parse error: $_" -ForegroundColor Red
        $failedCases++
        $allResults += @{
            case   = $case.Name
            passed = $false
            expectFail = $expectFail
            checks = @(@{ pass=$false; reason="Parse error: $_" })
        }
    }
}

Write-Host ""
Write-Host "Results: $passedCases / $totalCases passed" -ForegroundColor $(if ($failedCases -eq 0) { 'Green' } else { 'Red' })

if ($Json) {
    $output = @{
        total  = $totalCases
        passed = $passedCases
        failed = $failedCases
        cases  = $allResults
    }
    $output | ConvertTo-Json -Depth 3 | Write-Output
}

exit $(if ($failedCases -gt 0) { 1 } else { 0 })

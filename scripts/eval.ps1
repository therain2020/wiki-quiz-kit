param(
    [switch]$Json,
    [switch]$Verbose
)

$vaultRoot = Split-Path -Parent $PSScriptRoot
$evalsDir = Join-Path $vaultRoot "evals/cases"
$totalCases = 0
$passedCases = 0
$failedCases = 0
$results = @()

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

function Get-WikiLinks {
    param([string]$Content)
    $links = @()
    $pattern = '\[\[([^\]|#]+)(?:[|#][^\]]+)?\]\]'
    $matches = [regex]::Matches($Content, $pattern)
    foreach ($m in $matches) {
        $target = $m.Groups[1].Value.Trim()
        if ($target -notmatch '^https?://' -and $target -notmatch '\.(png|jpg|jpeg|gif|svg|pdf)$') {
            $links += $target
        }
    }
    return $links
}

function Resolve-NotePath {
    param([string]$LinkTarget)
    $candidate = Join-Path $vaultRoot "$LinkTarget.md"
    if (Test-Path $candidate) { return $candidate }
    return $null
}

# ── Check runners ────────────────────────────────────────

function Test-FrontmatterValid {
    param([string]$Content, [string]$CaseName, [string]$RequiredType)
    $fm = Get-Frontmatter -Content $Content
    if (-not $fm.ContainsKey('type')) {
        return @{ Pass = $false; Reason = "Missing 'type' in frontmatter" }
    }
    if ($RequiredType -and $fm['type'] -ne $RequiredType) {
        return @{ Pass = $false; Reason = "Expected type='$RequiredType', got '$($fm['type'])'" }
    }
    if (-not $fm.ContainsKey('created')) {
        return @{ Pass = $false; Reason = "Missing 'created' in frontmatter" }
    }
    return @{ Pass = $true; Reason = "Frontmatter valid (type=$($fm['type']))" }
}

function Test-NotBrokenLinks {
    param([string]$Content, [string]$CaseName)
    $links = Get-WikiLinks -Content $Content
    $broken = @()
    foreach ($link in $links) {
        $resolved = Resolve-NotePath -LinkTarget $link
        if (-not $resolved) { $broken += $link }
    }
    if ($broken.Count -gt 0) {
        return @{ Pass = $false; Reason = "Broken links: $($broken -join ', ')" }
    }
    return @{ Pass = $true; Reason = "All $($links.Count) wikilinks resolve" }
}

function Test-HasBody {
    param([string]$Content, [string]$CaseName)
    if ($Content -match '^---\s*\r?\n.*?\r?\n---\s*\r?\n(.+)') {
        $body = $matches[1].Trim()
        if ($body.Length -gt 20) {
            return @{ Pass = $true; Reason = "Body present ($($body.Length) chars)" }
        }
        return @{ Pass = $false; Reason = "Body too short ($($body.Length) chars, expected >20)" }
    }
    return @{ Pass = $false; Reason = "No body content beyond frontmatter" }
}

# ── Main ─────────────────────────────────────────────────

Write-Host "=== Eval Runner ===" -ForegroundColor Cyan
Write-Host "Vault: $vaultRoot"
Write-Host "Evals: $evalsDir"
Write-Host ""

if (-not (Test-Path $evalsDir)) {
    Write-Host "ERROR: evals/cases/ directory not found" -ForegroundColor Red
    exit 2
}

$cases = Get-ChildItem -Path $evalsDir -Directory | Sort-Object Name

foreach ($case in $cases) {
    $totalCases++
    $sourceFile = Join-Path $case.FullName "source.md"
    $expectedFile = Join-Path $case.FullName "expected.md"
    $metaFile = Join-Path $case.FullName "meta.json"

    if (-not (Test-Path $expectedFile)) {
        Write-Host "[$($case.Name)] SKIP — no expected.md" -ForegroundColor DarkGray
        continue
    }

    $expectedContent = Get-Content -Path $expectedFile -Raw -Encoding UTF8
    $meta = @{}
    if (Test-Path $metaFile) {
        try { $meta = Get-Content $metaFile -Raw -Encoding UTF8 | ConvertFrom-Json } catch {}
    }

    $expectedType = if ($meta.expectedType) { $meta.expectedType } else { $null }
    $expectFail = if ($meta.expectFail) { $meta.expectFail } else { $false }

    Write-Host "[$($case.Name)] " -NoNewline

    $checks = @()
    $checks += Test-FrontmatterValid -Content $expectedContent -CaseName $case.Name -RequiredType $expectedType
    $checks += Test-HasBody -Content $expectedContent -CaseName $case.Name
    $checks += Test-NotBrokenLinks -Content $expectedContent -CaseName $case.Name

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

    $results += @{
        case   = $case.Name
        passed = if ($expectFail) { -not $allPassed } else { $allPassed }
        expectFail = $expectFail
        checks = $checks | ForEach-Object { @{ pass = $_.Pass; reason = $_.Reason } }
    }
}

Write-Host ""
Write-Host "Results: $passedCases / $totalCases passed" -ForegroundColor $(if ($failedCases -eq 0) { 'Green' } else { 'Red' })

if ($Json) {
    $output = @{
        total  = $totalCases
        passed = $passedCases
        failed = $failedCases
        cases  = $results
    }
    $output | ConvertTo-Json -Depth 3 | Write-Output
}

exit $(if ($failedCases -gt 0) { 1 } else { 0 })
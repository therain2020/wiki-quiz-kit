param(
    [switch]$Full,
    [switch]$Process,
    [switch]$Interactive,
    [switch]$UseHash,
    [switch]$WhatIf,
    [switch]$Json,
    [string]$OutputDir
)

$vaultRoot = Split-Path -Parent $PSScriptRoot
$stateFile = Join-Path $PSScriptRoot ".compile-state.json"

# ── File-to-prompt mapping ──────────────────────────────

$promptMap = @{
    "raw/inbox"      = "prompts/inbox-triage.md"
    "raw/fleeting"   = "prompts/fleeting-to-permanent.md"
    "raw/articles"   = "prompts/article-to-literature.md"
    "raw/highlights" = "prompts/highlight-to-permanent.md"
    "raw/meetings"   = "prompts/meeting-to-notes.md"
    "raw/videos"     = "prompts/video-to-literature.md"
}

$outputMap = @{
    "raw/inbox"      = "raw/inbox"
    "raw/fleeting"   = "wiki/permanent"
    "raw/articles"   = "wiki/literature"
    "raw/highlights" = "wiki/permanent"
    "raw/meetings"   = "raw/meetings"
    "raw/videos"     = "wiki/literature"
}

# ── State management ────────────────────────────────────

function Load-State {
    if (Test-Path $stateFile) {
        try {
            return Get-Content $stateFile -Raw -Encoding UTF8 | ConvertFrom-Json
        } catch {
            return $null
        }
    }
    return @{ lastCompile = $null; files = @{} }
}

function Save-State {
    param($State)
    $State | ConvertTo-Json -Depth 3 | Set-Content $stateFile -Encoding UTF8
}

# ── File scanning ───────────────────────────────────────

function Get-RawFiles {
    $rawPath = Join-Path $vaultRoot "raw"
    if (-not (Test-Path $rawPath)) { return @() }
    Get-ChildItem -Path $rawPath -Filter "*.md" -Recurse -File | Where-Object {
        $_.FullName -notmatch '[\\/]\.cache[\\/]'
    }
}

function Get-RelativeVaultPath {
    param([string]$FullPath)
    return $FullPath.Replace($vaultRoot + '\', '').Replace('\', '/')
}

function Get-PromptFor {
    param([string]$RelativePath)
    foreach ($key in $promptMap.Keys) {
        if ($RelativePath.StartsWith($key)) {
            return @{
                PromptFile = $promptMap[$key]
                OutputDir  = if ($OutputDir) { $OutputDir } else { $outputMap[$key] }
            }
        }
    }
    return $null
}

function ComputeHash {
    param([string]$Path)
    try {
        $hash = (Get-FileHash -Path $Path -Algorithm MD5).Hash
        return $hash
    } catch {
        return ""
    }
}

# ── Change detection ────────────────────────────────────

function Get-ChangedFiles {
    param($State)

    $files = Get-RawFiles
    $changed = @()
    $unchanged = @()

    foreach ($file in $files) {
        $relPath = Get-RelativeVaultPath $file.FullName
        $lastWrite = $file.LastWriteTime.ToUniversalTime().ToString("o")
        $fileHash = ""

        if ($UseHash) {
            $fileHash = ComputeHash $file.FullName
        }

        $stored = $null
        if ($State.files) {
            try {
                $stored = $State.files.$relPath
            } catch { }
        }

        $isChanged = $false
        if (-not $stored -or $Full) {
            $isChanged = $true
        } elseif ($lastWrite -gt $stored.lastProcessed) {
            $isChanged = $true
        } elseif ($UseHash -and $fileHash -ne $stored.hash) {
            $isChanged = $true
        }

        $entry = @{
            Path      = $relPath
            LastWrite = $lastWrite
            Hash      = $fileHash
            Changed   = $isChanged
            Prompt    = Get-PromptFor $relPath
        }

        if ($isChanged) { $changed += $entry } else { $unchanged += $entry }
    }

    return @{ changed = $changed; unchanged = $unchanged }
}

# ── Main ────────────────────────────────────────────────

$state = Load-State
$lastCompile = if ($state.lastCompile) { $state.lastCompile } else { "never" }

$modeText = if ($Full) { "Full" } else { "Incremental" }

if (-not $Json) {
    Write-Host "=== Knowledge Compiler ===" -ForegroundColor Cyan
    Write-Host "Mode: $modeText"
    Write-Host "Last compile: $lastCompile"
    Write-Host ""
}

Write-Host "Scanning raw/ ..." -ForegroundColor Cyan
$scanResult = Get-ChangedFiles -State $state

if (-not $Json) {
    foreach ($f in ($scanResult.changed + $scanResult.unchanged)) {
        $status = if ($f.Changed) { "[CHANGED]" } else { "[UNCHANGED]" }
        $color  = if ($f.Changed) { 'Yellow' } else { 'DarkGray' }
        Write-Host "  $($f.Path) $status" -ForegroundColor $color
    }

    Write-Host ""
    Write-Host "Files requiring compilation: $($scanResult.changed.Count)" -ForegroundColor $(if ($scanResult.changed.Count -gt 0) { 'Yellow' } else { 'Green' })
}

# ── JSON output mode ────────────────────────────────────

if ($Json) {
    $jsonOutput = @{
        mode           = $modeText
        lastCompile    = $lastCompile
        totalFiles     = ($scanResult.changed.Count + $scanResult.unchanged.Count)
        changedCount   = $scanResult.changed.Count
        tasks          = @()
    }

    foreach ($f in $scanResult.changed) {
        $jsonOutput.tasks += @{
            sourceFile = $f.Path
            promptFile = if ($f.Prompt) { $f.Prompt.PromptFile } else { $null }
            outputDir  = if ($f.Prompt) { $f.Prompt.OutputDir } else { $null }
            lastWrite  = $f.LastWrite
            status     = "pending"
        }
    }

    $jsonOutput | ConvertTo-Json -Depth 3 | Write-Output
}

# ── Human-readable task list ─────────────────────────────

if (-not $Json -and $scanResult.changed.Count -gt 0) {
    Write-Host ""
    Write-Host "Suggested compilation plan:" -ForegroundColor Cyan
    foreach ($f in $scanResult.changed) {
        $promptRel = if ($f.Prompt) { $f.Prompt.PromptFile } else { "(no prompt mapped)" }
        $outRel    = if ($f.Prompt) { $f.Prompt.OutputDir } else { "(unknown)" }
        Write-Host "  $($f.Path)"
        Write-Host "    Prompt: $promptRel"
        Write-Host "    Output: $outRel"
    }
}

# ── Process mode ────────────────────────────────────────

if ($Process -and $scanResult.changed.Count -gt 0) {
    Write-Host ""
    Write-Host "--- Processing ---" -ForegroundColor Cyan

    foreach ($f in $scanResult.changed) {
        if (-not $f.Prompt) {
            Write-Host "  SKIP $($f.Path) — no prompt mapped" -ForegroundColor DarkGray
            continue
        }

        $promptPath = Join-Path $vaultRoot $f.Prompt.PromptFile
        if (-not (Test-Path $promptPath)) {
            Write-Host "  SKIP $($f.Path) — prompt file not found: $($f.Prompt.PromptFile)" -ForegroundColor DarkGray
            continue
        }

        if ($Interactive) {
            Write-Host "  PROCESS $($f.Path) ? [y/N/skip] " -NoNewline -ForegroundColor Yellow
            $key = [Console]::ReadKey($true).KeyChar
            Write-Host $key
            if ($key -ne 'y') {
                Write-Host "    Skipped." -ForegroundColor DarkGray
                continue
            }
        }

        if ($WhatIf) {
            Write-Host "  [WhatIf] Would process $($f.Path) with $($f.Prompt.PromptFile)" -ForegroundColor DarkGray
            continue
        }

        Write-Host "  To compile: $($f.Path)"
        Write-Host "    Run: Read the file, apply $($f.Prompt.PromptFile), write output to $($f.Prompt.OutputDir)/"
        Write-Host "    (LLM invocation requires manual execution via Claude Code)"
    }

    # ── Eval gate ────────────────────────────────────────
    Write-Host ""
    Write-Host "--- Eval Gate ---" -ForegroundColor Cyan
    $evalScript = Join-Path $vaultRoot "scripts/eval.ps1"
    if (Test-Path $evalScript) {
        Write-Host "Running eval.ps1 ..."
        $evalResult = & $evalScript -Json 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Eval FAILED — compilation not ready for delivery" -ForegroundColor Red
            Write-Host "Fix the failing cases and re-run compile." -ForegroundColor Yellow
            exit 1
        } else {
            Write-Host "Eval PASSED — compilation ready" -ForegroundColor Green
        }
    } else {
        Write-Host "eval.ps1 not found — skipping eval gate" -ForegroundColor DarkGray
    }
}

# ── Update state ────────────────────────────────────────

if (-not $WhatIf -and -not $Json) {
    $newState = @{
        lastCompile = (Get-Date).ToUniversalTime().ToString("o")
        files       = @{}
    }

    $scanResult = Get-ChangedFiles -State @{ lastCompile = $null; files = @{} }
    foreach ($f in ($scanResult.changed + $scanResult.unchanged)) {
        $newState.files | Add-Member -MemberType NoteProperty -Name $f.Path -Value @{
            lastProcessed = $f.LastWrite
            hash          = $f.Hash
        }
    }

    Save-State -State $newState
    Write-Host ""
    Write-Host "Compile state updated." -ForegroundColor Green
}

if (-not $Json) {
    Write-Host ""
    Write-Host "Done." -ForegroundColor Cyan
}
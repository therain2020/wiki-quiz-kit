param(
    [switch]$Strict,
    [switch]$Verbose,
    [switch]$Json
)

$vaultRoot = Split-Path -Parent $PSScriptRoot
$errors = @()
$warnings = @()

# ── Helpers ──────────────────────────────────────────────

function Get-MarkdownFiles {
    param([string]$Under)
    $path = if ($Under) { Join-Path $vaultRoot $Under } else { $vaultRoot }
    Get-ChildItem -Path $path -Filter "*.md" -Recurse -File | Where-Object {
        $_.FullName -notmatch '[\\/]\.obsidian[\\/]' -and
        $_.FullName -notmatch '[\\/]\.trash[\\/]' -and
        $_.FullName -notmatch '[\\/]templates[\\/]' -and
        $_.FullName -notmatch '[\\/]prompts[\\/]' -and
        $_.DirectoryName -ne $vaultRoot
    }
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

function Get-NoteBody {
    param([string]$Content)
    if ($Content -match '^---\s*\r?\n.*?\r?\n---\s*\r?\n(.*)') {
        return $matches[1].Trim()
    }
    return $Content.Trim()
}

function Resolve-NotePath {
    param([string]$LinkTarget)
    $candidate = Join-Path $vaultRoot "$LinkTarget.md"
    if (Test-Path $candidate) { return $candidate }

    $allFiles = Get-MarkdownFiles
    $match = $allFiles | Where-Object { $_.BaseName -eq $LinkTarget }
    if ($match) { return $match.FullName }

    return $null
}

function Get-RelativePath {
    param([string]$FullPath)
    return $FullPath.Replace($vaultRoot + '\', '').Replace('\', '/')
}

# ── Check 1: Broken Wiki-Links ──────────────────────────

function Test-BrokenLinks {
    $result = @()
    $files = Get-MarkdownFiles
    foreach ($file in $files) {
        $content = Get-Content -Path $file.FullName -Raw -Encoding UTF8
        $links = Get-WikiLinks -Content $content
        foreach ($link in $links) {
            $resolved = Resolve-NotePath -LinkTarget $link
            if (-not $resolved) {
                $result += @{
                    Type    = "error"
                    Check   = "broken-link"
                    File    = Get-RelativePath $file.FullName
                    Target  = $link
                    Message = "Broken link: [[$link]]"
                }
            }
        }
    }
    return $result
}

# ── Check 2: Orphan Notes ───────────────────────────────

function Test-OrphanNotes {
    $result = @()
    $allFiles = Get-MarkdownFiles
    $allPaths = @{}
    foreach ($f in $allFiles) { $allPaths[$f.FullName] = $true }

    $referenced = @{}
    foreach ($file in $allFiles) {
        $content = Get-Content -Path $file.FullName -Raw -Encoding UTF8
        $links = Get-WikiLinks -Content $content
        foreach ($link in $links) {
            $resolved = Resolve-NotePath -LinkTarget $link
            if ($resolved) { $referenced[$resolved] = $true }
        }
    }

    $wikiFiles = $allFiles | Where-Object {
        $_.FullName -match '[\\/]wiki[\\/]' -and
        $_.FullName -notmatch '[\\/]wiki[\\/]daily[\\/]' -and
        $_.FullName -notmatch '[\\/]wiki[\\/]moc[\\/]'
    }

    $cutoff = (Get-Date).AddHours(-24)
    foreach ($file in $wikiFiles) {
        if (-not $referenced.ContainsKey($file.FullName) -and $file.LastWriteTime -lt $cutoff) {
            $fm = Get-Frontmatter (Get-Content -Path $file.FullName -Raw -Encoding UTF8)
            $result += @{
                Type    = "warning"
                Check   = "orphan"
                File    = Get-RelativePath $file.FullName
                Message = "Orphan note: no incoming links"
            }
        }
    }
    return $result
}

# ── Check 3: Empty Files ────────────────────────────────

function Test-EmptyFiles {
    $result = @()
    $files = Get-MarkdownFiles -Under "wiki"
    foreach ($file in $files) {
        $content = Get-Content -Path $file.FullName -Raw -Encoding UTF8
        $body = Get-NoteBody -Content $content
        if (-not $body) {
            $result += @{
                Type    = "error"
                Check   = "empty-file"
                File    = Get-RelativePath $file.FullName
                Message = "Empty file: no body content beyond frontmatter"
            }
        }
    }
    return $result
}

# ── Check 4: Frontmatter Consistency ────────────────────

$requiredFields = @{
    "permanent"  = @("type", "tags", "created")
    "literature" = @("type", "source", "created")
    "daily"      = @("type", "created")
    "moc"        = @("type", "tags", "created")
    "fleeting"   = @("type", "created")
    "meeting"    = @("type", "date")
    "video"      = @("type", "source", "created")
    "article"    = @("type", "source", "created")
    "question"   = @("type", "topic", "source", "difficulty", "created")
}

function Test-Frontmatter {
    $result = @()
    $files = Get-MarkdownFiles
    foreach ($file in $files) {
        $content = Get-Content -Path $file.FullName -Raw -Encoding UTF8
        $fm = Get-Frontmatter -Content $content
        $type = if ($fm.ContainsKey('type')) { $fm['type'] } else { $null }

        if (-not $type) {
            $result += @{
                Type    = "error"
                Check   = "frontmatter"
                File    = Get-RelativePath $file.FullName
                Message = "Missing 'type' field in frontmatter"
            }
            continue
        }

        if (-not $requiredFields.ContainsKey($type)) { continue }

        $required = $requiredFields[$type]
        $missing = $required | Where-Object { -not $fm.ContainsKey($_) -or $fm[$_] -eq '' }
        foreach ($m in $missing) {
            $result += @{
                Type    = "error"
                Check   = "frontmatter"
                File    = Get-RelativePath $file.FullName
                Message = "Missing required field '$m' for type '$type'"
            }
        }
    }
    return $result
}

# ── Check 5: Symmetric Links (Strict only) ──────────────

function Test-SymmetricLinks {
    $result = @()
    $files = Get-MarkdownFiles -Under "wiki/permanent"
    $fileSet = @{}
    foreach ($f in $files) { $fileSet[$f.FullName] = $true }

    foreach ($file in $files) {
        $content = Get-Content -Path $file.FullName -Raw -Encoding UTF8
        $links = Get-WikiLinks -Content $content
        foreach ($link in $links) {
            $resolved = Resolve-NotePath -LinkTarget $link
            if ($resolved -and $fileSet.ContainsKey($resolved)) {
                $targetContent = Get-Content -Path $resolved -Raw -Encoding UTF8
                $baseName = [System.IO.Path]::GetFileNameWithoutExtension($file.FullName)
                $backLinks = Get-WikiLinks -Content $targetContent
                if ($baseName -notin $backLinks) {
                    $result += @{
                        Type    = "warning"
                        Check   = "symmetric-link"
                        File    = Get-RelativePath $file.FullName
                        Target  = Get-RelativePath $resolved
                        Message = "Links to [[$(Get-RelativePath $resolved)]] but no backlink"
                    }
                }
            }
        }
    }
    return $result
}

# ── Check 6: Question Bank Integrity ─────────────────────

function Test-QuestionBank {
    $result = @()
    $qDir = Join-Path $vaultRoot "questions"
    if (-not (Test-Path $qDir)) {
        $result += @{
            Type    = "warning"
            Check   = "question-bank"
            File    = "questions/"
            Message = "Question bank directory does not exist. Run ingest to generate questions."
        }
        return $result
    }
    $qFiles = Get-ChildItem -Path $qDir -Filter "*.md" -File | Where-Object { $_.Name -ne "INDEX.md" }
    if ($qFiles.Count -lt 5) {
        $result += @{
            Type    = "warning"
            Check   = "question-bank"
            File    = "questions/"
            Message = "Question bank has only $($qFiles.Count) questions (minimum 5 recommended). Run backfill or ingest more content."
        }
    }
    $indexFile = Join-Path $qDir "INDEX.md"
    if (-not (Test-Path $indexFile)) {
        $result += @{
            Type    = "error"
            Check   = "question-bank"
            File    = "questions/INDEX.md"
            Message = "INDEX.md is missing. Run ingest to regenerate the index."
        }
    }
    return $result
}

# ── Main ────────────────────────────────────────────────

Write-Host "=== Knowledge Base Health Check ===" -ForegroundColor Cyan
Write-Host "Vault: $vaultRoot`n"

$allErrors = @()
$allWarnings = @()

# Run checks
Write-Host "[1/6] Broken Wiki-Links ............... " -NoNewline
$r1 = Test-BrokenLinks
$allErrors += $r1
Write-Host "$($r1.Count) issues" -ForegroundColor $(if ($r1.Count -gt 0) { 'Red' } else { 'Green' })

Write-Host "[2/6] Orphan Notes .................... " -NoNewline
$r2 = Test-OrphanNotes
$allWarnings += $r2
Write-Host "$($r2.Count) issues" -ForegroundColor $(if ($r2.Count -gt 0) { 'Yellow' } else { 'Green' })

Write-Host "[3/6] Empty Files ..................... " -NoNewline
$r3 = Test-EmptyFiles
$allErrors += $r3
Write-Host "$($r3.Count) issues" -ForegroundColor $(if ($r3.Count -gt 0) { 'Red' } else { 'Green' })

Write-Host "[4/6] Frontmatter Consistency ......... " -NoNewline
$r4 = Test-Frontmatter
$allErrors += $r4
Write-Host "$($r4.Count) issues" -ForegroundColor $(if ($r4.Count -gt 0) { 'Red' } else { 'Green' })

if ($Strict) {
    Write-Host "[5/6] Symmetric Links ................. " -NoNewline
    $r5 = Test-SymmetricLinks
    $allWarnings += $r5
    Write-Host "$($r5.Count) issues" -ForegroundColor $(if ($r5.Count -gt 0) { 'Yellow' } else { 'Green' })
} else {
    Write-Host "[5/6] Symmetric Links ................. skipped (use -Strict)" -ForegroundColor DarkGray
}

Write-Host "[6/6] Question Bank Integrity ......... " -NoNewline
$r6 = Test-QuestionBank
$allErrors += ($r6 | Where-Object { $_.Type -eq 'error' })
$allWarnings += ($r6 | Where-Object { $_.Type -eq 'warning' })
Write-Host "$($r6.Count) issues" -ForegroundColor $(if ($r6.Count -gt 0) { 'Yellow' } else { 'Green' })

Write-Host ""

# ── Output ──────────────────────────────────────────────

$issueCount = $allErrors.Count + $allWarnings.Count

if ($Verbose -and $issueCount -gt 0) {
    Write-Host "--- Details ---" -ForegroundColor Cyan
    foreach ($e in ($allErrors + $allWarnings)) {
        $color = if ($e.Type -eq 'error') { 'Red' } else { 'Yellow' }
        $tag   = if ($e.Type -eq 'error') { 'ERROR' } else { 'WARN ' }
        Write-Host "  [$tag] $($e.File): $($e.Message)" -ForegroundColor $color
    }
    Write-Host ""
}

$allMdFiles = Get-MarkdownFiles
Write-Host "Summary: $($allErrors.Count) errors, $($allWarnings.Count) warnings, $($allMdFiles.Count) notes scanned" -ForegroundColor Cyan

if ($Json) {
    $output = @{
        errors   = $allErrors.Count
        warnings = $allWarnings.Count
        notes    = $allMdFiles.Count
        details  = @($allErrors; $allWarnings)
    }
    $output | ConvertTo-Json -Depth 3 | Write-Output
}

exit $(if ($allErrors.Count -gt 0) { 1 } else { 0 })

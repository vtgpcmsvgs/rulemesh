[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("surge", "mihomo", "all")]
    [string]$Target
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$baseDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$sourcePath = Join-Path $baseDir "private_subscription_direct.list"
$browserProcessNames = @(
    "chrome.exe"
    "Google Chrome"
    "com.android.chrome"
    "Safari"
    "com.apple.WebKit.Networking"
    "Microsoft Edge"
    "msedge.exe"
    "Firefox"
    "firefox.exe"
)
$surgeBrowserComment = "shared endpoint browser proxy rules (auto-synced, keep before direct)"
$surgeDirectComment = "endpoint roles: SUBSCRIPTION=DIRECT, WEBSITE=proxy, SHARED=browser proxy/client direct"
$mihomoProxyComment = "endpoint roles: SUBSCRIPTION=DIRECT, WEBSITE/SHARED=proxy; provider downloads remain DIRECT"

if (-not (Test-Path $sourcePath)) {
    throw "Missing private subscription source file: $sourcePath"
}

function Read-Utf8NoBom {
    param([Parameter(Mandatory = $true)][string]$Path)
    return [System.IO.File]::ReadAllText($Path, [System.Text.UTF8Encoding]::new($false))
}

function Write-Utf8NoBom {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Content
    )
    [System.IO.File]::WriteAllText($Path, $Content, [System.Text.UTF8Encoding]::new($false))
}

function Normalize-CommentText {
    param([Parameter(Mandatory = $true)][string]$Line)
    $trimmed = $Line.Trim()
    if ($trimmed.StartsWith("//")) {
        return $trimmed.Substring(2).Trim()
    }
    return $trimmed.Substring(1).Trim()
}

function Normalize-RuleText {
    param([Parameter(Mandatory = $true)][string]$Rule)
    $parts = $Rule.Split(",")
    if ($parts.Length -ne 2) {
        throw "Source rules must contain exactly type and value."
    }
    $ruleType = $parts[0].Trim().ToUpperInvariant()
    $ruleValue = $parts[1].Trim()
    if ($ruleType -notin @("DOMAIN", "DOMAIN-SUFFIX", "IP-CIDR", "IP-CIDR6")) {
        throw "Unsupported source rule type."
    }
    if (-not $ruleValue) {
        throw "Empty source rule value."
    }
    if ($ruleType -eq "DOMAIN" -or $ruleType -eq "DOMAIN-SUFFIX") {
        try { $ruleValue = ([System.Globalization.IdnMapping]::new()).GetAscii($ruleValue.TrimEnd('.')).ToLowerInvariant() }
        catch { throw "Invalid endpoint domain." }
        if ([Uri]::CheckHostName($ruleValue) -ne [UriHostNameType]::Dns) { throw "Invalid endpoint domain." }
    }
    if ($ruleType -eq "IP-CIDR" -and $ruleValue -notmatch "/") {
        $ruleValue = "$ruleValue/32"
    }
    elseif ($ruleType -eq "IP-CIDR6" -and $ruleValue -notmatch "/") {
        $ruleValue = "$ruleValue/128"
    }
    return "$ruleType,$ruleValue"
}

function Get-DirectRuleText {
    param([Parameter(Mandatory = $true)][string]$Rule)
    $parts = $Rule.Split(",")
    if ($parts[0] -eq "IP-CIDR" -or $parts[0] -eq "IP-CIDR6") {
        return "$Rule,DIRECT,no-resolve"
    }
    return "$Rule,DIRECT"
}

function Get-ProxyRuleText {
    param(
        [Parameter(Mandatory = $true)][string]$Rule,
        [Parameter(Mandatory = $true)][string]$ProxyPolicy,
        [Parameter(Mandatory = $true)][ValidateSet("surge", "mihomo")][string]$Mode
    )
    $parts = $Rule.Split(",")
    $policy = if ($Mode -eq "surge") { '"' + $ProxyPolicy + '"' } else { $ProxyPolicy }
    if ($parts[0] -eq "IP-CIDR" -or $parts[0] -eq "IP-CIDR6") {
        return "$Rule,$policy,no-resolve"
    }
    return "$Rule,$policy"
}

function Get-PrivateEntries {
    param([Parameter(Mandatory = $true)][string]$Path)
    $entries = [System.Collections.Generic.List[object]]::new()
    $seenRules = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($line in [System.IO.File]::ReadAllLines($Path, [System.Text.UTF8Encoding]::new($false))) {
        $trimmed = $line.Trim()
        if (-not $trimmed) {
            if ($entries.Count -gt 0 -and $entries[$entries.Count - 1].Type -ne "blank") {
                $entries.Add([PSCustomObject]@{ Type = "blank" })
            }
            continue
        }
        if ($trimmed.StartsWith("#") -or $trimmed.StartsWith("//") -or $trimmed.StartsWith(";")) {
            $commentText = Normalize-CommentText -Line $trimmed
            if ($commentText) {
                $entries.Add([PSCustomObject]@{ Type = "comment"; Text = $commentText })
            }
            continue
        }
        $fields = $trimmed.Split(',')
        if ($fields.Length -lt 2 -or $fields.Length -gt 3) { throw "Invalid endpoint field count." }
        $role = if ($fields.Length -eq 3) { $fields[2].Trim().ToUpperInvariant() } else { "SHARED" }
        if ($role -notin @("SUBSCRIPTION", "WEBSITE", "SHARED")) { throw "Invalid endpoint role." }
        $normalizedRule = Normalize-RuleText -Rule ($fields[0].Trim() + ',' + $fields[1].Trim())
        if (-not $seenRules.Add($normalizedRule)) {
            throw "Duplicate private endpoint rule."
        }
        $entries.Add([PSCustomObject]@{ Type = "rule"; Rule = $normalizedRule; Role = $role })
    }
    if (-not ($entries | Where-Object { $_.Type -eq "rule" })) {
        throw "Private subscription source file is empty: $Path"
    }
    return $entries
}

function Add-SourceEntries {
    param(
        [System.Collections.Generic.List[string]]$Lines,
        [Parameter(Mandatory = $true)][object[]]$Entries,
        [Parameter(Mandatory = $true)][AllowEmptyString()][string]$Prefix,
        [Parameter(Mandatory = $true)][ValidateSet("surge-browser", "surge-direct", "mihomo-proxy")][string]$Style,
        [Parameter(Mandatory = $true)][string]$ProxyPolicy
    )
    $pending = [System.Collections.Generic.List[string]]::new()
    foreach ($entry in $Entries) {
        if ($entry.Type -eq "blank") { $pending.Add(""); continue }
        if ($entry.Type -eq "comment") { $pending.Add("$Prefix# $($entry.Text)"); continue }
        if ($Style -eq "surge-browser" -and $entry.Role -ne "SHARED") {
            $pending.Clear()
            continue
        }
        foreach ($pendingLine in $pending) {
            if ($pendingLine -ne "" -or $Lines[$Lines.Count - 1] -ne "") { $Lines.Add($pendingLine) }
        }
        $pending.Clear()
        if ($Style -eq "surge-browser") {
            foreach ($processName in $browserProcessNames) {
                $Lines.Add(('AND,((PROCESS-NAME,{0}),({1})),{2}' -f $processName, $entry.Rule, $ProxyPolicy))
            }
        }
        elseif ($Style -eq "surge-direct") {
            if ($entry.Role -eq "WEBSITE") {
                $Lines.Add((Get-ProxyRuleText -Rule $entry.Rule -ProxyPolicy $ProxyPolicy -Mode surge))
            }
            else { $Lines.Add((Get-DirectRuleText -Rule $entry.Rule)) }
        }
        elseif ($entry.Role -eq "SUBSCRIPTION") {
            $Lines.Add("$Prefix- $(Get-DirectRuleText -Rule $entry.Rule)")
        }
        else {
            $Lines.Add("$Prefix- $(Get-ProxyRuleText -Rule $entry.Rule -ProxyPolicy $ProxyPolicy -Mode mihomo)")
        }
    }
}

function Build-ReplacementBlock {
    param(
        [Parameter(Mandatory = $true)][object[]]$Entries,
        [Parameter(Mandatory = $true)][string]$ProxyPolicy,
        [Parameter(Mandatory = $true)][ValidateSet("surge", "mihomo")][string]$Mode,
        [Parameter(Mandatory = $true)][string]$NewLine
    )
    $lines = [System.Collections.Generic.List[string]]::new()
    if ($Mode -eq "surge") {
        $lines.Add("# >>> PRIVATE_SUBSCRIPTION_DIRECT_START")
        $lines.Add("# $surgeBrowserComment")
        Add-SourceEntries -Lines $lines -Entries $Entries -Prefix "" -Style surge-browser -ProxyPolicy $ProxyPolicy
        $lines.Add("")
        $lines.Add("# $surgeDirectComment")
        Add-SourceEntries -Lines $lines -Entries $Entries -Prefix "" -Style surge-direct -ProxyPolicy $ProxyPolicy
        $lines.Add("# <<< PRIVATE_SUBSCRIPTION_DIRECT_END")
    }
    else {
        $lines.Add("  # >>> PRIVATE_SUBSCRIPTION_DIRECT_START")
        $lines.Add("  # $mihomoProxyComment")
        Add-SourceEntries -Lines $lines -Entries $Entries -Prefix "  " -Style mihomo-proxy -ProxyPolicy $ProxyPolicy
        $lines.Add("  # <<< PRIVATE_SUBSCRIPTION_DIRECT_END")
    }
    return ($lines -join $NewLine)
}

function Get-EndpointProxyPolicy {
    param(
        [Parameter(Mandatory = $true)][string]$Content,
        [Parameter(Mandatory = $true)][ValidateSet("surge", "mihomo")][string]$Mode,
        [Parameter(Mandatory = $true)][string]$Path
    )
    $sectionPattern = if ($Mode -eq "surge") { '(?ms)^\[Rule\]\r?\n(?<body>.*?)(?=^\[[^]\r\n]+\]\r?$|\z)' } else { '(?ms)^rules:\r?\n(?<body>.*?)(?=^[a-zA-Z][a-zA-Z0-9_-]*:|\z)' }
    $sections = [regex]::Matches($Content, $sectionPattern)
    if ($sections.Count -ne 1) { throw "Rules section must be unique." }
    $ruleContent = $sections[0].Groups['body'].Value
    $patterns = if ($Mode -eq "surge") {
        @(
            '(?m)^RULE-SET,https://raw\.githubusercontent\.com/.*/proxy/onepassword_proxy\.list,"([^"]+)"',
            '(?m)^RULE-SET,https://raw\.githubusercontent\.com/.*/proxy/gfw(?:_precise)?\.list,"([^"]+)"'
        )
    }
    else {
        @(
            '(?m)^\s*-\s*RULE-SET,proxy_onepassword,(.+?)\s*$',
            '(?m)^\s*-\s*RULE-SET,proxy_gfw(?:_precise)?,(.+?)\s*$'
        )
    }
    foreach ($pattern in $patterns) {
        $matches = [System.Text.RegularExpressions.Regex]::Matches($ruleContent, $pattern)
        if ($matches.Count -gt 1) { throw "Endpoint policy anchor must be unique." }
        if ($matches.Count -eq 1) { return $matches[0].Groups[1].Value.Trim() }
    }
    throw "Endpoint proxy policy not found in: $Path"
}

function Sync-Block {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][ValidateSet("surge", "mihomo")][string]$Mode,
        [Parameter(Mandatory = $true)][object[]]$Entries
    )
    if (-not (Test-Path $Path)) { throw "Missing target config file: $Path" }
    $content = Read-Utf8NoBom -Path $Path
    $newLine = "`n"
    $proxyPolicy = Get-EndpointProxyPolicy -Content $content -Mode $Mode -Path $Path
    $replacement = Build-ReplacementBlock -Entries $Entries -ProxyPolicy $proxyPolicy -Mode $Mode -NewLine $newLine
    $pattern = if ($Mode -eq "surge") {
        '(?ms)^# >>> PRIVATE_SUBSCRIPTION_DIRECT_START\r?\n.*?^# <<< PRIVATE_SUBSCRIPTION_DIRECT_END'
    }
    else {
        '(?ms)^  # >>> PRIVATE_SUBSCRIPTION_DIRECT_START\r?\n.*?^  # <<< PRIVATE_SUBSCRIPTION_DIRECT_END'
    }
    $regex = [System.Text.RegularExpressions.Regex]::new($pattern)
    $startPattern = '(?m)^\s*# >>> PRIVATE_SUBSCRIPTION_DIRECT_START\r?$'
    $endPattern = '(?m)^\s*# <<< PRIVATE_SUBSCRIPTION_DIRECT_END\r?$'
    if ([regex]::Matches($content, $startPattern).Count -ne 1 -or [regex]::Matches($content, $endPattern).Count -ne 1 -or $regex.Matches($content).Count -ne 1) {
        throw "Sync markers must be complete and unique."
    }
    $sectionPattern = if ($Mode -eq "surge") { '(?ms)^\[Rule\]\r?\n(?<body>.*?)(?=^\[[^]\r\n]+\]\r?$|\z)' } else { '(?ms)^rules:\r?\n(?<body>.*?)(?=^[a-zA-Z][a-zA-Z0-9_-]*:|\z)' }
    $sections = [regex]::Matches($content, $sectionPattern)
    if ($sections.Count -ne 1 -or -not $regex.IsMatch($sections[0].Groups['body'].Value)) { throw "Sync block must be inside the unique rules section." }
    $updated = $regex.Replace($content, [System.Text.RegularExpressions.MatchEvaluator]{ param($match) $replacement }, 1)
    return [PSCustomObject]@{ Path = $Path; Original = $content; Updated = $updated }
}

$entries = Get-PrivateEntries -Path $sourcePath
$ruleCount = @($entries | Where-Object { $_.Type -eq "rule" }).Count
$targets = @()
if ($Target -eq "surge" -or $Target -eq "all") {
    $targets += @{ Path = (Join-Path $baseDir "rulemesh-substore-surge-personal.conf"); Mode = "surge" }
    $targets += @{ Path = (Join-Path $baseDir "rulemesh-substore-surge-personal-company.conf"); Mode = "surge" }
    $targets += @{ Path = (Join-Path $baseDir "rulemesh-substore-surge-work-whitelist.conf"); Mode = "surge" }
}
if ($Target -eq "mihomo" -or $Target -eq "all") {
    $targets += @{ Path = (Join-Path $baseDir "rulemesh-substore-mihomo-flclash-desktop.yaml"); Mode = "mihomo" }
    $targets += @{ Path = (Join-Path $baseDir "rulemesh-substore-mihomo-flclash-android.yaml"); Mode = "mihomo" }
}
$plans = @(
    foreach ($targetConfig in $targets) {
        Sync-Block -Path $targetConfig.Path -Mode $targetConfig.Mode -Entries $entries
    }
)
foreach ($plan in $plans) {
    if ((Read-Utf8NoBom -Path $plan.Path) -cne $plan.Original) { throw "Target changed during preflight." }
}
foreach ($plan in $plans) {
    Write-Utf8NoBom -Path $plan.Path -Content $plan.Updated
    Write-Host ("[sync_private_subscription_direct] synced {0}" -f $plan.Path)
}
Write-Host ("[sync_private_subscription_direct] synced {0} endpoint rules for target={1}." -f $ruleCount, $Target)

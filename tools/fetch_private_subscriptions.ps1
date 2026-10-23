param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$requestData = [Console]::In.ReadToEnd() | ConvertFrom-Json
$globalDeadline = [Threading.CancellationTokenSource]::new()
$globalDeadline.CancelAfter([Math]::Min(60000, [int]$requestData.budgetMs))
$handler = [Net.Http.SocketsHttpHandler]::new()
$handler.UseProxy = $false
$handler.AllowAutoRedirect = $false
$handler.ConnectTimeout = [TimeSpan]::FromSeconds(5)
$client = [Net.Http.HttpClient]::new($handler)
$client.Timeout = [Threading.Timeout]::InfiniteTimeSpan
$client.MaxResponseContentBufferSize = 20971520
$jobs = @()
$rows = @()
try {
    foreach ($provider in $requestData.providers) {
        $deadline = [Threading.CancellationTokenSource]::CreateLinkedTokenSource($globalDeadline.Token)
        $deadline.CancelAfter(10000)
        $request = [Net.Http.HttpRequestMessage]::new([Net.Http.HttpMethod]::Get, [uri]$provider.url)
        foreach ($agent in $provider.agent) {
            $null = $request.Headers.TryAddWithoutValidation('User-Agent', [string]$agent)
        }
        $jobs += @{ Name=$provider.name; Deadline=$deadline; Request=$request;
            Task=$client.SendAsync($request, [Net.Http.HttpCompletionOption]::ResponseContentRead, $deadline.Token) }
    }
    foreach ($job in $jobs) {
        $row = @{ name=$job.Name; status=$null; body=''; userinfo=''; error=$false }
        $response = $null
        try {
            $response = $job.Task.GetAwaiter().GetResult()
            $row.status = [int]$response.StatusCode
            if ($response.IsSuccessStatusCode) {
                $row.body = $response.Content.ReadAsStringAsync($job.Deadline.Token).GetAwaiter().GetResult()
            }
            $headerValues = [Collections.Generic.IEnumerable[string]]$null
            if ($response.Headers.TryGetValues('Subscription-Userinfo', [ref]$headerValues)) {
                $row.userinfo = $headerValues -join ';'
            }
        }
        catch { $row.error = $true }
        finally {
            if ($null -ne $response) { $response.Dispose() }
            $job.Request.Dispose()
            $job.Deadline.Dispose()
        }
        $rows += $row
    }
    ConvertTo-Json -InputObject @($rows) -Depth 5 -Compress
}
finally {
    $client.Dispose()
    $globalDeadline.Dispose()
}

param([Parameter(Mandatory=$true)][string]$InputPath,[Parameter(Mandatory=$true)][string]$OutputPath)
$ErrorActionPreference = 'Stop'
$source = (Resolve-Path -LiteralPath $InputPath).Path
if ([IO.Path]::GetExtension($source) -ne '.doc') { throw 'Only legacy .doc is supported' }
$word = $null
$document = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $word.AutomationSecurity = 3
    $document = $word.Documents.Open($source, $false, $true, $false)
    $items = @()
    $number = 0
    foreach ($paragraph in $document.Paragraphs) {
        $number++
        $text = $paragraph.Range.Text.Trim()
        if ($text.Length -gt 0) { $items += @{ text=$text; paragraph=$number; page=$paragraph.Range.Information(3) } }
    }
    ConvertTo-Json -InputObject $items -Depth 4 | Set-Content -LiteralPath $OutputPath -Encoding UTF8
} finally {
    if ($document) { $document.Close(0); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($document) }
    if ($word) { $word.Quit(); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($word) }
}

param(
    [string]$DocxPath = (Join-Path (Split-Path $PSScriptRoot -Parent) 'BAO_CAO_DO_AN.docx'),
    [string]$OutputDir = (Join-Path $PSScriptRoot 'word_qa')
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$docx = (Resolve-Path -LiteralPath $DocxPath).Path
if (-not (Test-Path -LiteralPath $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir | Out-Null
}
$output = (Resolve-Path -LiteralPath $OutputDir).Path
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$document = $null
try {
    $document = $word.Documents.Open($docx, $false, $true)
    $pages = $document.ActiveWindow.Panes.Item(1).Pages
    $count = $pages.Count
    for ($number = 1; $number -le $count; $number++) {
        $page = $pages.Item($number)
        $stream = New-Object System.IO.MemoryStream(,$page.EnhMetaFileBits)
        $metafile = New-Object System.Drawing.Imaging.Metafile($stream)
        $width = [int][math]::Round($page.Width * 2)
        $height = [int][math]::Round($page.Height * 2)
        $bitmap = New-Object System.Drawing.Bitmap($width, $height)
        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
        try {
            $graphics.Clear([System.Drawing.Color]::White)
            $graphics.DrawImage($metafile, 0, 0, $width, $height)
            $file = Join-Path $output ('page-{0:d3}.png' -f $number)
            $bitmap.Save($file, [System.Drawing.Imaging.ImageFormat]::Png)
        }
        finally {
            $graphics.Dispose()
            $bitmap.Dispose()
            $metafile.Dispose()
            $stream.Dispose()
        }
    }
    Write-Output "Rendered $count pages to $output"
}
finally {
    if ($null -ne $document) { $document.Close($false) }
    $word.Quit()
}

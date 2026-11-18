$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$documentPath = [IO.Path]::GetFullPath((Join-Path $taskRoot '../../output/documents/论文第四五章_复核修订稿_v2.docx'))
$pdfPath = Join-Path $taskRoot 'book.pdf'
$wordApp = $null
$wordDoc = $null
try {
    $wordApp = New-Object -ComObject Word.Application
    $wordApp.Visible = $false
    $wordApp.DisplayAlerts = 0
    $wordDoc = $wordApp.Documents.Open($documentPath)
    $wordDoc.Fields.Update() | Out-Null
    foreach ($toc in $wordDoc.TablesOfContents) { $toc.Update() }
    $wordDoc.Repaginate()
    foreach ($toc in $wordDoc.TablesOfContents) { $toc.UpdatePageNumbers() }
    $wordDoc.Save()
    $wordDoc.ExportAsFixedFormat($pdfPath, 17)
    Write-Output ('Pages: ' + $wordDoc.ComputeStatistics(2))
    Write-Output ('Equations: ' + $wordDoc.OMaths.Count)
    Write-Output ('PDF: ' + $pdfPath)
} finally {
    if ($null -ne $wordDoc) { $wordDoc.Close(0) }
    if ($null -ne $wordApp) { $wordApp.Quit() }
}


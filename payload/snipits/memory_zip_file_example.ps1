Add-Type -AssemblyName 'System.IO.Compression'
Add-Type -AssemblyName 'System.IO.Compression.FileSystem'

$zipFilePath = "output.zip"

$memoryStream = New-Object System.IO.MemoryStream

$zipArchive = [System.IO.Compression.ZipArchive]::new($memoryStream, [System.IO.Compression.ZipArchiveMode]::Create, $true)

$files = @(
    "path\to\file1.txt",
    "path\to\file2.txt",
)

foreach ($file in $files) {
    $entryName = [System.IO.Path]::GetFileName($file)
    $zipEntry = $zipArchive.CreateEntry($entryName)
    
    $zipStream = $zipEntry.Open()
    [System.IO.File]::OpenRead($file).CopyTo($zipStream)
    $zipStream.Close()
}

$zipArchive.Dispose()

$memoryStream.Seek(0, [System.IO.SeekOrigin]::Begin) | Out-Null
[System.IO.File]::WriteAllBytes($zipFilePath, $memoryStream.ToArray())

$memoryStream.Dispose()
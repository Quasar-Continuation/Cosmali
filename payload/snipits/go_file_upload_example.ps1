$file_location = "C:\Path\To\File\file.txt"

function Get-ApiUrl {
    $request = Invoke-WebRequest -Uri "https://api.gofile.io/servers" -Method Get -UseBasicParsing
    $json = $request.Content | ConvertFrom-Json
    $servers = $json.data.servers
    $server = $servers | Get-Random
    $name = $server.name
    return $name
}

function UploadFile {
    param(
        [string]$file
    )

    $server = Get-ApiUrl

    $boundary = [System.Guid]::NewGuid().ToString()
    $url = "https://$server.gofile.io/uploadFile"

    $fileContent = [System.IO.File]::ReadAllBytes($file)
    $fileName = [System.IO.Path]::GetFileName($file)

    $bodyLines = @(
        "--$boundary",
        "Content-Disposition: form-data; name=`"file`"; filename=`"$fileName`"",
        "Content-Type: application/octet-stream",
        "",
        [System.Text.Encoding]::UTF8.GetString($fileContent),
        "--$boundary--"
    )

    $body = $bodyLines -join "`r`n"

    $response = Invoke-WebRequest -Uri $url -Method Post -Body $body -ContentType "multipart/form-data; boundary=$boundary"

    $downloadUrl = $response.Content | ConvertFrom-Json

    return $downloadUrl.data.downloadPage
}

$out = UploadFile -file $file_location
Write-Output $out

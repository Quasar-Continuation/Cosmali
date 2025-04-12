$message = "Hello, World!"
$title = "KDOT"
$icon = "Information"
$buttons = "OK"

Add-Type -AssemblyName PresentationFramework

[System.Windows.MessageBox]::Show($message, $title, $buttons, $icon)
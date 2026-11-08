param(
    [string]$Exe = "",
    [string]$Src = ""
)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$script = Join-Path $here 'verify_anchors.py'
$argv = @($script)
if ($Exe) { $argv += $Exe }
if ($Src) { $argv += $Src }
& python @argv
exit $LASTEXITCODE

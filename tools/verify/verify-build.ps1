param(
    [Parameter(Mandatory = $true)][string]$Dll
)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not (Test-Path $Dll)) { Write-Error "not found: $Dll"; exit 2 }

& python (Join-Path $here 'inspect_dll.py') $Dll
if ($LASTEXITCODE -ne 0) { exit 1 }

& python (Join-Path $here 'check_dll_constants.py') $Dll
exit $LASTEXITCODE

param(
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]*$')]
    [string]$PiHost = 'pi'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ASCII prompts keep this file compatible with Windows PowerShell 5.1.
$piTarget = 'pi@' + $PiHost
$piLocalFolder = $PSScriptRoot
if ((Split-Path -Leaf $piLocalFolder) -ne 'Code_HopAp_Demo') {
    throw 'Giu script nay trong thu muc Code_HopAp_Demo.'
}
foreach ($piRequiredFile in @('thu_mach.py', 'thu_mach_12v.py', 'chay_thu_12v.sh')) {
    if (-not (Test-Path -LiteralPath (Join-Path $piLocalFolder $piRequiredFile))) {
        throw ('Thieu file: ' + $piRequiredFile)
    }
}
Get-Command ssh, scp -ErrorAction Stop | Out-Null

Write-Host ('Dich ket noi: ' + $piTarget)
Write-Host 'Giu adapter 12 V dang rut, Pi duoc cap USB-C.'
Write-Host 'Nhap mat khau truc tiep trong Terminal khi SSH/SCP hoi.'
Write-Host 'Dang chep thu muc...'
$piCopyTarget = $piTarget + ':/home/pi/'
Push-Location -LiteralPath (Split-Path -Parent $piLocalFolder)
try {
    & scp -o ConnectTimeout=10 -r '.\Code_HopAp_Demo' $piCopyTarget
    $piCopyExitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}
if ($piCopyExitCode -ne 0) {
    throw 'SCP chua thanh cong. Kiem tra IP/hostname, LAN/Wi-Fi va SSH truoc khi thu mach.'
}

Write-Host 'Da chep file. Dang mo phien SSH de cai/kiem tra thu vien va thu mach...'
& ssh -t -o ConnectTimeout=10 $piTarget 'bash /home/pi/Code_HopAp_Demo/chay_thu_12v.sh'
if ($LASTEXITCODE -ne 0) {
    throw 'Phien thu da dung hoac bi loi. Kiem tra ket qua tren Terminal; rut 12 V neu tai khong tat.'
}

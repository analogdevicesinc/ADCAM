<#
.SYNOPSIS
  Non-interactive CLI to list interfaces, remove IPv4 addresses, set Static/DHCP, verify, and show results.

SHORT USAGE
  .\set-ip.ps1                     # show this short help
  .\set-ip.ps1 -ShowInterfaces     # list adapters and IPv4 interfaces
  .\set-ip.ps1 -InterfaceAlias "Ethernet 3" -Mode Static -IPAddress 192.168.1.150 -PrefixLength 24 -Gateway 192.168.1.1 -DnsServers "8.8.8.8","8.8.4.4" -RemoveAllExistingIPs
  .\set-ip.ps1 -InterfaceAlias "Ethernet 3" -Mode DHCP -RemoveAllExistingIPs

NOTES
  - Non-interactive (no prompts). Use CLI switches only.
  - For operational actions the script requires Administrator elevation.
#>

param(
  [switch]$Help,
  [switch]$ShowInterfaces,

  [string]$InterfaceAlias,

  [ValidateSet("Static","DHCP")]
  [string]$Mode,

  [string]$IPAddress,
  [int]$PrefixLength = 24,
  [string]$Gateway,
  [string[]]$DnsServers,

  [switch]$RemoveAllExistingIPs,
  [switch]$NoVerify
)

function Show-Usage {
  Write-Host ""
  Write-Host "Usage (short):" -ForegroundColor Cyan
  Write-Host "  .\set-ip.ps1                         # show this help"
  Write-Host "  .\set-ip.ps1 -ShowInterfaces         # list adapters and IPv4 interfaces"
  Write-Host "  .\set-ip.ps1 -InterfaceAlias <name> -Mode Static -IPAddress <ip> -PrefixLength <len> -Gateway <gw> -DnsServers <dns1,dns2> -RemoveAllExistingIPs"
  Write-Host "  .\set-ip.ps1 -InterfaceAlias <name> -Mode DHCP -RemoveAllExistingIPs"
  Write-Host ""
  Write-Host "Notes: non-interactive; operational commands require Administrator."
  Write-Host ""
}

function Fail {
  param($Message, $Code = 1)
  Write-Error $Message
  exit $Code
}

# Show short usage if requested or if no meaningful operational parameter provided.
if ($Help -or -not ($ShowInterfaces -or $InterfaceAlias -or $Mode -or $IPAddress -or $DnsServers -or $RemoveAllExistingIPs -or $Gateway)) {
  Show-Usage
  exit 0
}

# Require admin for operational actions
if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
      [Security.Principal.WindowsBuiltInRole] "Administrator")) {
  Fail "This script must be run as Administrator for operational commands. Use -ShowInterfaces or -Help to avoid requiring elevation." 1
}

# Show interfaces and exit if requested
if ($ShowInterfaces) {
  Write-Host "Network adapters:" -ForegroundColor Cyan
  Get-NetAdapter | Format-Table -AutoSize ifIndex, Name, InterfaceDescription, Status
  Write-Host "`nIP Interfaces (IPv4):" -ForegroundColor Cyan
  Get-NetIPInterface -AddressFamily IPv4 | Format-Table -AutoSize InterfaceAlias, ifIndex, AddressFamily, Dhcp, InterfaceMetric
  exit 0
}

# Validate parameters for operational mode
if (-not $InterfaceAlias) {
  Fail "Parameter -InterfaceAlias is required for operational modes." 1
}
if (-not $Mode) {
  Fail "Parameter -Mode (Static or DHCP) is required." 1
}
if ($Mode -eq "Static" -and -not $IPAddress) {
  Fail "When -Mode Static, you must provide -IPAddress." 1
}

# Basic IPv4 validation helper
function Test-IPv4 {
  param($ip)
  try {
    $addr = [System.Net.IPAddress]::Parse($ip)
    return ($addr.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork)
  } catch {
    return $false
  }
}

if ($Mode -eq "Static") {
  if (-not (Test-IPv4 $IPAddress)) {
    Fail "Invalid IPv4 address provided for -IPAddress: '$IPAddress'" 1
  }
  if ($Gateway -and ($Gateway.Trim() -ne '') -and -not (Test-IPv4 $Gateway)) {
    Fail "Invalid IPv4 address provided for -Gateway: '$Gateway'" 1
  }
  if ($DnsServers) {
    foreach ($d in $DnsServers) {
      if (-not (Test-IPv4 $d)) { Fail "Invalid IPv4 address in -DnsServers: '$d'" 1 }
    }
  }
}

# Display selected interface summary
Write-Host "Selected interface summary:" -ForegroundColor Cyan
try {
  Get-NetAdapter -Name $InterfaceAlias -ErrorAction Stop | Format-Table -AutoSize ifIndex, Name, Status, MacAddress
  Get-NetIPInterface -InterfaceAlias $InterfaceAlias -AddressFamily IPv4 | Format-List *
  # suppress errors if none present
  Get-NetIPAddress -InterfaceAlias $InterfaceAlias -AddressFamily IPv4 -ErrorAction SilentlyContinue
}
catch {
  Fail "Failed to retrieve interface information for '$InterfaceAlias': $_" 1
}

# Remove all existing IPv4 addresses if requested
if ($RemoveAllExistingIPs) {
  Write-Host "`nRemoving existing IPv4 addresses on $($InterfaceAlias)..." -ForegroundColor Yellow
  $existing = Get-NetIPAddress -InterfaceAlias $InterfaceAlias -AddressFamily IPv4 -ErrorAction SilentlyContinue
  if ($existing) {
    foreach ($addr in $existing) {
      try {
        Write-Host "  Removing $($addr.IPAddress)/$($addr.PrefixLength) (PrefixOrigin: $($addr.PrefixOrigin))"
        Remove-NetIPAddress -InterfaceAlias $InterfaceAlias -IPAddress $addr.IPAddress -Confirm:$false -ErrorAction Stop
      }
      catch {
        Write-Warning "  Failed to remove $($addr.IPAddress): $_"
      }
    }
  }
  else {
    Write-Host "  No existing IPv4 addresses found." -ForegroundColor DarkGreen
  }
}

# Apply requested mode
try {
  if ($Mode -eq "DHCP") {
    Write-Host "`nEnabling DHCP for IPv4 on $($InterfaceAlias)..." -ForegroundColor Yellow
    Set-NetIPInterface -InterfaceAlias $InterfaceAlias -AddressFamily IPv4 -Dhcp Enabled -ErrorAction Stop
    Write-Host "Resetting DNS to DHCP..." -ForegroundColor Yellow
    Set-DnsClientServerAddress -InterfaceAlias $InterfaceAlias -ResetServerAddresses -ErrorAction Stop
  }
  else {
    Write-Host "`nDisabling DHCP for IPv4 on $($InterfaceAlias)..." -ForegroundColor Yellow
    Set-NetIPInterface -InterfaceAlias $InterfaceAlias -AddressFamily IPv4 -Dhcp Disabled -ErrorAction Stop

    Write-Host "Adding static IP $IPAddress/$PrefixLength" -ForegroundColor Yellow

    # Build parameters for New-NetIPAddress and include DefaultGateway only if provided
    $niaParams = @{
      InterfaceAlias = $InterfaceAlias
      IPAddress      = $IPAddress
      PrefixLength   = $PrefixLength
      ErrorAction    = 'Stop'
    }
    if ($Gateway -and $Gateway.Trim() -ne '') {
      $niaParams.DefaultGateway = $Gateway
    }

    # Add address if not already present
    $existsNow = Get-NetIPAddress -InterfaceAlias $InterfaceAlias -AddressFamily IPv4 -ErrorAction SilentlyContinue |
                 Where-Object { $_.IPAddress -eq $IPAddress }
    if (-not $existsNow) {
      New-NetIPAddress @niaParams
    }
    else {
      Write-Host "  Address $IPAddress already present, skipping New-NetIPAddress." -ForegroundColor DarkGreen
    }

    if ($DnsServers) {
      Write-Host "Setting DNS servers: $($DnsServers -join ', ')" -ForegroundColor Yellow
      Set-DnsClientServerAddress -InterfaceAlias $InterfaceAlias -ServerAddresses $DnsServers -ErrorAction Stop
    }
  }
}
catch {
  Fail "Failed to apply network settings: $_" 2
}

# Verification and results
Write-Host "`nFlushing DNS resolver cache..." -ForegroundColor Cyan
try { ipconfig /flushdns | Out-Null } catch {}

Write-Host "`nResulting IPv4 addresses on $($InterfaceAlias):" -ForegroundColor Cyan
$finalAddrs = Get-NetIPAddress -InterfaceAlias $InterfaceAlias -AddressFamily IPv4 -ErrorAction SilentlyContinue
if ($finalAddrs) {
  $finalAddrs | Format-Table -AutoSize IPAddress, PrefixLength, DefaultGateway, PrefixOrigin
} else {
  Write-Host "  (no IPv4 addresses found)" -ForegroundColor DarkYellow
}

Write-Host "`nInterface properties:" -ForegroundColor Cyan
Get-NetIPInterface -InterfaceAlias $InterfaceAlias -AddressFamily IPv4 | Format-List InterfaceAlias, AddressFamily, Dhcp, InterfaceMetric, Forwarding

if (-not $NoVerify) {
  Write-Host "`nVerifying outcome..." -ForegroundColor Cyan
  if ($Mode -eq "Static") {
    if ($finalAddrs -and ($finalAddrs | Where-Object { $_.IPAddress -eq $IPAddress })) {
      Write-Host "Verification: Static IP $IPAddress is present." -ForegroundColor Green
      exit 0
    } else {
      Fail "Verification failed: Static IP $IPAddress not found on interface." 3
    }
  }
  else {
    $ipif = Get-NetIPInterface -InterfaceAlias $InterfaceAlias -AddressFamily IPv4 -ErrorAction SilentlyContinue
    $dhcpEnabled = $false
    if ($ipif) {
      if ($ipif.Dhcp -eq "Enabled" -or $ipif.Dhcp -eq $true -or $ipif.Dhcp -eq "True") { $dhcpEnabled = $true }
    }
    if (-not $dhcpEnabled) {
      $dhcpFound = $finalAddrs | Where-Object { $_.PrefixOrigin -match "Dhcp" }
      if ($dhcpFound) { $dhcpEnabled = $true }
    }

    if ($dhcpEnabled) {
      Write-Host "Verification: DHCP is enabled/confirmed on interface." -ForegroundColor Green
      exit 0
    } else {
      Fail "Verification failed: DHCP not confirmed on interface." 3
    }
  }
}
else {
  Write-Host "Verification skipped ( -NoVerify )" -ForegroundColor Yellow
  exit 0
}

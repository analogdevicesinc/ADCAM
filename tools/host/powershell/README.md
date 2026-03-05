## Setting the IP address on a Windows Machine

We have provided a tool

```console
PS C:\tmp> .\set-ip.ps1 -ShowInterfaces
Network adapters:

ifIndex Name                         InterfaceDescription                     Status
------- ----                         --------------------                     ------
     23 Wi-Fi 5                      Intel(R) Wi-Fi 7 BE200 320MHz #3         Not Present
     22 Ethernet 2                   Realtek USB GbE Family Controller #2     Up
     16 Wi-Fi 2                      Intel(R) Wi-Fi 7 BE200 320MHz #3         Not Present
     13 Wi-Fi 4                      Intel(R) Wi-Fi 7 BE200 320MHz #3         Disconnected
     12 Wi-Fi                        Intel(R) Wi-Fi 7 BE200 320MHz #3         Disconnected
     61 Ethernet 3                   Realtek USB GbE Family Controller #3     Up
      8 Wi-Fi 3                      Intel(R) Wi-Fi 7 BE200 320MHz #3         Disconnected
      7 Bluetooth Network Connection Bluetooth Device (Personal Area Network) Disconnected
      5 Connect Tunnel               SonicWall VPN Adapter                    Disconnected



IP Interfaces (IPv4):

InterfaceAlias               ifIndex AddressFamily     Dhcp InterfaceMetric
--------------               ------- -------------     ---- ---------------
Ethernet 3                        61          IPv4 Disabled              25
vEthernet (Default Switch)        25          IPv4 Disabled              15
Ethernet 2                        22          IPv4  Enabled              25
Wi-Fi 4                           13          IPv4 Disabled              25
Wi-Fi 3                            8          IPv4  Enabled              25
Bluetooth Network Connection       7          IPv4  Enabled              65
Wi-Fi                             12          IPv4  Enabled              30
Connect Tunnel                     5          IPv4 Disabled               5
Loopback Pseudo-Interface 1        1          IPv4 Disabled              75
```

```console
PS C:\tmp> .\set-ip.ps1 -InterfaceAlias "Ethernet 3" -Mode Static -IPAddress 192.168.1.99 -PrefixLength 24 -DnsServers "8.8.8.8" -RemoveAllExistingIPs
```

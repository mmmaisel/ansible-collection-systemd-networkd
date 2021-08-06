# Ansible Collection systemd_networkd

An Ansible plugin to generate systemd-networkd configuration files.

XXX: usage

## Examples:
### Configure simple interface
```
- name: Configure eth0 with DHCP
  systemd_networkd:
    networks:
      eth0:
        mac: "00:11:22:33:44:55"
        dhcp: true
```

### Complex configuration
```
- name: Configure network
  systemd_networkd:
    networks:
      eth0:
        mac: "00:11:22:33:44:55"
        vlan:
          - { id: 1, bridge: br1 }
      br1:
        bridge: true
        address: "192.168.1.1/24"
```

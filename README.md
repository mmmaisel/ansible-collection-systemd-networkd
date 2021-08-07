# Ansible Collection systemd_networkd

An Ansible plugin to generate systemd-networkd configuration files.
Currently, it supports physical networks, bridges and VLANs.

## Installation
Download this collection from Ansible-Galaxy or copy the file
"plugins/modules/systemd_networkd.py" into your Ansible project root at
"library/modules/systemd_networkd.py".

## Usage Examples:
For full details about the options, see the documentation at the beginning of
the file "plugins/modules/systemd_networkd.py".

### Configure single interface with DHCP
```
- name: Configure eth0 with DHCP
  systemd_networkd:
    networks:
      - name: eth0
        mac: "00:11:22:33:44:55"
        dhcp: true
```

### Adjust systemd config file permissions
```
- name: Configure eth0 with DHCP
  systemd_networkd:
    mode: 0640
    owner: root
    group: users
    networks:
      - name: eth0
        mac: "00:11:22:33:44:55"
        dhcp: true
```

### Complex single interface statically
```
- name: Configure eth0 statically
  systemd_networkd:
    networks:
      - name: eth0
        mac: "00:11:22:33:44:55"
        address: "192.168.1.1/24"
        dns:
          - 1.1.1.1
          - 2.2.2.2
        gateway: "192.168.0.1"
```

### Two interfaces bridged together
```
- name: Configure bridge
  systemd_networkd:
    networks:
      - name: eth0
        mac: "00:11:22:33:44:55"
        bridge: br1

      - name: eth1
        mac: "00:11:22:33:44:56"
        bridge: br1

      - name: br1
        type: bridge
        address: "192.168.1.1/24"
```

### In interface with VLANs
```
- name: Configure interface with VLANs
  systemd_networkd:
    networks:
      - name: eth0
        mac: "00:11:22:33:44:55"
        vlan:
          - id: 1
            dhcp: true
          - id: 2
            name: vlan2
            address: "192.168.2.2/24"
            dns:
              - 1.1.1.1
              - 2.2.2.2
            gateway: "192.168.1.1"
```

### VLANs in a bridge
```
- name: Configure VLAN bridge
  systemd_networkd:
    networks:
      - name: eth0
        mac: "00:11:22:33:44:55"
        vlan:
          - { id: 1, bridge: br1 }
          - { id: 2, bridge: br1 }

      - name: br1
        type: bridge
        address: "192.168.1.1/24"
        dns:
          - 1.1.1.1
          - 2.2.2.2
        gateway: "192.168.1.1"
```

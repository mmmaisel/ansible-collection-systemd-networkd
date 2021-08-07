"""Unit tests for the 'generate_config' function from the
Ansible systemd_networkd module function"""

from systemd_networkd import generate_config

def with_defaults(args):
    """ Adds default values to arguments. """
    keys = ["name", "address", "bridge", "dhcp", "dns", "gateway", "mac",
        "type", "vlan"]
    for arg in args:
        for key in keys:
            if not key in arg:
                arg[key] = None

        if arg["vlan"] is not None:
            vlan_keys = [
                "id", "name", "address", "bridge", "dhcp", "dns", "gateway"
            ]
            for vlan in arg["vlan"]:
                for vkey in vlan_keys:
                    if not vkey in vlan:
                        vlan[vkey] = None

    return args

def test_simple_dhcp_config():
    """ Tests if a single interfaces is configured correctly with DHCP. """
    args = with_defaults([
        {
            "name": "eth0",
            "mac": "00:11:22:33:44:55",
            "dhcp": True
        }
    ])

    expected = {
        '10-eth0.link':
            '[Match]\n'
            'MACAddress=00:11:22:33:44:55\n'
            'Driver=!802.1Q*\n'
            '\n'
            '[Link]\n'
            'Name=eth0',
        '10-eth0.network':
            '[Match]\n'
            'Name=eth0\n'
            '\n'
            '[Network]\n'
            'DHCP=ipv4\n'
    }

    config = generate_config(args)
    assert expected == config

def test_multi_dhcp_config():
    """ Tests if two interfaces are configured correctly with DHCP. """
    args = with_defaults([
        {
            "name": "eth0",
            "mac": "00:11:22:33:44:55",
            "dhcp": True
        },
        {
            "name": "eth1",
            "mac": "00:11:22:33:44:56",
            "dhcp": True
        }
    ])

    expected = {
        '10-eth0.link':
            '[Match]\n'
            'MACAddress=00:11:22:33:44:55\n'
            'Driver=!802.1Q*\n'
            '\n'
            '[Link]\n'
            'Name=eth0',
        '10-eth0.network':
            '[Match]\n'
            'Name=eth0\n'
            '\n'
            '[Network]\n'
            'DHCP=ipv4\n',
        '10-eth1.link':
            '[Match]\n'
            'MACAddress=00:11:22:33:44:56\n'
            'Driver=!802.1Q*\n'
            '\n'
            '[Link]\n'
            'Name=eth1',
        '10-eth1.network':
            '[Match]\n'
            'Name=eth1\n'
            '\n'
            '[Network]\n'
            'DHCP=ipv4\n'
    }

    config = generate_config(args)
    assert expected == config

def test_simple_static_config():
    """ Tests if a single interfaces is configured correctly with
    static configuration. """
    args = with_defaults([
        {
            "name": "eth0",
            "mac": "00:11:22:33:44:55",
            "address": "192.168.1.2/24",
            "gateway": "192.168.1.1",
            "dns": [
                "1.1.1.1",
                "8.8.8.8"
            ]
        }
    ])

    expected = {
        '10-eth0.link':
            '[Match]\n'
            'MACAddress=00:11:22:33:44:55\n'
            'Driver=!802.1Q*\n'
            '\n'
            '[Link]\n'
            'Name=eth0',
        '10-eth0.network':
            '[Match]\n'
            'Name=eth0\n'
            '\n'
            '[Network]\n'
            'Address=192.168.1.2/24\n'
            'DNS=1.1.1.1\n'
            'DNS=8.8.8.8\n'
            'Gateway=192.168.1.1\n'
    }

    config = generate_config(args)
    assert expected == config

def test_vlan_bridge_configuration():
    """ Tests an interface is assigned to a bridge with an IP address
    correctly. """
    args = with_defaults([
        {
            "name": "eth0",
            "mac": "00:11:22:33:44:55",
            "vlan": [
                { "id": 1, "bridge": "br1" }
            ]
        },
        {
            "name": "br1",
            "type": "bridge",
            "address": "192.168.1.1/24"
        }
    ])

    expected = {
        '10-eth0.link':
            '[Match]\n'
            'MACAddress=00:11:22:33:44:55\n'
            'Driver=!802.1Q*\n'
            '\n'
            '[Link]\n'
            'Name=eth0',
        '10-eth0.network':
            '[Match]\n'
            'Name=eth0\n'
            '\n'
            '[Network]\n'
            'VLAN=eth0.1\n',
        '20-eth0.1.netdev':
            '[NetDev]\n'
            'Name=eth0.1\n'
            'Kind=vlan\n'
            '\n'
            '[VLAN]\n'
            'Id=1\n',
        '20-eth0.1.network':
            '[Match]\n'
            'Name=eth0.1\n'
            '\n'
            '[Network]\n'
            'Bridge=br1\n',
        '30-br1.netdev':
            '[NetDev]\n'
            'Name=br1\n'
            'Kind=bridge\n',
        '30-br1.network':
            '[Match]\n'
            'Name=br1\n'
            '\n'
            '[Network]\n'
            'Address=192.168.1.1/24\n'
    }

    config = generate_config(args)
    assert expected == config

def test_vlan_with_name_and_dhcp_configuration():
    """ Tests if custom VLAN names work. """
    args = with_defaults([
        {
            "name": "eth0",
            "mac": "00:11:22:33:44:55",
            "vlan": [
                { "id": 1, "name": "vlan1", "dhcp": True }
            ]
        }
    ])

    expected = {
        '10-eth0.link':
            '[Match]\n'
            'MACAddress=00:11:22:33:44:55\n'
            'Driver=!802.1Q*\n'
            '\n'
            '[Link]\n'
            'Name=eth0',
        '10-eth0.network':
            '[Match]\n'
            'Name=eth0\n'
            '\n'
            '[Network]\n'
            'VLAN=vlan1\n',
        '20-vlan1.netdev':
            '[NetDev]\n'
            'Name=vlan1\n'
            'Kind=vlan\n'
            '\n'
            '[VLAN]\n'
            'Id=1\n',
        '20-vlan1.network':
            '[Match]\n'
            'Name=vlan1\n'
            '\n'
            '[Network]\n'
            'DHCP=ipv4\n'
    }

    config = generate_config(args)
    assert expected == config

def test_vlan_with_name_and_static_configuration():
    """ Tests if static configuration work an a VLAN as well. """
    args = with_defaults([
        {
            "name": "eth0",
            "mac": "00:11:22:33:44:55",
            "vlan": [
                {
                    "id": 1,
                    "address": "192.168.1.2/24",
                    "dns": ["1.1.1.1", "8.8.8.8"],
                    "gateway": "192.168.1.1"
                }
            ]
        }
    ])

    expected = {
        '10-eth0.link':
            '[Match]\n'
            'MACAddress=00:11:22:33:44:55\n'
            'Driver=!802.1Q*\n'
            '\n'
            '[Link]\n'
            'Name=eth0',
        '10-eth0.network':
            '[Match]\n'
            'Name=eth0\n'
            '\n'
            '[Network]\n'
            'VLAN=eth0.1\n',
        '20-eth0.1.netdev':
            '[NetDev]\n'
            'Name=eth0.1\n'
            'Kind=vlan\n'
            '\n'
            '[VLAN]\n'
            'Id=1\n',
        '20-eth0.1.network':
            '[Match]\n'
            'Name=eth0.1\n'
            '\n'
            '[Network]\n'
            'Address=192.168.1.2/24\n'
            'DNS=1.1.1.1\n'
            'DNS=8.8.8.8\n'
            'Gateway=192.168.1.1\n'
    }

    config = generate_config(args)
    assert expected == config

def test_multi_vlan_configuration():
    """ Tests if two VLANs can be assigned two one interface correctly. """
    args = with_defaults([
        {
            "name": "eth0",
            "mac": "00:11:22:33:44:55",
            "vlan": [
                { "id": 1, "address": "192.168.1.2/24" },
                { "id": 2, "address": "192.168.2.2/24" },
            ]
        }
    ])

    expected = {
        '10-eth0.link':
            '[Match]\n'
            'MACAddress=00:11:22:33:44:55\n'
            'Driver=!802.1Q*\n'
            '\n'
            '[Link]\n'
            'Name=eth0',
        '10-eth0.network':
            '[Match]\n'
            'Name=eth0\n'
            '\n'
            '[Network]\n'
            'VLAN=eth0.1\n'
            'VLAN=eth0.2\n',
        '20-eth0.1.netdev':
            '[NetDev]\n'
            'Name=eth0.1\n'
            'Kind=vlan\n'
            '\n'
            '[VLAN]\n'
            'Id=1\n',
        '20-eth0.1.network':
            '[Match]\n'
            'Name=eth0.1\n'
            '\n'
            '[Network]\n'
            'Address=192.168.1.2/24\n',
        '20-eth0.2.netdev':
            '[NetDev]\n'
            'Name=eth0.2\n'
            'Kind=vlan\n'
            '\n'
            '[VLAN]\n'
            'Id=2\n',
        '20-eth0.2.network':
            '[Match]\n'
            'Name=eth0.2\n'
            '\n'
            '[Network]\n'
            'Address=192.168.2.2/24\n'
    }

    config = generate_config(args)
    assert expected == config

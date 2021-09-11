#!/usr/bin/python
""" Ansible module which generates systemd-networkd config files. """

# Copyright: (c) 2021 - Max Maisel
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = r'''
---
module: systemd_networkd

short_description: Generates systemd_networkd configuration

version_added: "0.1.0"

description: >
    Generates systemd_networkd configuration files.
    Currently supports physical interfaces, berdges and VLANs.

options:
    networks:
        description: Networks configuration
        required: true
        type: list
        elements: dict
        suboptions:
            mac:
                type: str
                description: >
                    The MAC address of this inferface.
                    Required for interfaces of type "net".
            type:
                type: str
                choices: ["net", "bridge"]
                default: "net"
                description: The type of the interface.
            name:
                type: str
                required: true
                description: The name that should be assigned to the interface.
            address:
                type: str
                description: >
                    The static IP address of the interface in format
                    "x.x.x.x/length".
            bridge:
                type: str
                description: >
                    The name of the bridge is the interface should be assigned
                    to a bridge.
            dhcp:
                type: bool
                description: True if the interface should use DHCPv4.
            dns:
                type: list
                elements: str
                description: List of DNS server IP addresses.
            gateway:
                type: str
                description: Static IP address of the default gateway.
            vlan:
                type: list
                elements: dict
                description: List of VLANs on this interface.
                suboptions:
                    id:
                        type: "int"
                        required: true
                        description: VLAN ID of this virutal interface.
                    name:
                        type: str
                        required: false
                        description: >
                            Name of the virtual interface.
                    address:
                        type: str
                        description: >
                            The static IP address of the interface in format
                            "x.x.x.x/length".
                    bridge:
                        type: str
                        description: >
                            The name of the bridge is the interface should be
                            assigned to a bridge.
                    dhcp:
                        type: bool
                        description: True if the interface should use DHCPv4.
                    dns:
                        type: list
                        elements: str
                        description: List of DNS server IP addresses.
                    gateway:
                        type: str
                        description: Static IP address of the default gateway.

extends_documentation_fragment: ansible.builtin.files

author:
    - Max Maisel (@mmmaisel)
'''

EXAMPLES = r'''
# Configure simple interface
- name: Configure eth0 with DHCP
  systemd_networkd:
    networks:
      eth0:
        mac: "00:11:22:33:44:55"
        dhcp: true

# Complex configuration
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
'''

RETURN = r'''
diff:
    description: Configuration difference
    returned: success
    type: dict
    sample: {"before": "config1", "after" :"config2"}
'''

import glob
import os
from ansible.module_utils.basic import AnsibleModule

NETWORKD_CFG_PATH = "/etc/systemd/network"


def basic_network_block(network):
    """ Processes general network attributes into a systemd-networkd
    "[Network] config file block. """

    network_block = "[Network]\n"
    if network["address"] is not None:
        network_block += "Address={0}\n".format(network["address"])
    if network["bridge"] is not None:
        network_block += "Bridge={0}\n".format(network["bridge"])
    if network["dhcp"] is not None:
        network_block += "DHCP=ipv4\n"
    if network["dns"] is not None:
        for server in network["dns"]:
            network_block += "DNS={0}\n".format(server)
    if network["gateway"] is not None:
        network_block += "Gateway={0}\n".format(network["gateway"])

    return network_block


def generate_config(networks):
    """ Generates a dictionary of systemd-networkd config files from given
    dictionary of Ansible task arguments. """

    files = {}
    for network in networks:
        name = network["name"]
        if network["mac"] is not None:
            link_match_block = "[Match]\nMACAddress={0}\nDriver=!802.1Q*" \
                .format(network["mac"])
            match_block = "[Match]\nName={0}".format(name)
            link_block = "[Link]\nName={0}".format(name)

            network_block = basic_network_block(network)
            if network["vlan"] is not None:
                for vlan in network["vlan"]:
                    if vlan["name"] is not None:
                        vname = vlan["name"]
                    else:
                        vname = "{0}.{1}".format(name, vlan["id"])

                    network_block += "VLAN={0}\n".format(vname)
                    files["20-{0}.netdev".format(vname)] = \
                        "[NetDev]\nName={0}\nKind=vlan\n\n[VLAN]\nId={1}\n" \
                        .format(vname, vlan["id"])

                    vnetwork_block = "[Match]\nName={0}\n\n".format(vname)
                    vnetwork_block += basic_network_block(vlan)
                    files["20-{0}.network".format(vname)] = vnetwork_block

            files["10-{0}.link".format(name)] = \
                "{0}\n\n{1}".format(link_match_block, link_block)
            files["10-{0}.network".format(name)] = \
                "{0}\n\n{1}".format(match_block, network_block)
        if network["type"] == "bridge":
            files["30-{0}.netdev".format(name)] = \
                "[NetDev]\nName={0}\nKind=bridge\n".format(name)
            files["30-{0}.network".format(name)] = \
                "[Match]\nName={0}\n\n[Network]\nAddress={1}\n" \
                .format(name, network["address"])

    return files


def set_attributes(module, config_files, changed, perm_diff):
    """ Applies file attributes to files and generates attribute diff. """
    for file in config_files:
        path = "{0}/{1}".format(NETWORKD_CFG_PATH, file)
        file_args = module.load_file_common_arguments(module.params, path)
        diff = {}
        changed |= module.set_fs_attributes_if_different(
            file_args, changed, diff=diff)
        if "before" in diff:
            perm_diff["before"][file] = diff["before"]
            perm_diff["after"][file] = diff["after"]
    return changed


def read_config():
    """ Reads current systemd-networkd configuration from the target machine
    to a dictionary."""

    files = {}
    for filename in glob.glob("{0}/*".format(NETWORKD_CFG_PATH)):
        name = os.path.basename(filename)
        with open(filename, "r") as file:
            content = file.read(-1)
        files[name] = content

    return files


def files_to_string(files, perms):
    """ Converts a dictionary of systemd-networkd files to a single string
    for diffing. """

    acc = ""
    for key in sorted(files):
        acc += "***** {0} *****\n".format(key)
        if key in perms:
            acc += "{0}\n".format(perms[key])
        acc += "{0}\n\n".format(files[key])
    return acc


def module_args():
    """ Returns module argument specification. """

    network_args = {
        "address": {
            "required": False,
            "type": "str"
        },
        "bridge": {
            "required": False,
            "type": "str"
        },
        "dhcp": {
            "required": False,
            "type": "bool"
        },
        "dns": {
            "required": False,
            "type": "list",
            "elements": "str"
        },
        "gateway": {
            "required": False,
            "type": "str"
        }
    }

    args = {
        "networks": {
            "required": True,
            "type": "list",
            "elements": "dict",
            "options": {
                # **network_args,
                "mac": {
                    "type": "str"
                },
                "name": {
                    "required": True,
                    "type": "str"
                },
                "type": {
                    "required": False,
                    "type": "str",
                    "choices": ["net", "bridge"],
                    "default": "net"
                },
                "vlan": {
                    "required": False,
                    "type": "list",
                    "elements": "dict",
                    "options": {
                        # **network_args,
                        "id": {
                            "required": True,
                            "type": "int"
                        },
                        "name": {
                            "required": False,
                            "type": "str"
                        }
                    }
                }
            }
        }
    }

    args["networks"]["options"].update(network_args.copy())
    args["networks"]["options"]["vlan"]["options"]. \
        update(network_args.copy())
    args["networks"]["options"]["vlan"]["options"]["name"]["required"] = False

    return args


def run_module():
    """ The main Ansible module function. """

    result = dict(
        changed=False,
        diff={"before": "", "after": ""},
        modified=[],
        removed=[]
    )

    module = AnsibleModule(
        argument_spec=module_args(),
        add_file_common_args=True,
        supports_check_mode=True
    )

    config_files = generate_config(module.params["networks"])
    existing_config_files = read_config()
    result["changed"] = config_files != existing_config_files

    files_to_remove = \
        set(existing_config_files.keys()) - set(config_files.keys())
    files_to_write = set()
    for file in config_files:
        if not (file in existing_config_files and
                config_files[file] == existing_config_files[file]):
            files_to_write.add(file)

    perm_diff = {"before": {}, "after": {}}
    if module.check_mode:
        result["changed"] |= set_attributes(
            module, existing_config_files, result["changed"], perm_diff)
        result["diff"] = {
            "before": files_to_string(existing_config_files, perm_diff["before"]),
            "after": files_to_string(config_files, perm_diff["after"])
        }
        module.exit_json(**result)

    for name in files_to_write:
        with open("{0}/{1}".format(NETWORKD_CFG_PATH, name), "w") as file:
            file.write(config_files[name])

    for name in files_to_remove:
        os.remove("{0}/{1}".format(NETWORKD_CFG_PATH, name))

    result["changed"] |= set_attributes(
        module, config_files, result["changed"], perm_diff)
    result["diff"] = {
        "before": files_to_string(existing_config_files, perm_diff["before"]),
        "after": files_to_string(config_files, perm_diff["after"])
    }

    module.exit_json(**result)


def main():
    """ Program entry point. """
    run_module()


if __name__ == '__main__':
    main()

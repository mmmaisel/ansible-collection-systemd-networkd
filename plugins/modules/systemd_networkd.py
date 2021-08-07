#!/usr/bin/python
""" Ansible module which generates systemd-networkd config files. """

# Copyright: (c) 2021 - Max Maisel
# GNU Affero General Public License v3.0+
# (see https://www.gnu.org/licenses/agpl-3.0.txt)

import glob
import os
from ansible.module_utils.basic import AnsibleModule

DOCUMENTATION = r'''
---
module: systemd_networkd

short_description: Generates systemd_networkd configuration

version_added: "0.1.0"

description: Generates systemd_networkd configuration files

options:
    networks:
        description: Networks configuration
        required: true
        type: list
        elements: dict
        options:
            mac:
                type: str
            type:
                choices: ["net", "bridge"]
            name:
                type: str
                required: true
            address:
                type: str
            bridge:
                type: str
            dhcp:
                type: bool
            dns:
                type: list
                elements: str
            gateway:
                type: str
            vlan:
                type: list
                elements: dict
                options:
                    id:
                        type: "int"
                        required: true
                        name:
                            type: str
                            required: true
                        address:
                            type: str
                        bridge:
                            type: str
                        dhcp:
                            type: bool
                        dns:
                            type: list
                            elements: str
                        gateway:
                            type: str

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
    sample {"before": "config1", "after" :"config2"}
'''

NETWORKD_CFG_PATH = "/etc/systemd/network"

def basic_network_block(network):
    """ Processes general network attributes into a systemd-networkd
    "[Network] config file block. """

    network_block = "[Network]\n"
    if network["address"] is not None:
        network_block += "Address={}\n".format(network["address"])
    if network["bridge"] is not None:
        network_block += "Bridge={}\n".format(network["bridge"])
    if network["dhcp"] is not None:
        network_block += "DHCP=ipv4\n"
    if network["dns"] is not None:
        for server in network["dns"]:
            network_block += "DNS={}\n".format(server)
    if network["gateway"] is not None:
        network_block += "Gateway={}\n".format(network["gateway"])

    return network_block

def generate_config(networks):
    """ Generates a dictionary of systemd-networkd config files from given
    dictionary of Ansible task arguments. """

    files = {}
    for network in networks:
        name = network["name"]
        if network["mac"] is not None:
            link_match_block = "[Match]\nMACAddress={}\nDriver=!802.1Q*" \
                .format(network["mac"])
            match_block = "[Match]\nName={}".format(name)
            link_block = "[Link]\nName={}".format(name)

            network_block = basic_network_block(network)
            if network["vlan"] is not None:
                for vlan in network["vlan"]:
                    if vlan["name"] is not None:
                        vname = vlan["name"]
                    else:
                        vname = "{}.{}".format(name, vlan["id"])

                    network_block += "VLAN={}\n".format(vname)
                    files["20-{}.netdev".format(vname)] = \
                        "[NetDev]\nName={}\nKind=vlan\n\n[VLAN]\nId={}\n" \
                        .format(vname, vlan["id"])

                    vnetwork_block = "[Match]\nName={}\n\n".format(vname)
                    vnetwork_block += basic_network_block(vlan)
                    files["20-{}.network".format(vname)] = vnetwork_block

            files["10-{}.link".format(name)] = \
                "{}\n\n{}".format(link_match_block, link_block)
            files["10-{}.network".format(name)] = \
                "{}\n\n{}".format(match_block, network_block)
        if network["type"] == "bridge":
            files["30-{}.netdev".format(name)] = \
                "[NetDev]\nName={}\nKind=bridge\n".format(name)
            files["30-{}.network".format(name)] = \
                "[Match]\nName={}\n\n[Network]\nAddress={}\n" \
                .format(name, network["address"])

    return files

def set_attributes(module, config_files, changed, perm_diff):
    """ Applies file attributes to files and generates attribute diff. """
    for file in config_files:
        path = "{}/{}".format(NETWORKD_CFG_PATH, file)
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
    for filename in glob.glob("{}/*".format(NETWORKD_CFG_PATH)):
        name = os.path.basename(filename)
        with open(filename, "r") as file:
            content = file.read(-1)
        files[name] = content

    for key in files:
        files[key] = files[key].rstrip("\n")
    return files

def files_to_string(files, perms):
    """ Converts a dictionary of systemd-networkd files to a single string
    for diffing. """

    acc = ""
    for key in sorted(files):
        acc += "***** {} *****\n".format(key)
        if key in perms:
            acc += "{}\n".format(perms[key])
        acc += "{}\n\n".format(files[key])
    return acc

def module_args():
    """ Returns module argument specification. """

    network_args = {
        "name": {
            "required": True,
            "type": "str"
        },
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
                #**network_args,
                "mac": {
                    "type": "str"
                },
                "type": {
                    "required": False,
                    "type": "str",
                    "default": "net"
                },
                "vlan": {
                    "required": False,
                    "type": "list",
                    "elements": "dict",
                    "options": {
                        #**network_args,
                        "id": {
                            "required": True,
                            "type": "int"
                        }
                    }
                }
            }
        }
    }

    args["networks"]["options"].update(network_args.copy())
    args["networks"]["options"]["vlan"]["options"]. \
        update(network_args.copy())
    args["networks"]["options"]["vlan"]["options"] \
        ["name"]["required"] = False

    return args

def run_module():
    """ The main Ansible module function. """

    required_if = [
        ("type", "net", ("mac"))
    ]

    result = dict(
        changed=False,
        diff={"before":"", "after": ""},
        modified=[],
        removed=[]
    )

    module = AnsibleModule(
        argument_spec=module_args(),
        required_if=required_if,
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
        if not (file in existing_config_files and \
                config_files[file] == existing_config_files[file]):
            files_to_write.add(file)

    perm_diff = {"before":{}, "after":{}}
    if module.check_mode:
        result["changed"] |= set_attributes(
            module, existing_config_files, result["changed"], perm_diff)
        result["diff"] = {
            "before": files_to_string(existing_config_files, perm_diff["before"]),
            "after": files_to_string(config_files, perm_diff["after"])
        }
        module.exit_json(**result)

    for name in files_to_write:
        with open("{}/{}".format(NETWORKD_CFG_PATH, name), "w") as file:
            file.write(config_files[name])

    for name in files_to_remove:
        os.remove("{}/{}".format(NETWORKD_CFG_PATH, name))

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

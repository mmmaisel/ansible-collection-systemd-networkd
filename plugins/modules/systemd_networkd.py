#!/usr/bin/python

# Copyright: (c) 2021 - Max Maisel
# GNU Affero General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/agpl-3.0.txt)

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
        type: dict

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

import glob
import os

from ansible.module_utils.basic import AnsibleModule

NETWORKD_CFG_PATH = "/etc/systemd/network"


def generate_config(networks):
    files = {}
    for key in networks:
        network = networks[key]
        if "mac" in network:
            link_match_block = "[Match]\nMACAddress={}\nDriver=!802.1Q*" \
                .format(network["mac"])
            match_block = "[Match]\nName={}".format(key)
            link_block = "[Link]\nName={}".format(key)
            network_block = "[Network]\n"

            # XXX: deduplicate
            if "address" in network:
                network_block += "Address={}\n".format(network["address"])
            if "bridge" in network:
                network_block += "Bridge={}\n".format(network["bridge"])
            if "dhcp" in network:
                network_block += "DHCP=ipv4\n"
            if "dns" in network:
                for server in network["dns"]:
                    network_block += "DNS={}\n".format(server)
            if "gateway" in network:
                network_block += "Gateway={}\n".format(network["gateway"])
            if "vlan" in network:
                for vlan in network["vlan"]:
                    if "name" in vlan:
                        name = vlan["name"]
                    else:
                        name = "{}.{}".format(key, vlan["id"])

                    network_block += "VLAN={}\n".format(name)
                    files["20-{}.netdev".format(name)] = \
                        "[NetDev]\nName={}\nKind=vlan\n\n[VLAN]\nId={}\n" \
                        .format(name, vlan["id"])

                    vnetwork_block = "[Match]\nName={}\n\n[Network]\n" \
                        .format(name)
                    if "address" in vlan:
                        vnetwork_block += "Address={}\n".format(vlan["address"])
                    if "bridge" in vlan:
                        vnetwork_block += "Bridge={}\n".format(vlan["bridge"])
                    if "dhcp" in vlan:
                        vnetwork_block += "DHCP=ipv4\n"
                    if "dns" in vlan:
                        for server in vlan["dns"]:
                            vnetwork_block += "DNS={}\n".format(server)
                    if "gateway" in vlan:
                        vnetwork_block += "Gateway={}\n".format(vlan["gateway"])
                    files["20-{}.network".format(name)] = vnetwork_block

            files["10-{}.link".format(key)] = \
                "{}\n\n{}".format(link_match_block, link_block)
            files["10-{}.network".format(key)] = \
                "{}\n\n{}".format(match_block, network_block)
        if "bridge" in network and network["bridge"] == True:
            files["30-{}.netdev".format(key)] = \
                "[NetDev]\nName={}\nKind=bridge\n".format(key)
            files["30-{}.network".format(key)] = \
                "[Match]\nName={}\n\n[Network]\nAddress={}\n" \
                .format(key, network["address"])

    return files

def read_config():
    files = {}
    permissions = {}
    for filename in glob.glob("{}/*".format(NETWORKD_CFG_PATH)):
        name = os.path.basename(filename)
        file = open(filename, "r")
        content = file.read(-1)
        file.close
        files[name] = content

        stat = os.stat(filename)
        permissions[name] = "* uid: {} gid: {} mode: {:o} *". \
            format(stat.st_uid, stat.st_gid, stat.st_mode)

    for key in files:
        files[key] = files[key].rstrip("\n")
    return files, permissions

def files_to_string(files, perms):
    acc = ""
    for key in sorted(files):
        acc += "***** {} *****\n{}\n{}\n\n".format(key, perms[key], files[key])
    return acc

def run_module():
    module_args = dict(
        networks=dict(type="dict", required=True)
    )

    result = dict(
        changed=False,
        modified=[],
        removed=[]
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    # TODO: validate input
    #if module.params['name'] == 'fail me':
    #    module.fail_json(msg='You requested this to fail', **result)

    # TODO: set mode and owner from params

    config_files = generate_config(module.params["networks"])
    config_perms = {}
    for file in config_files:
        config_perms[file] = "* uid: 0 gid: 0 mode: 100644 *"
    existing_config_files, existing_permissions = read_config()
    result["changed"] = config_files != existing_config_files or \
        config_perms != existing_permissions

    files_to_remove = \
        set(existing_config_files.keys()) - set(config_files.keys())
    files_to_write = set()
    for file in config_files:
        if not (file in existing_config_files and \
                config_files[file] == existing_config_files[file]):
            files_to_write.add(file)

    if module._diff:
        result["diff"] = {
                "before": files_to_string(existing_config_files,
                    existing_permissions),
                "after": files_to_string(config_files, config_perms)
            }

    if module.check_mode:
        module.exit_json(**result)

    for name in files_to_write:
        f = open("{}/{}".format(NETWORKD_CFG_PATH, name), "w")
        f.write(config_files[name])
        f.close

    for name in files_to_remove:
        os.remove("{}/{}".format(NETWORKD_CFG_PATH, name))

    for file in config_files:
        path = "{}/{}".format(NETWORKD_CFG_PATH, file)
        module.set_mode_if_different(path, 0o644, False)
        module.set_owner_if_different(path, "root", False)
        module.set_group_if_different(path, "root", False)

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
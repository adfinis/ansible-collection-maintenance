#!/usr/bin/python

# Copyright: (c) 2022, Adfinis AG <support@adfinis.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)


from __future__ import (absolute_import, division, print_function)
__metaclass__ = type


DOCUMENTATION = r'''
---
module: systemd_cat_config

short_description: Run systemd-analyze cat-config on a specified config file and return the parsed result.

# If this is part of a collection, you need to use semantic versioning,
# i.e. the version is of the form "2.5.0" and not "2.4".
version_added: "0.1.8"

description: Run systemd-analyze cat-config on a specified config file and return the parsed result.

options:
    config:
        description: Name of the config to parse, e.g. systemd/journald.conf
        required: true
        type: str
    path:
        description: Path to systemd-analyze binary.
        required: false
        default: /usr/bin/systemd-analyze
        type: str

# Specify this value according to your collection
# in format of namespace.collection.doc_fragment_name
#extends_documentation_fragment:
#    - adfinis.maintenance.systemd_cat_config

author:
    - Adfinis AG (support@adfinis.com)
'''


EXAMPLES = r'''
- name: "Gather journald config"
  adfinis.maintenance.systemd_cat_config:
    config: systemd/journald.conf
'''


RETURN = r'''
globals:
  description: Global INI options
  type: dict
  returned: always
  sample: {"AGlobalOption": "AGlobalValue"}
sections:
  description: INI sections and their key value pairs
  type: dict
  returned: always
  sample: {"Journal": {"storage": "persistent"}}
'''


from ansible.module_utils.basic import AnsibleModule

import io
import sys
import subprocess

if sys.version_info.major < 3:
    import ConfigParser as configparser
else:
    import configparser


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        config=dict(type='str', required=True),
        path=dict(type='str', required=False, default='/usr/bin/systemd-analyze'),
    )

    # seed the result dict in the object
    # we primarily care about changed and state
    # changed is if this module effectively modified the target
    # state will include any data that you want your module to pass back
    # for consumption, for example, in a subsequent task
    result = dict(
        changed=False,
    )

    # the AnsibleModule object will be our abstraction working with Ansible
    # this includes instantiation, a couple of common attr would be the
    # args/params passed to the execution, as well as if the module
    # supports check mode
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
    )

    cmdline = [module.params['path'], 'cat-config', 'systemd/journald.conf']
    # Run the find command
    proc = subprocess.Popen(cmdline, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate()

    if proc.returncode != 0:
        result['stderr'] = err.decode()
        module.fail_json(msg='systemd-analyze process exited with non-zero returncode.  Run with -vvv to view stderr', **result)

    parser = configparser.ConfigParser()
    if sys.version_info.major < 3:
        parser.readfp(io.StringIO(out.decode()))
    else:
        parser.read_string(out.decode())

    result['globals'] = {}
    result['sections'] = {}

    for k, v in parser.defaults().items():
        result['globals'][k] = v

    for section in parser.sections():
        for k, v in parser.items(section):
            result['sections'].setdefault(section, {})[k] = v

    result['changed'] = False

    # in the event of a successful module execution, you will want to
    # simple AnsibleModule.exit_json(), passing the key/value results
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()

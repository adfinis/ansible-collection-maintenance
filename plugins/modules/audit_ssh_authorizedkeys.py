#!/usr/bin/python

# Copyright: (c) 2022, Adfinis AG <support@adfinis.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)


from __future__ import (absolute_import, division, print_function)
__metaclass__ = type


DOCUMENTATION = r'''
---
module: audit_ssh_authorizedkeys

short_description: This is my test module

# If this is part of a collection, you need to use semantic versioning,
# i.e. the version is of the form "2.5.0" and not "2.4".
version_added: "0.1.0"

description: This is my longer description explaining my test module.

options:
    file:
        description: Path to the authorized_keys file.  If absent, sshd_config is queried (see config and sshd below)
        required: false
        default: null
        type: str
    user:
        description: User whose keys to audit
        required: false
        default: ALL
        type: str
    required:
        description: List of required authorized_keys entries
        required: false
        default: []
        type: list
    allowed:
        description: List of optional, allowed authorized_keys entries
        required: false
        default: []
        type: list
    forbidden:
        description: List of forbidden authorized_keys entries
        required: false
        default: []
        type: list
    config:
        description: Path to the sshd config fille
        required: false
        default: /etc/ssh/sshd_config
        type: str
    sshd:
        description: Path to the sshd binary
        required: false
        default: sshd
        type: str

# Specify this value according to your collection
# in format of namespace.collection.doc_fragment_name
#extends_documentation_fragment:
#    - adfinis.maintenance.audit_ssh_authorizedkeys

author:
    - Adfinis AG (@adfinis)
'''


EXAMPLES = r'''
- name: Check for unknown SSH keys
  adfinis.maintenance.audit_ssh_authorizedkeys:
    allowed:
      - 'from="2001:db8::42/128" ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIKBIpR/ccV9KAL5eoyPaT0frG1+moHO2nM2TsRKrdANU root@backup.example.org'
      - 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICZWKDPix+uTd+P+ZdoD3AkrD8cfikji9JKzvrfhczMA'
'''


RETURN = r'''
authorized_keys:
  description: Entries in all authorized_keys files, per user
  type: dict
  returned: always
  sample:
    root:
      - 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICZWKDPix+uTd+P+ZdoD3AkrD8cfikji9JKzvrfhczMA mallory@evil.example.org'
'''


from ansible.module_utils.basic import AnsibleModule

import os
import pwd
import subprocess
import shlex


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        file=dict(type='str', required=False, default=None),
        config=dict(type='str', required=False, default='/etc/ssh/sshd_config'),
        sshd=dict(type='str', required=False, default='sshd'),
        user=dict(type='str', required=False, default=None),
        required=dict(type='list', required=False, default=[]),
        allowed=dict(type='list', required=False, default=[]),
        forbidden=dict(type='list', required=False, default=[]),
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

    # Get user homes
    users = []
    if module.params['user'] is not None:
        user = module.params['user']
        try:
            pwdent = pwd.getpwnam(user)
            users.append(pwdent)
        except KeyError:
            module.fail_json(msg='User {} does not exist'.format(user), **result)
    else:
        for pwdent in pwd.getpwall():
            users.append(pwdent)

    # Read the acutal ssh authorized_keys
    result['authorized_keys'] = {}
    for pwdent in users:

        # Gather sshd config, may differ per user
        authorized_keys_paths = None
        if module.params['file'] is not None:
            authorized_keys_paths = [module.params['file']]
        else:
            ufilter = 'host=,addr=,user=' + pwdent.pw_name  # host and addr are required by some implementations
            sshd_cmdline = [module.params['sshd'], '-C', ufilter , '-T', '-f', module.params['config']]
            sshd_configtest = subprocess.Popen(sshd_cmdline, stdout=subprocess.PIPE)
            sshd_stdout, _ = sshd_configtest.communicate()
            if sshd_configtest.returncode != 0:
                module.fail_json(msg='SSHD configuration invalid (or insufficient privileges, try become_user=root become=yes)', **result)

            for cline in sshd_stdout.decode().splitlines():
                conf = cline.split()
                if conf[0] != 'authorizedkeysfile':
                    continue
                authorized_keys_paths = conf[1:]
                
        if authorized_keys_paths is None:
            authorized_keys_paths = []

        # Parse the % placeholders in the path (see TOKENS section in man 5 sshd_config) and load the config files
        sshkeys = []
        for path in authorized_keys_paths:
            resolved = ''
            escape = False
            for c in path:
                if escape:
                    escape = False
                    if c == '%':
                        resolved += c
                    elif c == 'u':
                        resolved += pwdent.pw_name
                    elif c == 'U':
                        resolved += pwdent.pw_uid
                    elif c == 'h':
                        resolved += pwdent.pw_dir
                    else:
                        module.fail_json(msg='Unsupported token %{} in AuthorizedKeysFile path {}'.format(c, path), **result)
                elif c == '%':
                    escape = True
                else:
                    resolved += c
            # Read the authorized_keys file if it exists
            if not os.path.isabs(resolved):
                resolved = os.path.join(pwdent.pw_dir, resolved)
            if not os.path.exists(resolved):
                continue
            with open(resolved, 'r') as f:
                keys = f.read().splitlines()
                sshkeys.extend(keys)
        sshkeys = [l for l in sshkeys if not l.strip().startswith('#')]
        result['authorized_keys'][pwdent.pw_name] = sshkeys

    violations = ''
    result['diff'] = []
    for user, user_keys in result['authorized_keys'].items():
        diffplus = ''
        diffminus = ''
        # Audit keys
        if len(module.params['required']) > 0:
            for key in module.params['required']:
                if key not in user_keys:
                    diffplus += key + '\n'

        if len(module.params['allowed']) > 0:
            for key in user_keys:
                if key not in module.params['allowed']:
                    diffminus += key + '\n'

        if len(module.params['forbidden']) > 0:
            for key in user_keys:
                if key in module.params['forbidden']:
                    diffminus += key + '\n'

        violations += diffplus + diffminus

        if len(diffplus) > 0 or len(diffminus) > 0:
            result['diff'].append({
                'before': diffminus,
                'after': diffplus,
                'before_header': 'authorized_keys ({})'.format(user),
                'after_header': 'authorized_keys ({})'.format(user),
            })

    if len(violations) > 0:
        result['changed'] = True
        if not module.check_mode:
            module.fail_json(msg=violations, **result)
    # in the event of a successful module execution, you will want to
    # simple AnsibleModule.exit_json(), passing the key/value results
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()

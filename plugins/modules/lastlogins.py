#!/usr/bin/python

# Copyright: (c) 2022, Adfinis AG <support@adfinis.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)


from __future__ import (absolute_import, division, print_function)
__metaclass__ = type


DOCUMENTATION = r'''
---
module: lastlogins

short_description: Check wtmp entries for suspicious logins.

# If this is part of a collection, you need to use semantic versioning,
# i.e. the version is of the form "2.5.0" and not "2.4".
version_added: "0.1.0"

description: Queries wtmp entries (last interactive login sessions), optionally checking for suspicious logins.

options:
    last:
        description: 'Path to the "last" binary. If absent, assumed to be on PATH.'
        required: false
        default: last
        type: str
    wtmp:
        description: 'Path to the wtmp logfile parsed by "last".'
        required: false
        default: 'See "man 1 last" on the target system.'
        type: str
    since:
        description: 'Time window to consider by "last".  Format e.g. "-90days", see "man 1 last" for details.'
        required: false
        default: none
        type: str
    allowed_users:
        description: List of usernames allowed to log in.
        required: false
        default: null
        type: list
    forbidden_users:
        description: List of usernames forbidden from logging in.
        required: false
        default: null
        type: list
    allowed_ips:
        description: List of source IPs (or CIDR ranges) from which log in is allowed.
        required: false
        default: null
        type: list
    forbidden_ips:
        description: List of source IPs (or CIDR ranges) from which log in is forbidden.
        required: false
        default: null
        type: list

# Specify this value according to your collection
# in format of namespace.collection.doc_fragment_name
#extends_documentation_fragment:
#    - adfinis.maintenance.lastlogins

author:
    - Adfinis AG (support@adfinis.com)
'''


EXAMPLES = r'''
# print last logins
- name: Retrieve list of logins
  adfinis.maintenance.lastlogins: {}
  register: last

- ansible.builtin.debug:
    var: last.last_logins

# Check for forbidden logins
- name: Root should never login
  adfinis.maintenance.lastlogins:
    forbidden_users:
      - root

- name: Nobody except root and adfinis should ever login
  adfinis.maintenance.lastlogins:
    allowed_users:
      - root
      - adfinis
    # This examples only checks the previous day
    since: yesterday
'''


RETURN = r'''
last_logins:
    description: List of all login entries in wtmp.
    type: list
    returned: always
    sample: ['root tty0    0.0.0.0     Thu Sep 29 13:17:56 2022   still logged in']
bad_logins:
    description: List of wtmp logins matching any of the filters.
    type: list
    returned: always
    sample: ['root tty0    0.0.0.0     Thu Sep 29 13:17:56 2022   still logged in']
'''


from ansible.module_utils.basic import AnsibleModule

import subprocess
import ipaddress

def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        last=dict(type='str', required=False, default='last'),
        wtmp=dict(type='str', required=False, default=None),
        since=dict(type='str', required=False, default=None),
        allowed_users=dict(type='list', required=False, default=None),
        forbidden_users=dict(type='list', required=False, default=None),
        allowed_ips=dict(type='list', required=False, default=None),
        forbidden_ips=dict(type='list', required=False, default=None),
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

    # Execute `last` to parse wtmp
    env = {
        'LC_ALL': 'C',
    }
    if module.params['wtmp'] is not None:
        # last --file wtmp --ip --fullnames --fulltimes (RHEL version only supports shortops
        cmdline = [module.params['last'], '-f', module.params['wtmp'], '-i', '-w', '-F']
    else:
        cmdline = [module.params['last'], '-i', '-w', '-F']
    if module.params['since'] is not None:
        cmdline.extend(['-s', module.params['since']])
    lastproc = subprocess.Popen(cmdline, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    out, err = lastproc.communicate()

    if lastproc.returncode != 0:
        result['stderr'] = err.decode('utf-8')
        module.fail_json(msg='last process exited with non-zero returncode.  Run with -vvv to view stderr', **result)

    # Parse output and match against allowed or forbidden users and/or ips

    last_logins = []
    bad_logins = []
    # last -i shows 0.0.0.0 for local logins
    allowed_ips = ['0.0.0.0']
    if module.params['allowed_ips'] is not None:
        allowed_ips.extend(module.params['allowed_ips'])
    forbidden_ips = []
    if module.params['forbidden_ips'] is not None:
        forbidden_ips.extend(module.params['forbidden_ips'])

    for line in out.decode('utf-8').splitlines():
        if line.startswith('reboot') or line[1:].startswith('tmp begins') or len(line) == 0:
            continue
        tokens = line.split(None, 3)
        if len(tokens) < 4:
            module.fail_json(msg='I don\'t understand this wtmp line: "{}"'.format(line), **result)
        user = tokens[0]
        ip = tokens[2]

        last_logins.append(line)
        if module.params['allowed_users'] is not None and user not in module.params['allowed_users']:
            bad_logins.append(line)
        elif module.params['forbidden_users'] is not None and user in module.params['forbidden_users']:
            bad_logins.append(line)
        elif not any(ipaddress.ip_address(ip) in ipaddress.ip_network(allowed_ip) for allowed_ip in allowed_ips):
            bad_logins.append(line)
        elif any(ipaddress.ip_address(ip) in ipaddress.ip_network(forbidden_ip) for forbidden_ip in forbidden_ips):
            bad_logins.append(line)

    result['last_logins'] = last_logins
    result['bad_logins'] = bad_logins

    # Report bad logins, if any, as diff, ellipsized to 10 entries

    result['changed'] = len(bad_logins) > 0
    if len(bad_logins) == 0:
        after = ''
    elif len(bad_logins) > 11:
        after = '\n'.join(bad_logins[:10]) + '\n{} more\n'.format(len(bad_logins) - 10)
    else:
        after = '\n'.join(bad_logins) + '\n'
        
    result['diff'] = [{
        'before': '',
        'after': after,
    }]

    # in the event of a successful module execution, you will want to
    # simple AnsibleModule.exit_json(), passing the key/value results
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()

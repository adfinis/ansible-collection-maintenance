#!/usr/bin/python

# Copyright: (c) 2022, Adfinis AG <support@adfinis.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)


from __future__ import (absolute_import, division, print_function)
__metaclass__ = type


DOCUMENTATION = r'''
---
module: find

short_description: Wrapper around the UNIX find utility

# If this is part of a collection, you need to use semantic versioning,
# i.e. the version is of the form "2.5.0" and not "2.4".
version_added: "0.1.1"

description: Wrapper around the UNIX find utility, because ansible.builtin.file capabilities are very restricted.

options:
    pattern:
        description: Regex that the files must match
        required: false
        default: null
        type: string
    paths:
        description: Paths to search in
        required: true
        type: list
    prune:
        description: Paths to exclude from find (through find -path ... -prune)
        required: false
        default: []
        type: list
    type:
        description: types of files to return
        required: false
        default: ALL
        type: list|str
    xdev:
        description: Do not descend directories on other filesystems.
        required: false
        default: false
        type: bool
    size:
        description: Find files using less than, more than or exactly this amount (through find -size ..,.)
        required: false
        default: null
        type: str
    age:
        description: Find files whose data was last modified less than, more than or exactly n minutes ago (through find -mmin ..,.)
        required: false
        default: null
        type: str
    exclude:
        description: Exclude files from the result set if they match one of these regular expressions.
        required: false
        default: []
        type: list

# Specify this value according to your collection
# in format of namespace.collection.doc_fragment_name
#extends_documentation_fragment:
#    - adfinis.maintenance.find

author:
    - Adfinis AG (support@adfinis.com)
'''


EXAMPLES = r'''
- name: "Find large, recently modified files"
  adfinis.maintenance.find:
    paths:
      - /
    pattern: "*.log"
    prune: [/boot, /proc, /sys]
    type: file
    size: "+16M"
    age: "-{{ 60*24*7*2 }}"
'''


RETURN = r'''
found:
  description: List of files returned by find
  type: list
  returned: always
  sample: [/opt/error.log, /opt/access.log]
'''


from ansible.module_utils.basic import AnsibleModule

import os
import re
import subprocess


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        pattern=dict(type='str', required=False),
        paths=dict(type='list', required=True),
        prune=dict(type='list', required=False, default=[]),
        type=dict(type='str', required=False, default=None),
        xdev=dict(type='bool', required=False, default=False),
        size=dict(type='str', required=False, default=None),
        age=dict(type='str', required=False, default=None),
        exclude=dict(type='list', required=False, default=[]),
        find=dict(type='str', required=False, default='find'),
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

    cmdline = [module.params['find']]
    for path in module.params['paths']:
        if path.startswith('-'):
            path = './' + path
        # Search paths below a pruned subtree must be removed from the cmdline, otherwise they are not pruned.
        prune = False
        for p in module.params['prune']:
            abspath = os.path.abspath(p)
            if os.path.commonprefix([os.path.abspath(path), abspath]) == abspath:
                prune = True
                break
        if not prune:
            cmdline.append(path)

    if module.params['pattern'] is not None:
        cmdline.append('-name')
        cmdline.append(module.params['pattern'])

    for path in module.params['prune']:
        cmdline.append('-path')
        cmdline.append(path)
        cmdline.append('-prune')
        cmdline.append('-o')

    if module.params['xdev']:
        cmdline.append('-xdev')

    if module.params['type'] is not None:
        types = module.params['type']
        if isinstance(types, str):
            types = [types]
        typeflags = []
        for typ in types:
            if typ == 'file':
                typeflags.append('f')
            elif typ == 'block':
                typeflags.append('b')
            elif typ == 'char':
                typeflags.append('c')
            elif typ == 'directory':
                typeflags.append('d')
            elif typ == 'pipe':
                typeflags.append('p')
            elif typ == 'link':
                typeflags.append('l')
            elif typ == 'socket':
                typeflags.append('s')
            elif typ == 'door':
                typeflags.append('D')
            else:
                module.fail_json(msg='Unknown type "{}"'.format(typ), **result)
        cmdline.append('-type')
        cmdline.append(','.join(typeflags))

    if module.params['size'] is not None:
        cmdline.append('-size')
        cmdline.append(module.params['size'])

    if module.params['age'] is not None:
        cmdline.append('-mmin')
        cmdline.append(module.params['age'])

    cmdline.append('-print0')

    result['cmdline'] = cmdline

    if module.check_mode:
        result['found'] = []
        module.exit_json(**result)

    # Run the find command
    findproc = subprocess.Popen(cmdline, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = findproc.communicate()

    if findproc.returncode != 0:
        result['stderr'] = err.decode('utf-8')
        module.fail_json(msg='find process exited with non-zero returncode.  Run with -vvv to view stderr', **result)

    result['found'] = []
    # Compile regex patterns for faster search
    patterns = [re.compile(p) for p in module.params['exclude']]
    
    for found in out.split(b'\0'):
        found = found.decode('utf-8')
        if len(found) == 0:
            continue
        exclude = False
        for pattern in patterns:
            if pattern.match(found) is not None:
                exclude = True
                break
        if not exclude:
            result['found'].append(found)

    result['changed'] = len(result['found']) > 0
    result['diff'] = [{
        'before': '',
        'after': '\n'.join(result['found']) + '\n',
    }]
    # in the event of a successful module execution, you will want to
    # simple AnsibleModule.exit_json(), passing the key/value results
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()

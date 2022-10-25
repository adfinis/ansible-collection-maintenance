from __future__ import (absolute_import, division, print_function)
__metaclass__ = type


DOCUMENTATION = '''
name: report
callback_type: aggregate
requirements:
  - |
    enable in configuration:
      callback_plugins=(insert default callback plugins path here):./plugins/callback
      callbacks_enabled=report
short_description: Print Markdown checklists indicating which tasks require human interaction
version_added: "0.1.0"
description:
  - |
    Print Markdown checklists indicating which tasks require human interaction.
    Example:

      example01.example.org
      - [x] 10-028
      - [x] 10-032
      - [ ] 10-034

      example02.example.org
      - [x] 10-028
      - [ ] 10-032
      - [x] 10-034
options: {}
#  # Kept around as reference
#  format_string:
#    description: format of the string shown to user at play end
#    ini:
#      - section: callback_timer
#        key: format_string
#    env:
#      - name: ANSIBLE_CALLBACK_TIMER_FORMAT
#    default: "Playbook run took %s days, %s hours, %s minutes, %s seconds"
'''


import json
from datetime import datetime

from ansible.plugins.callback import CallbackBase
from ansible.executor.task_result import TaskResult


class CallbackModule(CallbackBase):
    """
    Print Markdown checklists indicating which tasks require human interaction.
    """
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'aggregate'
    CALLBACK_NAME = 'adfinis.maintenance.report'

    CALLBACK_NEEDS_ENABLED = True

    def __init__(self):
        self.hosts = {}
        self.tasknames = {}
        super(CallbackModule, self).__init__()

    def on_any(self, *args, **kwargs):
        # on_any is a horribly hacky catch-all handler that's triggered on every single event during a play.

        # There is no clearly defined "event type" at the top level of the args/kwargs, so we carefully need to check
        # the result object's internal structure.
        if len(args) != 2 and len(args[0]) != 2:
            return
        task = args[0][0]
        if not isinstance(task, TaskResult):
            return

        if task.is_skipped():
            return
        if task.is_failed():
            state = 2
        elif task.is_changed():
            state = 1
        else:
            state = 0

        # Extract the task information from the TaskResult.
        # Unfortunately, some protected members need to be accessed to get the information we need.  If something in
        # this plugin breaks with future ansible versions, it's probably the next 3 lines.
        host = task._host.name
        taskid = task._task.vars.get('taskid')
        taskname = task._task.vars.get('name', '')
        if taskid is None or taskid == 'ignore-me':
            return

        # Store the "worst" result (max, failed=2, changed=1, ok=0) per host and taskid.
        # E.g. if one subtask failed, consider the entire maintenance task failed.
        hostdict = self.hosts.setdefault(host, {})
        hostdict[taskid] = max(hostdict.get(taskid, 0), state)
        # Pipe `|` is used as the separator for "subtasks" if one maintenance task is split into multiple ansible tasks
        self.tasknames[taskid] = taskname.split('|', 1)[0].strip()

    def v2_playbook_on_stats(self, stats):
        # Generate checklist report at the end of the playbook run
        for host, tasks in self.hosts.items():
            self._display.display('')
            self._display.display(host)
            for task, result in tasks.items():
                if result == 0:
                    self._display.display('- [x] %s: %s' % (task, self.tasknames.get(task, '')))
                else:
                    self._display.display('- [ ] %s: %s' % (task, self.tasknames.get(task, '')))

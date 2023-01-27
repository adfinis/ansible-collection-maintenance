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
      - [x] 10-028: This task is ok
      - [x] 10-032: This is ok as well
      - [ ] 10-034: This task reported changed

      example02.example.org
      - [x] 10-028 A task that reported ok
      - [~] 10-032 This task was skipped
      - [x] 10-034 Another ok task
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
from enum import IntEnum

from ansible.plugins.callback import CallbackBase
from ansible.executor.task_result import TaskResult


class TaskState(IntEnum):
    SKIPPED = 0
    OK = 1
    CHANGED = 2
    FAILED = 3


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

    def _process_task_result(self, result, state):
        if not isinstance(result, TaskResult):
            return
        # Extract the task information from the TaskResult.
        # Unfortunately, some protected members need to be accessed to get the information we need.  If something in
        # this plugin breaks with future ansible versions, it's probably the next 3 lines.
        host = result._host.name
        taskid = result._task.vars.get('taskid')
        taskname = result._task.vars.get('name', '')
        if taskid is None or taskid == 'ignore-me':
            return
        # Store the "worst" result (max, failed=3, changed=2, ok=1, skipped=0) per host and taskid.
        # E.g. if one subtask failed, consider the entire maintenance task failed.
        hostdict = self.hosts.setdefault(host, {})
        hostdict[taskid] = max(hostdict.get(taskid, TaskState.SKIPPED), state)
        # Pipe `|` is used as the separator for "subtasks" if one maintenance task is split into multiple ansible tasks
        self.tasknames[taskid] = taskname.split('|', 1)[0].strip()

    def v2_runner_on_failed(self, result, ignore_errors=False):
        self._process_task_result(result, TaskState.FAILED)

    def v2_runner_on_skipped(self, result):
        self._process_task_result(result, TaskState.SKIPPED)

    def v2_runner_on_ok(self, result):
        if result.is_changed():
            self._process_task_result(result, TaskState.CHANGED)
        else:
            self._process_task_result(result, TaskState.OK)

    def v2_playbook_on_stats(self, stats):
        # Generate checklist report at the end of the playbook run
        for host, tasks in self.hosts.items():
            self._display.display('')
            self._display.display(host)
            for task, result in tasks.items():
                if result == TaskState.SKIPPED:
                    self._display.display('- [~] %s: %s' % (task, self.tasknames.get(task, '')))
                elif result == TaskState.OK:
                    self._display.display('- [x] %s: %s' % (task, self.tasknames.get(task, '')))
                else:
                    self._display.display('- [ ] %s: %s' % (task, self.tasknames.get(task, '')))

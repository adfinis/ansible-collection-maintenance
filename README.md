# Ansible Collection - adfinis.maintenance

[![License](https://img.shields.io/github/license/adfinis/ansible-collection-maintenance?style=flat-square)](https://github.com/adfinis/ansible-collection-maintenance/blob/main/LICENSE)
[![Pipeline](https://img.shields.io/github/actions/workflow/status/adfinis/ansible-collection-maintenance/.github/workflows/ansible-lint.yml?branch=main&style=flat-square)](https://github.com/adfinis/ansible-collection-maintenance/actions)
[![Ansible Galaxy](https://img.shields.io/badge/collection-adfinis.maintenance-informational?style=flat-square)](https://galaxy.ansible.com/adfinis/maintenance)
<!--[![Ansible Galaxy](https://img.shields.io/ansible/collection/2059?style=flat-square)](https://galaxy.ansible.com/adfinis/maintenance)-->

This Ansible collection provides a framework to run maintenance tasks automatically against a host.

It does so in a way that may be a bit counterintuitive for someone used to Ansible:
* Almost everything is executed in check mode - The exceptions are tasks that won't break anything.
* Tasks that report `ok` can be considered completed - no human intervention is required.
* Tasks that report `changed` or `failed` require human intervention.
  * **NOTE: It is expected that tasks fail** if some critical prerequesite is not met.  Usually this is not a bug, and
    the correct way to resolve the issue is to either fulfil the required prerequisite, or to exclude the failing task
    (see `maintenance_exclude_tasks` below).

The tasks to run are grouped into "checklists". By convention, each checklist is implemented in a separate role, e.g.:
* The `maintenance_10_linux` role implements tasks common to most Linux systems
* The `maintenance_11_debian` role implements Debian-specific tasks

Checklists (i.e. roles) are assigned to hosts via playbooks.  The
example playbook in `playbooks/playbook.yml` applies each role to an
eponymous host group.  When using this example playbook, your inventory could look like this:

```ini
[maintenance_10_linux:children]
maintenance_11_debian
maintenance_15_rhel

[maintenance_11_debian]
debian01.example.org
debian02.example.org

[maintenance_15_rhel]
rhel01.example.org
centos01.example.org
```

Every checklist task (which may consist of more than one Ansible task) has a unique task ID in the form `XX-YYY` which `XX` being the checklist id and `YYY` being a consecutive number within the checklist. E.g. `10-042`.  These IDs can be used to exclude tasks from being applied to one or more hosts using the `maintenance_exclude_tasks` hostvar.
To be able to easily exclude some checks globally in a playbook and some checks only on a host-level, the variable by default combines `maintenance_global_exclude_tasks` and `maintenance_host_exclude_tasks`:

```yaml
# Exclude tasks globally
--- group_vars/all/maint.yml
maintenance_global_exclude_tasks:
  - 10-042

--- host_vars/my_host/maint.yml
# Additionally exclude 11-023 only on one host
maintenance_host_exclude_tasks:
  - 11-023
  # 10-042 is implicitly excluded by above global statement

--- host_vars/other_host/maint.yml
# Explicitly ONLY exclude a task on my host
maintenance_exclude_tasks:
  - 11-023
  # 10-042 will be included, global list doesn't apply
```

Some of the checklists have additional options which can be
overwritten at the host or group level, e.g. to override the expected
alias for `root` in `/etc/aliases`:

```yaml
linux_serverlogs_root_alias: serverlogs@example.com
```

Check out `roles/maintenance_*/defaults/main.yml` to see which options can be overwritten.


## Recommendations for ansible.cfg

```ini
[defaults]
display_skipped_hosts=no
display_ok_hosts=no
callback_whitelist=adfinis.maintenance.report
callbacks_enabled=adfinis.maintenance.report
duplicate_dict_key=ignore
inject_facts_as_vars=no
collections_path=./galaxy
roles_path=./galaxy/roles
```


## Example output

Running the example playbook in `playbooks/playbook.yml` with the recommended settings above against a host that is in the `maintenance_10_linux` and `maintenance_11_debian` hostgroups will provide an output like this:

```
user@maintenancemaster:~/git/maintenance-test$ ansible-playbook -l debian01.example.org playbook.yml 

PLAY [Run automated maintenance tasks] *****************************************************************************************************************************************************************************************************************************************************

TASK [adfinis.maintenance.maintenance_10_linux : 10-041: Security: Logins: Are there logins from suspicious hosts/users? | Gather past logins from `last` output] **************************************************************************************************************************
changed: [debian01.example.org]

TASK [adfinis.maintenance.maintenance_10_linux : 10-042: Security: SSH keys: Check for unknown or outdated keys for root and all users] ****************************************************************************************************************************************************
changed: [debian01.example.org]

TASK [adfinis.maintenance.maintenance_11_debian : 11-016: dpkg status: Are there packages which do not have the dpkg status ii or hi? | Report matching packages] **************************************************************************************************************************
changed: [debian01.example.org] => {
    "debian_dpkg_status.stdout_lines": [
        "rc  linux-image-5.10.0-9-amd64           5.10.70-1                      amd64        Linux 5.10 for 64-bit PCs (signed)"
    ]
}

TASK [adfinis.maintenance.maintenance_11_debian : 11-017: apt: Simulate the package upgrade] ***********************************************************************************************************************************************************************************************
changed: [debian01.example.org]

PLAY RECAP *********************************************************************************************************************************************************************************************************************************************************************************
debian01.example.org : ok=35   changed=4    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0   


debian01.example.org
- [x] 10-028: Systemd: Check all important service units
- [x] 10-032: Disk: Fstab: fstab correct?
- [x] 10-034: Disk: logrotate: Are there files in /var/log that are not rotated?
- [x] 10-035: Are there logfiles outside /var/log that are not rotated?
- [x] 10-039: Logfiles: Does journald log to persistent storage?
- [x] 10-040: Security: User: Are all created users documented in the wiki with password?
- [ ] 10-041: Security: Logins: Are there logins from suspicious hosts/users?
- [ ] 10-042: Security: SSH keys: Check for unknown or outdated keys for root and all users
- [~] 10-050: Mail: serverlogs: Is serverlogs@ entered in /etc/aliases for root?
- [~] 10-051: Mail: aliases.db: Make sure /etc/aliases.db is up to date
- [x] 11-011: Security: Are the security updates in the sources.list?
- [x] 11-012: Repository: Check if repository is set to release name (e.g. 'bullseye') and not to 'stable'
- [x] 11-013: For old distributions, has the repository been moved to http://archive.debian.org/ already?
- [x] 11-014: Update package lists and check for errors
- [ ] 11-016: dpkg status: Are there packages which do not have the dpkg status ii or hi?
- [ ] 11-017: apt: Simulate the package upgrade
- [x] 11-019: apt: Remove obsolete packages
- [x] 11-020: boot-config: Check boot configuration: keep bootloader up to date
- [x] 10-061: Updates: Check if a major update is pending.
```

With the ansible.cfg settings above, tasks that completed with the status `ok` or `skipped` won't be displayed, instead only `changed` tasks are shown, getting you a clear report on that you should look at.

The content of the checkboxes has the following meaning:
```
- [x] ok - nothing to do
- [~] skipped - task skipped as configured. Check if it's still reasonable to skip this task
- [ ] changed or failed - See output on what to do
```

If you want more detailed output, execute the playbook with the `--diff` option, example output:
```
TASK [adfinis.maintenance.maintenance_10_linux : 10-042: Security: SSH keys: Check for unknown or outdated keys for root and all users] ****************************************************************************************************************************************************
--- before: authorized_keys (root)
+++ after: authorized_keys (root)
@@ -1 +0,0 @@
-ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQCoquOVPUnXKNP25SQzdKpXKby2s1fDhZS/zllKW5zGMr+C9mnf7xMN+sB16yfXhQRCJGWjzjxNPl56lB9s4jV1lrFtDVEmGu+arv2eQa1cQJ6ggeOxhzfpbPVJh0T5cZg9XpuucJDTFceA/wN5eeWAIAQpzjeFTYn0obDjzSzoXsPiRZ35URCEF6R1/+6gj6WaosiGiCVUyyIK5vJLsbJCVsV+hSFmTrZfKIt33h+XcjKacfzGNsON++2B5m0EEvCy0= user@maintenancemaster

changed: [debian01.example.org]
```

There is also a checklist summarising all tasks that were run but finished with either `ok` or `skipped`.


## Development Setup

For development on this collection, we recommend the following setup:

- Set up a separate project folder with an inventory of your development target systems, hostvars and ansible.cfg as described above.
- `cd` to that folder.
- Run `ansible-galaxy collection install adfinis.maintenance`.  This will also install all the required dependencies.
- `rm -rf ./galaxy/ansible_collections/adfinis/maintenance` to remove the collection downloaded from Galaxy.
- `git clone github.com:adfinis/ansible-collection-maintenance ./galaxy/ansible_collections/adfinis/maintenance` to checkout the git repository.
- Do your development inside `./galaxy/ansible_collections/adfinis/maintenance`.
- For testing, run the playbook from your project folder as e.g. `ansible-galaxy -i inventory --diff adfinis.maintenance.playbook`.
  - If your Ansible version does not allow this yet, use the playbook path rather than its FQCN, i.e. `./galaxy/ansible_collections/adfinis/maintenance/playbooks/playbook.yml`.
  - To only test a single checklist item, you can run `ansible-playbook` limited to the taskid, using the `maintenance_only` variable: ` ansible-playbook -e maintenance_only=10-011 ...`.


## License

[GPL-3.0](https://github.com/adfinis/ansible-role-repo_mirror/blob/master/LICENSE)

## Author Information

adfinis.maintenance was written by:

* Adfinis AG | [Website](https://adfinis.com) | [Twitter](https://twitter.com/adfinis) | [GitHub](https://github.com/adfinis)

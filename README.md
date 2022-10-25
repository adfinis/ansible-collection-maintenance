# Ansible Collection - adfinis.maintenance

![Pipeline](https://github.com/adfinis/ansible-collection-maintenance/actions/workflows/ansible-lint.yml/badge.svg)

This Ansible collection provides a framework to run maintenance tasks automatically against a host.

It does so in a way that may be a bit counterintuitive for someone used to Ansible:
* Almost everything is executed in check mode - The exceptions are tasks that won't break anything.
* Tasks that report `ok` can be considered completed - no human intervention is required.
* Tasks that report `changed` or `failed` require human intervention.

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

Every checklist task (which may consist of more than one Ansible task) has a unique task ID in the form `XX-YYY` which `XX` being the checklist id and `YYY` being a consecutive number within the checklist. E.g. `10-042`.  These IDs can be used to exclude tasks from being applied to one or more hosts using the `maintenance_exclude_tasks` hostvar:


```yaml
maintenance_exclude_tasks:
  - 10-042
  - 11-023
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
callbacks_enabled=adfinis.maintenance.report
duplicate_dict_key=ignore
```


## License

[GPL-3.0](https://github.com/adfinis-sygroup/ansible-role-repo_mirror/blob/master/LICENSE)

## Author Information

adfinis.maintenance was written by:

* Adfinis AG | [Website](https://adfinis.com) | [Twitter](https://twitter.com/adfinis) | [GitHub](https://github.com/adfinis)

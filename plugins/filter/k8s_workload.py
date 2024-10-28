from datetime import datetime

class FilterModule(object):
    """Ansible custom filters"""

    def filters(self):
        """Return the custom filters"""
        return {
            "k8s_workload_pods_unhealthy": self._k8s_workload_pods_unhealthy,
            "k8s_workload_pods_restart_last_days": self._k8s_workload_pods_restart_last_days,
            "k8s_workload_check_service_type": self._k8s_workload_check_service_type
        }

    def _k8s_workload_pods_unhealthy(self, pods):
        if not pods:
            return []
        unhealthy_pods = []
        for pod in pods:
            for status in pod.get('status').get('containerStatuses', []):
                if status.get('state') and status.get('state').get('running'):
                    continue
                if status.get('state') and status.get('state').get('terminated'):
                    if status['state']['terminated'].get('reason') == 'Completed':
                        continue
                unhealthy_pods.append(pod.get('metadata').get('name'))
        return unhealthy_pods

    def _k8s_workload_pods_restart_last_days(self, pods, x_days):
        if not pods:
            return []
        restarted_pods = []
        for pod in pods:
            for status in pod.get('containerStatuses', []):
                if not status.get('startedAt') and status.get('restartCount', 0) > 0:
                    restarted_pods.append({
                        "name": pod.get('name'),
                        "started_at": "unknown",
                        "restarts": status.get('restartCount')
                    })
                    continue
                started_at = datetime.fromisoformat(status.get('startedAt'))
                if (datetime.now(started_at.tzinfo) - started_at).days < x_days:
                    restarted_pods.append({
                        "name": pod.get('name'),
                        "started_at": started_at.strftime("%Y-%m-%d %H:%M:%S"),
                        "restarts": status.get('restartCount')
                    })
        return restarted_pods

    def _k8s_workload_check_service_type(self, services, allowed_types):
        if not services:
            return []
        faulty_service = []
        for service in services:
            allowed_type = allowed_types.get(service.get('name'))
            if service.get('type') != allowed_type:
                faulty_service.append({
                    "name": service.get('name'),
                    "type": service.get('type'),
                    "allowed_type": allowed_type
                })
        return faulty_service

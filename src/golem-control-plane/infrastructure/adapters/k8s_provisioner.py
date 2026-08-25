# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Kubernetes implementation of the Provisioner interface."""

import time

from kubernetes import client, config  # type: ignore[import-untyped]
from kubernetes.client.rest import ApiException  # type: ignore[import-untyped]

from core.config import settings
from core.log import LoggerManager
from domain.models import AgentSpec, SandboxHandle, SandboxStatus
from domain.ports.provisioner import Provisioner

logger = LoggerManager.get_logger("KubernetesProvisioner")


def _load_k8s_config() -> None:
    """Load kubeconfig from in-cluster env or local ~/.kube/config."""
    try:
        config.load_incluster_config()
        logger.info("Loaded in-cluster K8s config")
    except config.ConfigException:
        config.load_kube_config()
        logger.info("Loaded local kubeconfig")


class KubernetesProvisioner(Provisioner):
    """Creates one K8s Namespace + Pod per agent, with ResourceQuota and NetworkPolicy."""

    def __init__(self) -> None:
        _load_k8s_config()
        self._core = client.CoreV1Api()
        self._apps = client.AppsV1Api()
        self._networking = client.NetworkingV1Api()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def create_sandbox(self, spec: AgentSpec) -> SandboxHandle:
        """Create Namespace, ResourceQuota, NetworkPolicy, ConfigMap, Pod and Service for the agent."""
        handle = SandboxHandle(agent_id=spec.agent_id, ttl_seconds=spec.ttl_seconds)
        logger.info(f"Creating sandbox '{handle.agent_id}' (ttl={spec.ttl_seconds}s)")

        self._create_namespace(handle, spec)
        self._apply_resource_quota(handle)
        self._apply_network_policy(handle)
        self._create_runner_configmap(handle, spec)
        self._create_pod(handle, spec)
        self._create_service(handle)

        return handle

    def delete_sandbox(self, handle: SandboxHandle) -> None:
        """Delete the entire Namespace (cascades to all resources inside it)."""
        logger.info(f"Deleting sandbox namespace '{handle.namespace}'")
        try:
            self._core.delete_namespace(handle.namespace)
        except ApiException as e:
            if e.status != 404:
                logger.error(f"Failed to delete namespace '{handle.namespace}': {e}")
                raise

    def get_status(self, handle: SandboxHandle) -> SandboxHandle:
        """Read the pod phase and map it to SandboxStatus."""
        try:
            pod = self._core.read_namespaced_pod(handle.pod_name, handle.namespace)
            phase = (pod.status.phase or "Unknown").lower()  # type: ignore[union-attr]
            handle.status = {
                "pending": SandboxStatus.PENDING,
                "running": SandboxStatus.RUNNING,
                "failed": SandboxStatus.FAILED,
                "succeeded": SandboxStatus.TERMINATED,
            }.get(phase, SandboxStatus.PENDING)
        except ApiException as e:
            if e.status == 404:
                handle.status = SandboxStatus.TERMINATED
            else:
                raise
        return handle

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _create_namespace(self, handle: SandboxHandle, spec: AgentSpec) -> None:
        ns = client.V1Namespace(
            metadata=client.V1ObjectMeta(
                name=handle.namespace,
                labels={"golem.io/managed": "true", "golem.io/agent-id": handle.agent_id},
                annotations={"golem.io/ttl-seconds": str(spec.ttl_seconds)},
            )
        )
        try:
            self._core.create_namespace(ns)
            logger.debug(f"Namespace '{handle.namespace}' created")
        except ApiException as e:
            if e.status == 409:
                # Namespace already exists (pre-created by deploy.sh) — update labels/annotations.
                self._core.patch_namespace(handle.namespace, ns)
                logger.debug(f"Namespace '{handle.namespace}' already exists — patched")
            else:
                raise

    def _apply_resource_quota(self, handle: SandboxHandle) -> None:
        quota = client.V1ResourceQuota(
            metadata=client.V1ObjectMeta(name="golem-quota", namespace=handle.namespace),
            spec=client.V1ResourceQuotaSpec(
                hard={"requests.cpu": "500m", "requests.memory": "512Mi", "limits.cpu": "1", "limits.memory": "1Gi"}
            ),
        )
        try:
            self._core.create_namespaced_resource_quota(handle.namespace, quota)
            logger.debug(f"ResourceQuota applied to namespace '{handle.namespace}'")
        except ApiException as e:
            if e.status == 409:
                self._core.patch_namespaced_resource_quota("golem-quota", handle.namespace, quota)
                logger.debug(f"ResourceQuota already exists in '{handle.namespace}' — patched")
            else:
                raise

    def _apply_network_policy(self, handle: SandboxHandle) -> None:
        # Allow all egress — MCP servers may run on arbitrary ports.
        # TODO §2.5: tighten once the MCP Registry introduces a known port set.
        policy = client.V1NetworkPolicy(
            metadata=client.V1ObjectMeta(name="default-deny-egress", namespace=handle.namespace),
            spec=client.V1NetworkPolicySpec(
                pod_selector=client.V1LabelSelector(),
                policy_types=["Egress"],
                egress=[client.V1NetworkPolicyEgressRule()],
            ),
        )
        try:
            self._networking.create_namespaced_network_policy(handle.namespace, policy)
            logger.debug(f"NetworkPolicy applied to namespace '{handle.namespace}'")
        except ApiException as e:
            if e.status == 409:
                self._networking.patch_namespaced_network_policy("default-deny-egress", handle.namespace, policy)
                logger.debug(f"NetworkPolicy already exists in '{handle.namespace}' — patched")
            else:
                raise

    def _create_runner_configmap(self, handle: SandboxHandle, spec: AgentSpec) -> None:
        """Create a ConfigMap in the agent namespace with runner config, AGENTS.md, and skill files.

        Keys:
        - ``config.yaml``: always present — runner configuration.
        - ``AGENTS.md``: present only when ``spec.agents_md`` is set.
        - ``skill-<name>.md``: one key per entry in ``spec.skills``.
        """
        data: dict[str, str] = {"config.yaml": spec.runner_config}

        if spec.agents_md is not None:
            data["AGENTS.md"] = spec.agents_md

        for skill_name, skill_content in spec.skills.items():
            data[f"skill-{skill_name}.md"] = skill_content

        cm = client.V1ConfigMap(
            metadata=client.V1ObjectMeta(name="runner-config", namespace=handle.namespace),
            data=data,
        )
        try:
            self._core.create_namespaced_config_map(handle.namespace, cm)
            logger.debug(f"ConfigMap 'runner-config' created in namespace '{handle.namespace}'")
        except ApiException as e:
            if e.status == 409:
                self._core.patch_namespaced_config_map("runner-config", handle.namespace, cm)
                logger.debug(f"ConfigMap 'runner-config' already exists in '{handle.namespace}' — patched")
            else:
                raise

    def _create_pod(self, handle: SandboxHandle, spec: AgentSpec) -> None:
        # WATSONX_API_KEY is the only secret — passed as env var, not in config.yaml.
        env_vars = [
            client.V1EnvVar(name="WATSONX_API_KEY", value=settings.llm.api_key),
        ]

        # envFrom: mount secrets listed in spec.env_secrets as environment variables.
        # Each secret must already exist in the agent namespace (created by deploy.sh).
        env_from = [
            client.V1EnvFromSource(secret_ref=client.V1SecretEnvSource(name=name)) for name in spec.env_secrets
        ] or None

        # Runner app-dir is /app/src/golem-runner — all files must be mounted there.
        _APP_DIR = "/app/src/golem-runner"

        # Always mount config.yaml.
        volume_mounts = [
            client.V1VolumeMount(
                name="runner-config",
                mount_path=f"{_APP_DIR}/config.yaml",
                sub_path="config.yaml",
                read_only=True,
            )
        ]

        # Mount AGENTS.md at <app-dir>/AGENTS.md when provided.
        if spec.agents_md is not None:
            volume_mounts.append(
                client.V1VolumeMount(
                    name="runner-config",
                    mount_path=f"{_APP_DIR}/AGENTS.md",
                    sub_path="AGENTS.md",
                    read_only=True,
                )
            )

        # Mount each skill at <app-dir>/skills/<name>.md.
        for skill_name in spec.skills:
            volume_mounts.append(
                client.V1VolumeMount(
                    name="runner-config",
                    mount_path=f"{_APP_DIR}/skills/{skill_name}.md",
                    sub_path=f"skill-{skill_name}.md",
                    read_only=True,
                )
            )

        pod = client.V1Pod(
            metadata=client.V1ObjectMeta(
                name=handle.pod_name,
                namespace=handle.namespace,
                labels={"golem.io/agent-id": handle.agent_id, "app": handle.pod_name},
            ),
            spec=client.V1PodSpec(
                restart_policy="Never",
                containers=[
                    client.V1Container(
                        name="runner",
                        image=settings.control_plane.runner_image,
                        image_pull_policy="IfNotPresent",
                        ports=[client.V1ContainerPort(container_port=8000)],
                        env=env_vars,
                        env_from=env_from,
                        resources=client.V1ResourceRequirements(
                            requests={"cpu": "250m", "memory": "256Mi"},
                            limits={"cpu": "1", "memory": "1Gi"},
                        ),
                        volume_mounts=volume_mounts,
                        startup_probe=client.V1Probe(
                            http_get=client.V1HTTPGetAction(path="/health", port=8000),
                            failure_threshold=12,
                            period_seconds=10,
                        ),
                        liveness_probe=client.V1Probe(
                            http_get=client.V1HTTPGetAction(path="/health", port=8000),
                            initial_delay_seconds=0,
                            period_seconds=10,
                            failure_threshold=3,
                        ),
                    )
                ],
                volumes=[
                    client.V1Volume(
                        name="runner-config",
                        config_map=client.V1ConfigMapVolumeSource(name="runner-config"),
                    )
                ],
            ),
        )
        try:
            self._core.create_namespaced_pod(handle.namespace, pod)
            logger.debug(f"Pod '{handle.pod_name}' created in namespace '{handle.namespace}'")
        except ApiException as e:
            if e.status == 409:
                logger.debug(f"Pod '{handle.pod_name}' already exists in '{handle.namespace}' — skipped")
            else:
                raise

    def _create_service(self, handle: SandboxHandle) -> None:
        """Create a ClusterIP Service so the pod is reachable by DNS within the cluster."""
        svc = client.V1Service(
            metadata=client.V1ObjectMeta(name=handle.pod_name, namespace=handle.namespace),
            spec=client.V1ServiceSpec(
                selector={"app": handle.pod_name},
                ports=[client.V1ServicePort(port=8000, target_port=8000, protocol="TCP")],
                type="ClusterIP",
            ),
        )
        try:
            self._core.create_namespaced_service(handle.namespace, svc)
            logger.debug(f"Service '{handle.pod_name}' created in namespace '{handle.namespace}'")
        except ApiException as e:
            if e.status == 409:
                self._core.patch_namespaced_service(handle.pod_name, handle.namespace, svc)
                logger.debug(f"Service '{handle.pod_name}' already exists in '{handle.namespace}' — patched")
            else:
                raise

    def wait_for_running(self, handle: SandboxHandle, timeout: int = 120) -> SandboxHandle:
        """Block until the pod is Running or timeout expires."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            updated = self.get_status(handle)
            if updated.status == SandboxStatus.RUNNING:
                return updated
            if updated.status in (SandboxStatus.FAILED, SandboxStatus.TERMINATED):
                logger.error(f"Pod '{handle.pod_name}' reached status {updated.status} before Running")
                raise RuntimeError(f"Pod {handle.pod_name} reached status {updated.status} before Running.")
            time.sleep(2)
        logger.error(f"Pod '{handle.pod_name}' timed out after {timeout}s waiting for Running status")
        raise TimeoutError(f"Pod {handle.pod_name} did not reach Running within {timeout}s.")

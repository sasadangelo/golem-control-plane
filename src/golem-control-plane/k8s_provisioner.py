# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Kubernetes implementation of the Provisioner interface."""

import logging
import os
import time

from kubernetes import client, config  # type: ignore[import-untyped]
from kubernetes.client.rest import ApiException  # type: ignore[import-untyped]
from models import AgentSpec, SandboxHandle, SandboxStatus
from provisioner import Provisioner

logger = logging.getLogger(__name__)


def _load_k8s_config() -> None:
    """Load kubeconfig from in-cluster env or local ~/.kube/config."""
    try:
        config.load_incluster_config()
        logger.info("Loaded in-cluster K8s config.")
    except config.ConfigException:
        config.load_kube_config()
        logger.info("Loaded local kubeconfig.")


class KubernetesProvisioner(Provisioner):
    """Creates one K8s Namespace + Pod per agent, with ResourceQuota and NetworkPolicy."""

    def __init__(self) -> None:
        _load_k8s_config()
        self._core = client.CoreV1Api()
        self._apps = client.AppsV1Api()
        self._networking = client.NetworkingV1Api()
        # Read at instantiation time so load_dotenv() in app.py runs first.
        self._runner_image = os.getenv("RUNNER_IMAGE", "localhost/golem-runner:v1")
        self._watsonx_api_key = os.getenv("WATSONX_API_KEY", "")
        self._watsonx_url = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
        self._watsonx_project_id = os.getenv("WATSONX_PROJECT_ID", "")
        self._watsonx_model_id = os.getenv("WATSONX_MODEL_ID", "openai/gpt-oss-120b")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def create_sandbox(self, spec: AgentSpec) -> SandboxHandle:
        """Create Namespace, ResourceQuota, NetworkPolicy and Pod for the agent."""
        handle = SandboxHandle(ttl_seconds=spec.ttl_seconds)
        logger.info("Creating sandbox %s", handle.agent_id)

        self._create_namespace(handle, spec)
        self._apply_resource_quota(handle)
        self._apply_network_policy(handle)
        self._create_pod(handle, spec)

        return handle

    def delete_sandbox(self, handle: SandboxHandle) -> None:
        """Delete the entire Namespace (cascades to all resources inside it)."""
        logger.info("Deleting sandbox namespace %s", handle.namespace)
        try:
            self._core.delete_namespace(handle.namespace)
        except ApiException as e:
            if e.status != 404:
                raise

    def get_status(self, handle: SandboxHandle) -> SandboxHandle:
        """Read the pod phase and map it to SandboxStatus."""
        try:
            pod = self._core.read_namespaced_pod(handle.pod_name, handle.namespace)
            phase = (pod.status.phase or "Unknown").lower()
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
        self._core.create_namespace(ns)
        logger.debug("Namespace %s created.", handle.namespace)

    def _apply_resource_quota(self, handle: SandboxHandle) -> None:
        quota = client.V1ResourceQuota(
            metadata=client.V1ObjectMeta(name="golem-quota", namespace=handle.namespace),
            spec=client.V1ResourceQuotaSpec(
                hard={"requests.cpu": "500m", "requests.memory": "512Mi", "limits.cpu": "1", "limits.memory": "1Gi"}
            ),
        )
        self._core.create_namespaced_resource_quota(handle.namespace, quota)
        logger.debug("ResourceQuota applied to %s.", handle.namespace)

    def _apply_network_policy(self, handle: SandboxHandle) -> None:
        policy = client.V1NetworkPolicy(
            metadata=client.V1ObjectMeta(name="default-deny-egress", namespace=handle.namespace),
            spec=client.V1NetworkPolicySpec(
                pod_selector=client.V1LabelSelector(),
                policy_types=["Egress"],
                egress=[
                    # Allow HTTPS egress so the agent can reach WatsonX and other
                    # external APIs. TODO Phase 2: restrict to specific CIDRs per skill.
                    client.V1NetworkPolicyEgressRule(
                        ports=[client.V1NetworkPolicyPort(port=443, protocol="TCP")],
                    ),
                    # Allow DNS resolution (UDP + TCP port 53).
                    client.V1NetworkPolicyEgressRule(
                        ports=[
                            client.V1NetworkPolicyPort(port=53, protocol="UDP"),
                            client.V1NetworkPolicyPort(port=53, protocol="TCP"),
                        ],
                    ),
                ],
            ),
        )
        self._networking.create_namespaced_network_policy(handle.namespace, policy)
        logger.debug("NetworkPolicy (allow-https+dns) applied to %s.", handle.namespace)

    def _create_pod(self, handle: SandboxHandle, spec: AgentSpec) -> None:
        agent_endpoint = f"http://{handle.pod_name}.{handle.namespace}.svc.cluster.local:8000"
        env_vars = [
            client.V1EnvVar(name="AGENT_ID", value=handle.agent_id),
            client.V1EnvVar(name="AGENT_NAME", value=spec.name),
            client.V1EnvVar(name="AGENT_ENDPOINT", value=agent_endpoint),
            client.V1EnvVar(name="SYSTEM_PROMPT", value=spec.system_prompt),
            client.V1EnvVar(name="ENABLED_SKILLS", value=",".join(spec.enabled_skills)),
            client.V1EnvVar(name="WATSONX_API_KEY", value=self._watsonx_api_key),
            client.V1EnvVar(name="WATSONX_URL", value=self._watsonx_url),
            client.V1EnvVar(name="WATSONX_PROJECT_ID", value=self._watsonx_project_id),
            client.V1EnvVar(name="WATSONX_MODEL_ID", value=self._watsonx_model_id),
        ]
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
                        image=self._runner_image,
                        image_pull_policy="IfNotPresent",
                        ports=[client.V1ContainerPort(container_port=8000)],
                        env=env_vars,
                        resources=client.V1ResourceRequirements(
                            requests={"cpu": "250m", "memory": "256Mi"},
                            limits={"cpu": "1", "memory": "1Gi"},
                        ),
                        liveness_probe=client.V1Probe(
                            http_get=client.V1HTTPGetAction(path="/health", port=8000),
                            initial_delay_seconds=15,
                            period_seconds=10,
                        ),
                    )
                ],
            ),
        )
        self._core.create_namespaced_pod(handle.namespace, pod)
        logger.debug("Pod %s created in namespace %s.", handle.pod_name, handle.namespace)

    def wait_for_running(self, handle: SandboxHandle, timeout: int = 120) -> SandboxHandle:
        """Block until the pod is Running or timeout expires."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            updated = self.get_status(handle)
            if updated.status == SandboxStatus.RUNNING:
                return updated
            if updated.status in (SandboxStatus.FAILED, SandboxStatus.TERMINATED):
                raise RuntimeError(f"Pod {handle.pod_name} reached status {updated.status} before Running.")
            time.sleep(2)
        raise TimeoutError(f"Pod {handle.pod_name} did not reach Running within {timeout}s.")

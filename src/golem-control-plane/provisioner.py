# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Abstract Provisioner interface for Golem sandbox management."""

from abc import ABC, abstractmethod

from models import AgentSpec, SandboxHandle


class Provisioner(ABC):
    """
    Abstract base class for sandbox provisioners.

    The only MVP implementation is KubernetesProvisioner.
    A DockerComposeProvisioner for single-machine development is planned for Phase 3.
    """

    @abstractmethod
    def create_sandbox(self, spec: AgentSpec) -> SandboxHandle:
        """
        Provision an isolated sandbox for the given agent spec.

        Args:
            spec: The agent specification (name, prompt, skills, mode, TTL).

        Returns:
            A SandboxHandle referencing the newly created sandbox.
        """

    @abstractmethod
    def delete_sandbox(self, handle: SandboxHandle) -> None:
        """
        Tear down the sandbox identified by the given handle.

        Args:
            handle: The SandboxHandle returned by create_sandbox.
        """

    @abstractmethod
    def get_status(self, handle: SandboxHandle) -> SandboxHandle:
        """
        Refresh and return the current status of a sandbox.

        Args:
            handle: The SandboxHandle to inspect.

        Returns:
            An updated SandboxHandle with the current status.
        """

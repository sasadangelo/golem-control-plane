# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Agent router — HTTP endpoints for sandbox lifecycle management."""

from application.services.agent_service import AgentService
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from interfaces.api.schemas import AgentStatusResponse, CreateAgentResponse, HandshakeRequest, HandshakeResponse


def make_router(agent_service: AgentService) -> APIRouter:
    """Wire the agent_service into the router and return it.

    Args:
        agent_service: The application-layer service to delegate to.

    Returns:
        A fully configured APIRouter ready to be included in the FastAPI app.
    """
    router = APIRouter(tags=["agents"])

    @router.post(path="/agents", response_model=CreateAgentResponse, status_code=201)
    async def create_agent(
        config: UploadFile = File(description="Runner config.yaml file."),  # noqa: B008
        ttl_seconds: int | None = Form(
            default=None,
            description="Sandbox TTL in seconds. Omit for a sandbox that never expires automatically.",
        ),
        agents_md: UploadFile | None = File(default=None, description="Optional AGENTS.md file."),  # noqa: B008
        skills: list[UploadFile] = File(default=[], description="Optional SKILL.md files (one per skill)."),  # noqa: B008
    ) -> CreateAgentResponse:
        """Provision a new isolated agent sandbox."""
        runner_config = (await config.read()).decode("utf-8")

        agents_md_content: str | None = None
        if agents_md is not None:
            agents_md_content = (await agents_md.read()).decode("utf-8")

        skills_content: dict[str, str] = {}
        for skill_file in skills:
            skill_name = (skill_file.filename or "skill").removesuffix(".md")
            skills_content[skill_name] = (await skill_file.read()).decode("utf-8")

        try:
            handle = agent_service.create_agent(
                runner_config=runner_config,
                ttl_seconds=ttl_seconds,
                agents_md=agents_md_content,
                skills=skills_content,
            )
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

        return CreateAgentResponse(
            agent_id=handle.agent_id,
            namespace=handle.namespace,
            status=handle.status,
        )

    @router.get("/agents/{agent_id}/status", response_model=AgentStatusResponse)
    async def get_agent_status(agent_id: str) -> AgentStatusResponse:
        """Return the current status of an agent sandbox."""
        try:
            handle = await agent_service.get_status(agent_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found.")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

        return AgentStatusResponse(
            agent_id=handle.agent_id,
            namespace=handle.namespace,
            status=handle.status,
            agent_card=handle.agent_card,
        )

    @router.delete("/agents/{agent_id}", status_code=204)
    async def delete_agent(agent_id: str) -> None:
        """Tear down the agent sandbox and deregister its Agent Card."""
        try:
            agent_service.delete_agent(agent_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found.")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

    @router.get(path="/agents", response_model=list[AgentStatusResponse])
    async def list_agents() -> list[AgentStatusResponse]:
        """List all known agent sandboxes with their current live status."""
        handles = await agent_service.list_agents()
        return [
            AgentStatusResponse(
                agent_id=h.agent_id,
                namespace=h.namespace,
                status=h.status,
                agent_card=h.agent_card,
            )
            for h in handles
        ]

    @router.get(path="/agents/{agent_id}/card")
    async def get_agent_card(agent_id: str) -> dict:
        """Return the A2A Agent Card for an agent (peer-discovery endpoint)."""
        try:
            return agent_service.get_card(agent_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Agent Card for {agent_id} not found.")

    @router.post(path="/agents/{agent_id}/handshake", response_model=HandshakeResponse)
    async def agent_handshake(agent_id: str, body: HandshakeRequest) -> HandshakeResponse:
        """Runner push: register the Agent Card and mark sandbox as RUNNING."""
        try:
            agent_service.register_handshake(agent_id, body.card)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found.")

        return HandshakeResponse(registered=True, agent_id=agent_id)

    return router

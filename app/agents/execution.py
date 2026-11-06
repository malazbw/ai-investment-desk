"""
Agent execution - runs agents in parallel
"""
import asyncio
import time
from typing import Callable, List, Optional
from app.agents.base import BaseAgent, AgentContext, AgentOutput
import logging

logger = logging.getLogger(__name__)


async def execute_agents_parallel(
    agents: List[BaseAgent],
    context: AgentContext,
) -> List[AgentOutput]:
    """
    Execute multiple agents in parallel and collect results.

    Args:
        agents: List of agents to execute
        context: Context to pass to each agent

    Returns:
        List of AgentOutput from each agent
    """
    if not agents:
        logger.warning("No agents to execute")
        return []

    logger.info(f"Executing {len(agents)} agents in parallel")

    session_factory = context.metadata.get("db_factory")
    if "db" in context.metadata and not callable(session_factory):
        logger.warning(
            "Running agents sequentially because a shared database session was provided"
        )
        return [
            await _run_agent(agent, context, None)
            for agent in agents
        ]

    tasks = [
        _run_agent(
            agent,
            context,
            session_factory if callable(session_factory) else None,
        )
        for agent in agents
    ]
    outputs = await asyncio.gather(*tasks)

    logger.info(f"Agent execution completed. Results: {len(outputs)}")
    return outputs


async def _run_agent(
    agent: BaseAgent,
    context: AgentContext,
    session_factory: Optional[Callable],
) -> AgentOutput:
    db = session_factory() if session_factory is not None else None
    agent_context = context
    if db is not None:
        metadata = {
            key: value
            for key, value in context.metadata.items()
            if key != "db_factory"
        }
        metadata["db"] = db
        agent_context = AgentContext(
            user_message=context.user_message,
            portfolio_data=context.portfolio_data,
            metadata=metadata,
        )

    try:
        return await _execute_with_timing(agent, agent_context)
    except Exception as exc:
        logger.error("Agent %s failed: %s", agent.name, exc)
        return agent._create_output(success=False, data={}, error=str(exc))
    finally:
        if db is not None:
            db.close()


async def _execute_with_timing(
    agent: BaseAgent,
    context: AgentContext,
) -> AgentOutput:
    """Execute agent and measure execution time"""
    start_time = time.time()
    logger.info(f"[AGENT-EXEC] Starting {agent.name} agent")
    try:
        output = await agent.execute(context)
        execution_time = (time.time() - start_time) * 1000  # ms
        output.execution_time_ms = execution_time
        logger.info(
            f"[AGENT-EXEC] ✓ {agent.name} completed in {execution_time:.2f}ms - success={output.success}"
        )
        if output.success:
            logger.debug(f"[AGENT-EXEC] {agent.name} output keys: {list(output.data.keys())}")
        return output
    except Exception as e:
        execution_time = (time.time() - start_time) * 1000
        logger.error(f"[AGENT-EXEC] ✗ {agent.name} error after {execution_time:.2f}ms: {e}")
        raise

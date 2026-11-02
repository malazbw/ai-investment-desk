"""
Agent execution - runs agents in parallel
"""
import asyncio
import time
from typing import List
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

    # Execute all agents concurrently
    tasks = [_execute_with_timing(agent, context) for agent in agents]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results, handling exceptions
    outputs = []
    for agent, result in zip(agents, results):
        if isinstance(result, Exception):
            logger.error(f"Agent {agent.name} failed: {result}")
            output = agent._create_output(
                success=False,
                data={},
                error=str(result),
            )
        else:
            output = result
        outputs.append(output)

    logger.info(f"Agent execution completed. Results: {len(outputs)}")
    return outputs


async def _execute_with_timing(
    agent: BaseAgent,
    context: AgentContext,
) -> AgentOutput:
    """Execute agent and measure execution time"""
    start_time = time.time()
    try:
        output = await agent.execute(context)
        execution_time = (time.time() - start_time) * 1000  # ms
        output.execution_time_ms = execution_time
        logger.info(
            f"Agent {agent.name} completed in {execution_time:.2f}ms"
        )
        return output
    except Exception as e:
        execution_time = (time.time() - start_time) * 1000
        logger.error(f"Agent {agent.name} error after {execution_time:.2f}ms: {e}")
        raise

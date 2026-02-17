"""Autonomous AI Agent with ReAct-style reasoning loop."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from openai import AsyncAzureOpenAI, AsyncOpenAI

from spot_agent.config import AgentConfig
from spot_agent.core.memory import AgentMemory
from spot_agent.core.task_queue import Task, TaskQueue, TaskStatus
from spot_agent.logging import get_logger

log = get_logger(__name__)

SYSTEM_PROMPT = """You are an autonomous AI agent running on Azure SPOT VMs. You execute tasks assigned by users using the tools available to you.

When given a task:
1. OBSERVE: Understand the task requirements
2. THINK: Plan your approach step by step
3. ACT: Execute using available tools
4. REFLECT: Evaluate the result and decide if the task is complete

Available tools will be provided as function definitions. Use them to accomplish tasks.

If a task requires multiple steps, break it down and execute each step.
Always provide clear, structured results.

You can write code, search the internet, manage files, and execute shell commands.
If you need a capability you don't have, you can request the creation of a new tool."""

MAX_ITERATIONS = 50


class AutonomousAgent:
    """ReAct-style autonomous agent that processes tasks using LLM reasoning and tools."""

    def __init__(
        self,
        config: AgentConfig,
        task_queue: TaskQueue,
        memory: AgentMemory,
        tool_registry: Any = None,
    ) -> None:
        self.config = config
        self.task_queue = task_queue
        self.memory = memory
        self.tool_registry = tool_registry
        self._running = False

        # Initialize LLM client (lazy — may be None if not configured)
        self._llm: AsyncOpenAI | AsyncAzureOpenAI | None = None
        llm_cfg = getattr(config, "llm", None)
        if llm_cfg and getattr(llm_cfg, "api_key", None):
            provider = getattr(llm_cfg, "provider", "openai")
            if provider == "azure_openai":
                self._llm = AsyncAzureOpenAI(
                    api_key=llm_cfg.api_key,
                    azure_endpoint=llm_cfg.api_base,
                    api_version="2024-02-01",
                )
            else:
                client_kwargs: dict[str, Any] = {"api_key": llm_cfg.api_key}
                if llm_cfg.api_base:
                    client_kwargs["base_url"] = llm_cfg.api_base
                self._llm = AsyncOpenAI(**client_kwargs)

    async def _get_tool_definitions(self) -> list[dict[str, Any]]:
        """Get OpenAI-compatible tool definitions from the registry."""
        if not self.tool_registry:
            return []
        tools = []
        for tool in self.tool_registry.list_tools():
            tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters_schema,
                },
            })
        return tools

    async def _call_llm(self, messages: list[dict], tools: list[dict] | None = None) -> Any:
        """Make a call to the LLM."""
        if not self._llm:
            raise RuntimeError("LLM client not configured — set LLM_API_KEY")

        llm_cfg = self.config.llm
        kwargs: dict[str, Any] = {
            "model": getattr(llm_cfg, "model", "gpt-4o"),
            "messages": messages,
            "max_tokens": getattr(llm_cfg, "max_tokens", 4096),
            "temperature": getattr(llm_cfg, "temperature", 0.1),
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = await self._llm.chat.completions.create(**kwargs)
        return response.choices[0].message

    async def _execute_tool(self, name: str, arguments: str) -> str:
        """Execute a tool by name with the given arguments."""
        if not self.tool_registry:
            return json.dumps({"error": "No tool registry configured"})

        tool = self.tool_registry.get_tool(name)
        if not tool:
            return json.dumps({"error": f"Tool '{name}' not found"})

        try:
            args = json.loads(arguments)
            result = await tool.execute(**args)
            return json.dumps({"result": result}, default=str)
        except Exception as exc:
            log.error("tool_execution_error", tool=name, error=str(exc))
            return json.dumps({"error": str(exc)})

    async def execute_task(self, task: Task) -> str:
        """Execute a single task using the ReAct loop."""
        log.info("executing_task", task_id=task.id, description=task.description)
        self.task_queue.mark_in_progress(task.id)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]

        # Load conversation chain from parent tasks
        if task.parent_id:
            chain = self.task_queue.get_conversation_chain(task.id)
            # Add all ancestor tasks (except current) as conversation context
            for ancestor in chain[:-1]:
                messages.append({
                    "role": "user",
                    "content": f"Execute this task: {ancestor.description}",
                })
                if ancestor.result:
                    messages.append({
                        "role": "assistant",
                        "content": ancestor.result,
                    })
        else:
            # No parent — add general memory context
            context = self.memory.get_context_for_llm(limit=10)
            messages.extend(context)

        # Add the current task
        messages.append({
            "role": "user",
            "content": f"Execute this task: {task.description}",
        })

        tools = await self._get_tool_definitions()
        final_result = ""

        for iteration in range(MAX_ITERATIONS):
            log.debug("react_iteration", task_id=task.id, iteration=iteration)

            response = await self._call_llm(messages, tools=tools or None)

            # If the LLM wants to call tools
            if response.tool_calls:
                messages.append({
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                        }
                        for tc in response.tool_calls
                    ],
                })

                # Execute each tool call
                for tool_call in response.tool_calls:
                    result = await self._execute_tool(
                        tool_call.function.name, tool_call.function.arguments
                    )
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    })
            else:
                # No tool calls — the agent is providing its final answer
                final_result = response.content or ""
                break

        self.memory.add_message("user", f"Task: {task.description}")
        self.memory.add_message("assistant", final_result)

        return final_result

    async def run(self) -> None:
        """Main autonomous loop — continuously process tasks."""
        self._running = True
        log.info("agent_started", name=self.config.name)

        # Load memory
        try:
            await self.memory.load()
        except Exception:
            log.info("starting_with_fresh_memory")

        while self._running:
            task = self.task_queue.next()

            if task is None:
                await asyncio.sleep(2)
                continue

            try:
                result = await self.execute_task(task)
                self.task_queue.mark_completed(task.id, result)
                self.memory.add_task_outcome(
                    task.id, task.description, success=True, result=result
                )
                log.info("task_completed", task_id=task.id)
            except Exception as exc:
                error_msg = str(exc)
                self.task_queue.mark_failed(task.id, error_msg)
                self.memory.add_task_outcome(
                    task.id, task.description, success=False, error=error_msg
                )
                log.error("task_failed", task_id=task.id, error=error_msg)

            # Periodically save memory
            try:
                await self.memory.save()
            except Exception as exc:
                log.warning("memory_save_failed", error=str(exc))

    def stop(self) -> None:
        """Stop the agent loop."""
        self._running = False
        log.info("agent_stopping")

    def get_state(self) -> dict[str, Any]:
        """Get serializable agent state for checkpointing."""
        return {
            "task_queue": self.task_queue.to_dict(),
            "memory": self.memory.to_dict(),
        }

    async def restore_state(self, state: dict[str, Any]) -> None:
        """Restore agent state from a checkpoint."""
        if "task_queue" in state:
            self.task_queue = TaskQueue.from_dict(state["task_queue"])
        if "memory" in state:
            self.memory = AgentMemory.from_dict(state["memory"], self.config.azure)
        log.info("agent_state_restored")

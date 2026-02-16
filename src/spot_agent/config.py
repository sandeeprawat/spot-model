"""Configuration management for SPOT Agent."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class AzureConfig(BaseSettings):
    """Azure-specific configuration."""

    model_config = {"env_prefix": "AZURE_"}

    subscription_id: str = Field(description="Azure subscription ID")
    resource_group: str = Field(description="Azure resource group name")
    location: str = Field(default="eastus", description="Azure region")
    storage_account: str = Field(description="Azure Storage account name")
    storage_container: str = Field(
        default="spot-agent-state", description="Blob container for state"
    )
    vm_size: str = Field(default="Standard_D2s_v3", description="VM size for SPOT instances")
    max_spot_price: float = Field(
        default=-1, description="Max price for SPOT VM (-1 = on-demand cap)"
    )


class LLMConfig(BaseSettings):
    """LLM provider configuration."""

    model_config = {"env_prefix": "LLM_"}

    provider: str = Field(default="openai", description="LLM provider: openai or azure_openai")
    api_key: str = Field(description="API key for the LLM provider")
    model: str = Field(default="gpt-4o", description="Model name to use")
    api_base: str | None = Field(default=None, description="Custom API base URL")
    max_tokens: int = Field(default=4096, description="Max tokens per response")
    temperature: float = Field(default=0.1, description="Sampling temperature")


class MCPConfig(BaseSettings):
    """MCP server configuration."""

    model_config = {"env_prefix": "MCP_"}

    servers: list[str] = Field(
        default_factory=list,
        description="List of MCP server URIs to connect to",
    )


class AgentConfig(BaseSettings):
    """Top-level agent configuration."""

    model_config = {"env_prefix": "AGENT_"}

    name: str = Field(default="spot-agent", description="Agent instance name")
    plugins_dir: str = Field(default="plugins", description="Directory for dynamic plugins")
    checkpoint_interval: int = Field(
        default=60, description="Checkpoint interval in seconds"
    )
    max_task_retries: int = Field(default=3, description="Max retries per task")
    log_level: str = Field(default="INFO", description="Logging level")

    azure: AzureConfig = Field(default_factory=AzureConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)

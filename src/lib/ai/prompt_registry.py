import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field

from src.config import paths


class PromptMetadata(BaseModel):
    id: str
    description: str
    owner: str
    version: Optional[str] = "1.0.0"


class ModelConfig(BaseModel):
    temperature: float = 0.7
    model: str = "active_profile"


class MessageTemplate(BaseModel):
    role: str
    content: str


class PromptDefinition(BaseModel):
    meta: PromptMetadata
    llm_config: ModelConfig = Field(default_factory=ModelConfig, alias="model_config")
    messages: List[MessageTemplate]


class PromptRegistry:
    def __init__(self):
        self._prompts: Dict[str, PromptDefinition] = {}

    def get_prompt_path(self, prompt_id: str) -> Path:
        """
        Resolves prompt ID to file path.
        Example: "dashboard.inbox.summarize" -> .../prompts/dashboard/inbox/summarize.yaml
        """
        parts = prompt_id.split(".")
        return paths.get_prompts_dir().joinpath(*parts).with_suffix(".yaml")

    def load_prompt_definition(self, prompt_id: str) -> PromptDefinition:
        """Loads and parses the prompt YAML definition."""
        path = self.get_prompt_path(prompt_id)
        if not path.exists():
            raise FileNotFoundError(f"Prompt ID '{prompt_id}' not found at {path}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            return PromptDefinition(**data)
        except Exception as e:
            raise ValueError(f"Failed to parse prompt '{prompt_id}': {str(e)}")

    def _interpolate(self, text: str, variables: Dict[str, Any]) -> str:
        """
        Simple double-brace interpolation.
        Replaces {{key}} with value.
        """
        if not variables:
            return text

        result = text
        for key, value in variables.items():
            pattern = f"{{{{{key}}}}}"
            result = result.replace(pattern, str(value))
        return result

    def render_prompt(
        self, prompt_id: str, variables: Dict[str, Any] = None
    ) -> Tuple[List[Dict[str, str]], ModelConfig]:
        """
        Loads a prompt and interpolates variables into the messages.

        Args:
            prompt_id: The ID of the prompt to load.
            variables: Dictionary of variables to inject.

        Returns:
            Tuple of (messages_list, model_config)
        """
        if variables is None:
            variables = {}

        definition = self.load_prompt_definition(prompt_id)

        rendered_messages = []
        for msg in definition.messages:
            rendered_content = self._interpolate(msg.content, variables)
            rendered_messages.append({"role": msg.role, "content": rendered_content})

        return rendered_messages, definition.llm_config


# Global instance
registry = PromptRegistry()

"""
HERMES Prompt Generator
Creates and customizes agent prompts from templates.
Persists generated prompts for reuse.
"""

import json
import os
import hashlib
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List
from .task_parser import TaskType, SubTask


@dataclass
class PromptTemplate:
    """A reusable prompt template for a specific agent type."""
    name: str
    task_type: TaskType
    base_prompt: str
    specializations: List[str]
    context_keywords: List[str]
    variables: List[str]  # Placeholders like {task_description}, {context}

    def render(self, variables: Dict[str, str]) -> str:
        """Render the template with provided variables."""
        prompt = self.base_prompt
        for key, value in variables.items():
            placeholder = f"{{{key}}}"
            prompt = prompt.replace(placeholder, str(value))
        return prompt


@dataclass
class GeneratedPrompt:
    """A prompt generated from a template for a specific task."""
    prompt_id: str
    template_name: str
    task_type: str
    rendered_prompt: str
    variables_used: Dict[str, str]
    created_at: str
    task_hash: str  # For detecting identical tasks


class PromptGenerator:
    """
    Generates agent prompts from templates.
    Supports template loading, customization, and persistence.
    """

    def __init__(self, knowledge_base_path: str):
        """
        Initialize the prompt generator.

        Args:
            knowledge_base_path: Path to the knowledge_base directory
        """
        self.kb_path = Path(knowledge_base_path)
        self.templates_path = self.kb_path / "templates"
        self.prompts_path = self.kb_path / "prompts"

        # Ensure directories exist
        self.templates_path.mkdir(parents=True, exist_ok=True)
        self.prompts_path.mkdir(parents=True, exist_ok=True)

        # Cache loaded templates
        self._templates: Dict[str, PromptTemplate] = {}
        self._load_templates()

    def _load_templates(self) -> None:
        """Load all templates from the templates directory."""
        for template_file in self.templates_path.glob("*.json"):
            try:
                with open(template_file, 'r') as f:
                    data = json.load(f)

                template = PromptTemplate(
                    name=data['name'],
                    task_type=TaskType(data['task_type']),
                    base_prompt=data['base_prompt'],
                    specializations=data.get('specializations', []),
                    context_keywords=data.get('context_keywords', []),
                    variables=data.get('variables', [])
                )
                self._templates[template.name] = template
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                print(f"Warning: Failed to load template {template_file}: {e}")

    def get_template(self, name: str) -> Optional[PromptTemplate]:
        """Get a template by name."""
        return self._templates.get(name)

    def get_template_for_task_type(self, task_type: TaskType) -> Optional[PromptTemplate]:
        """Get the first template matching a task type."""
        for template in self._templates.values():
            if template.task_type == task_type:
                return template
        return None

    def list_templates(self) -> List[str]:
        """List all available template names."""
        return list(self._templates.keys())

    def generate_prompt(
        self,
        subtask: SubTask,
        template_name: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> GeneratedPrompt:
        """
        Generate a prompt for a subtask.

        Args:
            subtask: The subtask to generate a prompt for
            template_name: Specific template to use (auto-selects if None)
            additional_context: Extra context to include in the prompt

        Returns:
            GeneratedPrompt with the rendered prompt
        """
        # Select template
        if template_name:
            template = self.get_template(template_name)
        else:
            template = self.get_template_for_task_type(subtask.task_type)

        # If no template found, use default prompt generation
        if not template:
            return self._generate_default_prompt(subtask, additional_context)

        # Prepare variables
        variables = self._prepare_variables(subtask, additional_context)

        # Render the prompt
        rendered = template.render(variables)

        # Create prompt ID and hash
        task_hash = self._hash_task(subtask)
        prompt_id = f"prompt_{task_hash[:12]}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        generated = GeneratedPrompt(
            prompt_id=prompt_id,
            template_name=template.name,
            task_type=subtask.task_type.value,
            rendered_prompt=rendered,
            variables_used=variables,
            created_at=datetime.now().isoformat(),
            task_hash=task_hash
        )

        return generated

    def _generate_default_prompt(
        self,
        subtask: SubTask,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> GeneratedPrompt:
        """Generate a default prompt when no template is available."""
        context_str = ""
        if additional_context:
            context_str = f"\n\nAdditional Context:\n{json.dumps(additional_context, indent=2)}"

        task_context_str = ""
        if subtask.context:
            task_context_str = f"\n\nTask Context:\n{json.dumps(subtask.context, indent=2)}"

        rendered = f"""You are a HERMES agent specialized in {subtask.task_type.value} tasks.

## Your Task
{subtask.description}

## Task Type
{subtask.task_type.value}

## Instructions
- Focus on completing the task efficiently
- Provide clear, actionable outputs
- Report any issues or blockers encountered
{context_str}{task_context_str}
"""

        task_hash = self._hash_task(subtask)
        prompt_id = f"prompt_default_{task_hash[:12]}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        return GeneratedPrompt(
            prompt_id=prompt_id,
            template_name="default",
            task_type=subtask.task_type.value,
            rendered_prompt=rendered,
            variables_used={'task_description': subtask.description},
            created_at=datetime.now().isoformat(),
            task_hash=task_hash
        )

    def _prepare_variables(
        self,
        subtask: SubTask,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        """Prepare template variables from subtask and context."""
        variables = {
            'task_description': subtask.description,
            'task_type': subtask.task_type.value,
            'task_id': subtask.id,
        }

        # Add context as formatted string
        if subtask.context:
            variables['context'] = json.dumps(subtask.context, indent=2)
        else:
            variables['context'] = "No additional context provided."

        # Add files if present
        files = subtask.context.get('files', [])
        if files:
            variables['files'] = ', '.join(files)
        else:
            variables['files'] = "No specific files mentioned."

        # Add technologies if present
        tech = subtask.context.get('technologies', [])
        if tech:
            variables['technologies'] = ', '.join(tech)
        else:
            variables['technologies'] = "No specific technologies mentioned."

        # Add any additional context
        if additional_context:
            variables['additional_context'] = json.dumps(additional_context, indent=2)
        else:
            variables['additional_context'] = ""

        return variables

    def _hash_task(self, subtask: SubTask) -> str:
        """Create a hash of a task for deduplication."""
        content = f"{subtask.task_type.value}:{subtask.description}"
        return hashlib.sha256(content.encode()).hexdigest()

    def save_prompt(self, prompt: GeneratedPrompt) -> str:
        """
        Save a generated prompt to the knowledge base.

        Args:
            prompt: The prompt to save

        Returns:
            Path to the saved prompt file
        """
        filename = f"{prompt.prompt_id}.json"
        filepath = self.prompts_path / filename

        data = {
            'prompt_id': prompt.prompt_id,
            'template_name': prompt.template_name,
            'task_type': prompt.task_type,
            'rendered_prompt': prompt.rendered_prompt,
            'variables_used': prompt.variables_used,
            'created_at': prompt.created_at,
            'task_hash': prompt.task_hash
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

        return str(filepath)

    def load_prompt(self, prompt_id: str) -> Optional[GeneratedPrompt]:
        """
        Load a previously saved prompt.

        Args:
            prompt_id: The ID of the prompt to load

        Returns:
            GeneratedPrompt if found, None otherwise
        """
        filepath = self.prompts_path / f"{prompt_id}.json"
        if not filepath.exists():
            return None

        with open(filepath, 'r') as f:
            data = json.load(f)

        return GeneratedPrompt(
            prompt_id=data['prompt_id'],
            template_name=data['template_name'],
            task_type=data['task_type'],
            rendered_prompt=data['rendered_prompt'],
            variables_used=data['variables_used'],
            created_at=data['created_at'],
            task_hash=data['task_hash']
        )

    def find_similar_prompt(self, subtask: SubTask) -> Optional[GeneratedPrompt]:
        """
        Find a previously generated prompt for a similar task.

        Args:
            subtask: The subtask to find a similar prompt for

        Returns:
            GeneratedPrompt if a similar one exists, None otherwise
        """
        task_hash = self._hash_task(subtask)

        for prompt_file in self.prompts_path.glob("*.json"):
            try:
                with open(prompt_file, 'r') as f:
                    data = json.load(f)
                if data.get('task_hash') == task_hash:
                    return self.load_prompt(data['prompt_id'])
            except (json.JSONDecodeError, KeyError):
                continue

        return None

    def save_template(self, template: PromptTemplate) -> str:
        """
        Save a template to the templates directory.

        Args:
            template: The template to save

        Returns:
            Path to the saved template file
        """
        filename = f"{template.name}.json"
        filepath = self.templates_path / filename

        data = {
            'name': template.name,
            'task_type': template.task_type.value,
            'base_prompt': template.base_prompt,
            'specializations': template.specializations,
            'context_keywords': template.context_keywords,
            'variables': template.variables
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

        # Update cache
        self._templates[template.name] = template

        return str(filepath)

    def create_template(
        self,
        name: str,
        task_type: TaskType,
        base_prompt: str,
        specializations: Optional[List[str]] = None,
        context_keywords: Optional[List[str]] = None
    ) -> PromptTemplate:
        """
        Create and save a new template.

        Args:
            name: Template name
            task_type: Type of tasks this template handles
            base_prompt: The base prompt text (can include {variables})
            specializations: Agent specializations
            context_keywords: Keywords that indicate relevance

        Returns:
            The created PromptTemplate
        """
        # Extract variables from base_prompt
        import re
        variables = re.findall(r'\{(\w+)\}', base_prompt)

        template = PromptTemplate(
            name=name,
            task_type=task_type,
            base_prompt=base_prompt,
            specializations=specializations or [],
            context_keywords=context_keywords or [],
            variables=list(set(variables))
        )

        self.save_template(template)
        return template

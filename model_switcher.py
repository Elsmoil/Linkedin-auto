# model_switcher.py
import os

def get_model_for_task(task_type: str) -> str:
    """
    Returns the most suitable free model for the task from OpenRouter.
    """
    mapping = {
        "analysis": "openai/gpt-4o",
        "writing": "google/gemini-pro",
        "code": "mistralai/mixtral-8x7b",
        "edit": "anthropic/claude-3-haiku",
    }
    return mapping.get(task_type, "openai/gpt-4o")  # Default fallback
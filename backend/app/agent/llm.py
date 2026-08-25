from functools import lru_cache

from langchain_core.utils.function_calling import convert_to_openai_function
from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.tools import SPECS, ToolSpec


class PlannerUnavailable(Exception):
    """The planner model is not configured or is unavailable."""


def _schema_of(spec: ToolSpec) -> dict:
    function = convert_to_openai_function(spec.params)
    function["name"] = spec.name
    function["description"] = spec.description

    parameters = function.get("parameters", {})
    for hidden in spec.agent_hidden:
        parameters.get("properties", {}).pop(hidden, None)
    parameters["required"] = [
        name for name in parameters.get("required", []) if name not in spec.agent_hidden
    ]
    return {"type": "function", "function": function}


@lru_cache
def planner():
    """Planner bound to every registered tool. Adding or removing tools needs no change here."""
    settings = get_settings()
    if not settings.openai_api_key:
        raise PlannerUnavailable(
            "OPENAI_API_KEY is not configured; chat instructions are unavailable"
        )

    model = ChatOpenAI(
        model=settings.planner_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        # Only reasoning models accept it; leave PLANNER_REASONING empty for the others
        reasoning_effort=settings.planner_reasoning or None,
    )
    return model.bind_tools([_schema_of(spec) for spec in SPECS])

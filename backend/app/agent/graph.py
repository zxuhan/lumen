from functools import lru_cache
from typing import TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from app.agent.llm import planner
from app.agent.plan import PlanError, validate
from app.services import tools as tool_service
from app.tools import UnknownTool, label_of

_SYSTEM = """You are a photo retouching assistant for e-commerce images. You carry out the user's
editing requests by calling tools.

Rules:
- Use only the tools provided. You may schedule several steps at once, calling them in the order
  they should complete; by default each step depends on the previous one.
- Don't split into several steps what one step can do. At most 8 steps.
- Fill in missing parameters from the canvas info and common sense; don't ask the user about
  parameters you can infer.
- Layers and selections are independent: layer_id decides which layer to change, the selection
  decides which area. When the user names a layer (e.g. "Object 2", "Background", "Subject"),
  put its id or name in layer_id.
- When the canvas summary shows an existing selection, that is the object the user wants to
  change: call erase_region, replace_region, or promote_object_to_layer directly. Don't ask the
  user to reselect, and don't guess whether the selection is accurate. These tools also work
  without a selection, in which case they apply to the whole target layer.
- When one request changes several layers, split it into one step per layer, each with a single
  layer_id.
- To change a color, swap a material, or turn something into something else, use replace_region
  and name the layer_id; use replace_background only to replace the whole background.
  adjust_image only adjusts brightness and color temperature; it doesn't recolor.
- Use flip_layer to flip the image; use rotate_layer when an angle is given.
- When the user asks to split layers or make an object its own layer, use split_layers or
  promote_object_to_layer.
- split_layers doesn't split out text by default; pass include_text only when the user
  explicitly asks for it.
- To change a text layer's copy, font size, or color, use set_layer_text and name the layer.
- For marketing images, main images, scene images, model shots, or posters, use
  generate_marketing with kind product / scene / model / poster respectively. Results only go
  to the image wall.
- To change sizes, produce ad assets, or output 1:1 / 4:5 / 9:16, use prepare_delivery_sizes;
  don't crop the subject, and don't use crop_canvas.
- To apply the same background removal, background replacement, color adjustment, upscale,
  expansion, or resize to multiple images, use batch_process. Don't use it for single-image
  retouching, marketing images, region edits, or layer splitting.
- When calling tools, don't output explanations or tool names. Only if the instruction is
  unrelated to photo editing, or the existing tools really can't do it, explain in one sentence
  in English, without mentioning internal parameters.

Current canvas: {context}"""

_FALLBACK_REPLY = (
    "I didn't quite understand that instruction. Try rephrasing it or being more specific."
)
_REFUSAL_LIMIT = 60


class AgentState(TypedDict):
    goal: str
    context: str
    plan: list[dict]
    reply: str


async def _plan(state: AgentState) -> AgentState:
    message = await planner().ainvoke(
        [
            SystemMessage(_SYSTEM.format(context=state["context"])),
            HumanMessage(state["goal"]),
        ]
    )
    return {
        "plan": [{"tool": call["name"], "params": call["args"]} for call in message.tool_calls],
        "reply": _text_of(message),
    }


def _verify(state: AgentState) -> AgentState:
    """Plans from the model are always validated server-side and never executed directly."""
    try:
        return {"plan": validate(state["plan"])}
    except (UnknownTool, tool_service.InvalidParams, PlanError) as exc:
        return {"plan": [], "reply": f"This step can't be run right now: {exc}"}


@lru_cache
def _graph():
    builder = StateGraph(AgentState)
    builder.add_node("plan", _plan)
    builder.add_node("verify", _verify)

    builder.add_edge(START, "plan")
    builder.add_edge("plan", "verify")
    builder.add_edge("verify", END)
    return builder.compile()


async def run(goal: str, context: str) -> tuple[str, list[dict]]:
    """Plan and validate one instruction turn; return the reply and the not-yet-dispatched plan."""
    state = await _graph().ainvoke({"goal": goal, "context": context, "plan": [], "reply": ""})
    return spoken(state["reply"], state["plan"]), state["plan"]


def spoken(reply: str, plan: list[dict]) -> str:
    """With a plan, describe its steps; otherwise use the fallback or a one-sentence refusal."""
    text = (reply or "").strip()
    if plan:
        if text and text != _FALLBACK_REPLY:
            return text
        labels = ", ".join(label_of(step["tool"], step.get("params")) for step in plan)
        if len(plan) > 1:
            return f"Here's the plan: {labels}. Confirm to start."
        return f"On it: {labels}."
    return _one_sentence(text) if text else _FALLBACK_REPLY


def _one_sentence(text: str) -> str:
    for sep in (".", "!", "?", "\n"):
        head, found, _ = text.partition(sep)
        if found and head.strip():
            return head.strip() + (sep if sep != "\n" else ".")
    if len(text) > _REFUSAL_LIMIT:
        return text[:_REFUSAL_LIMIT].rstrip() + "…"
    return text


def _text_of(message: AIMessage) -> str:
    if isinstance(message.content, str):
        return message.content.strip()
    return "".join(
        block.get("text", "") for block in message.content if isinstance(block, dict)
    ).strip()

"""EM LLM call wrapper — mirrors voss/eval/judge.py:judge_run (O5-03, OEM-03).

Async `em_plan(...)` calls provider.complete with response_format=EMPlanResponse
and temperature=0.0. On ParseError or parsed=None, returns a Noop fallback
(never raises for parse failures — only other exceptions bubble).
"""
from __future__ import annotations

from pathlib import Path

from voss.template_render import render_package_template
from voss.harness.prompt_override import default_runtime_vars, load_prompt
from voss_runtime.exceptions import ParseError
from voss_runtime.providers.base import ModelProvider

from .schema import EMPlanResponse, NoopOp


EM_SYSTEM = render_package_template(
    "voss",
    "templates/prompts/em_system.txt.jinja",
    {},
)


async def em_plan(
    *,
    provider: ModelProvider,
    model: str,
    idea: str,
    snapshot: str,
    roster_descriptions: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> EMPlanResponse:
    """Call the EM LLM and parse the structured response.

    On ParseError or parsed=None, returns EMPlanResponse(ops=[NoopOp(reason="parse_failure")]).
    On other exceptions, re-raises (the loop's responsibility to handle).
    """
    user_msg = render_package_template(
        "voss",
        "templates/prompts/em_user.md.jinja",
        {
            "idea": idea,
            "snapshot": snapshot,
            "roster": list(roster_descriptions.items()) if roster_descriptions else [],
        },
    )

    # Prompt resolved at load time so a project copy under .voss/prompts/
    # is honored; absent copy is byte-identical to EM_SYSTEM (R5). Callers
    # with a real workspace root pass cwd; None falls back to process cwd.
    prompt_root = (cwd or Path.cwd()).resolve()
    system = load_prompt(
        "em_system",
        cwd=prompt_root,
        runtime_vars=default_runtime_vars("em", prompt_root),
    )
    try:
        resp = await provider.complete(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            model=model,
            response_format=EMPlanResponse,
            temperature=0.0,
        )
    except ParseError:
        return EMPlanResponse(ops=[NoopOp(op="noop", reason="parse_failure")])

    if resp.parsed is None:
        return EMPlanResponse(ops=[NoopOp(op="noop", reason="parse_failure")])

    return resp.parsed

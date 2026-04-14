from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI


def build_risk_prompt(context: dict[str, Any]) -> str:
    return (
        "You are an operations risk assistant for SUT settlement.\n"
        "Write a concise high-level explanation for business users.\n"
        "Output sections with short bullets:\n"
        "1) Why this campaign is flagged\n"
        "2) Criteria triggered\n"
        "3) Evidence from data\n"
        "4) What operations should do next (priority order)\n"
        "Use plain language and avoid technical jargon.\n\n"
        f"Campaign context:\n{context}"
    )


def build_risk_fields_prompt(context: dict[str, Any]) -> str:
    return (
        "You are an operations risk assistant for SUT settlement.\n"
        "Generate business-friendly risk reason and next action.\n"
        "Return ONLY valid JSON with exact keys:\n"
        '{ "risk_reasons": "<string>", "next_actions": "<string>" }\n'
        "Rules:\n"
        "- Explain why campaign is risky in plain language.\n"
        "- Mention triggered criteria and evidence.\n"
        "- Keep concise and actionable.\n"
        "- next_actions should be prioritized steps in one short sentence.\n\n"
        f"Campaign context:\n{context}"
    )


def _extract_json_payload(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def _client_and_model() -> tuple[OpenAI, str] | None:
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("api_key")
    model = os.getenv("OPENAI_MODEL") or os.getenv("model") or "gpt-4.1-nano"
    if not api_key:
        return None
    return OpenAI(api_key=api_key), model


def generate_ai_risk_fields(context: dict[str, Any]) -> tuple[str, str] | None:
    configured = _client_and_model()
    if configured is None:
        return None
    client, model = configured
    try:
        response = client.responses.create(
            model=model,
            input=build_risk_fields_prompt(context),
            max_output_tokens=220,
        )
        text = getattr(response, "output_text", "").strip()
        payload = _extract_json_payload(text)
        if payload is None:
            return None
        reasons = str(payload.get("risk_reasons", "")).strip()
        actions = str(payload.get("next_actions", "")).strip()
        if not reasons or not actions:
            return None
        return reasons, actions
    except Exception:
        return None


def generate_ai_risk_guidance(context: dict[str, Any]) -> str | None:
    configured = _client_and_model()
    if configured is None:
        return None
    client, model = configured

    try:
        response = client.responses.create(
            model=model,
            input=build_risk_prompt(context),
            max_output_tokens=350,
        )
        text = getattr(response, "output_text", "").strip()
        return text or None
    except Exception:
        return None

#!/usr/bin/env python3
"""Public model-access shim for the RBC replication runner.

The original runs were executed inside the operating lab's internal
harness, which provided model access through internal modules. This
shim replaces that plumbing with the public APIs, using your own keys:

  GEMINI_API_KEY       Google AI Studio / Gemini API key
  OPENROUTER_API_KEY   OpenRouter API key (for the replication pairing)

Only the access layer differs from the original runs; every prompt,
packet, assignment, and scoring path in run_experiment.py is the code
that produced the published dataset. Model strings are the ones the
runner passes on its command line (defaults: gemini-3.8-flash for the
main phase, deepseek/deepseek-v4.1-flash via OpenRouter for the
replication), exactly as recorded in data/runs.jsonl.
"""
import json
import os
import urllib.request

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def _post(url, payload, headers, timeout=300):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def gemini_generate(model, system, user, max_tokens=1200):
    """Return (text, thought_text, total_tokens) for one Gemini call."""
    key = os.environ["GEMINI_API_KEY"]
    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.0},
    }
    d = _post(GEMINI_URL.format(model=model), payload, {"x-goog-api-key": key})
    text, thought = "", ""
    for cand in d.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            if part.get("thought"):
                thought += part.get("text", "")
            else:
                text += part.get("text", "")
    total = d.get("usageMetadata", {}).get("totalTokenCount", 0)
    return text, thought, int(total or 0)


def openrouter_chat(model, messages, temperature=0.0, max_tokens=1200):
    """Return (message_dict, usage_dict) for one OpenRouter chat call."""
    key = os.environ["OPENROUTER_API_KEY"]
    payload = {"model": model, "messages": messages,
               "temperature": temperature, "max_tokens": max_tokens}
    d = _post(OPENROUTER_URL, payload, {"Authorization": f"Bearer {key}"})
    msg = d.get("choices", [{}])[0].get("message", {})
    return msg, d.get("usage", {}) or {}


def openrouter_total_tokens(usage):
    return int((usage or {}).get("total_tokens", 0) or 0)

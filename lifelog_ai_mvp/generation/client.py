import json
import os


def api_key():
    return (
        os.getenv("LIFELOG_LLM_API_KEY", "").strip()
        or os.getenv("OPENAI_API_KEY", "").strip()
    )


def model_name():
    return (
        os.getenv("LIFELOG_LLM_MODEL", "").strip()
        or os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
    )


def get_client():
    key = api_key()
    if not key:
        return None
    from openai import OpenAI
    base_url = os.getenv("LIFELOG_LLM_BASE_URL", "").strip() or None
    return OpenAI(api_key=key, base_url=base_url)


def complete_json(system_prompt, user_prompt, temperature=0.4):
    client = get_client()
    if client is None:
        raise RuntimeError("OPENAI_API_KEY is not configured.")
    response = client.chat.completions.create(
        model=model_name(),
        temperature=temperature,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    content = response.choices[0].message.content or "{}"
    return json.loads(content)


def complete_text(user_prompt, temperature=0.4):
    client = get_client()
    if client is None:
        raise RuntimeError("OPENAI_API_KEY is not configured.")
    response = client.chat.completions.create(
        model=model_name(),
        temperature=temperature,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return (response.choices[0].message.content or "").strip()

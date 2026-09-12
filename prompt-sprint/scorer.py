import re

import litellm

SCORE_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")

JUDGE_PROMPT = """You are an expert evaluator. Given the PROMPT and RESPONSE below,
rate the response quality on a scale from 0.0 to 10.0.

Criteria:
- Accuracy / correctness
- Completeness
- Conciseness (penalise unnecessary padding)
- Code quality (if code is present)

Return ONLY a single number (e.g. 7.5). No explanation.

PROMPT: {prompt}

RESPONSE: {response}
"""


def extract_text(response):
    try:
        content = response.choices[0].message.content
    except (AttributeError, IndexError, TypeError):
        return ""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("text"):
                parts.append(str(item["text"]))
        return "".join(parts)
    return str(content)


def parse_score(text):
    if not text:
        return None
    match = SCORE_PATTERN.search(str(text))
    if not match:
        return None
    try:
        value = float(match.group(0))
    except ValueError:
        return None
    return max(0.0, min(10.0, value))


def judge_model_id(config):
    model = config.get("judge_model")
    if isinstance(model, str) and model.strip():
        return model.strip()
    return config["model"]


def score_response(prompt, response, config, call_kwargs):
    messages = [
        {
            "role": "user",
            "content": JUDGE_PROMPT.format(prompt=prompt, response=response),
        }
    ]
    kwargs = {
        "model": judge_model_id(config),
        "messages": messages,
        "temperature": 0,
        "timeout": config["timeout_seconds"],
        "stream": False,
        **call_kwargs,
        **config.get("extra_params", {}),
    }
    max_tokens = config.get("max_tokens")
    if max_tokens is not None:
        kwargs["max_tokens"] = min(int(max_tokens), 64)
    else:
        kwargs["max_tokens"] = 64
    try:
        completion = litellm.completion(**kwargs)
        return parse_score(extract_text(completion))
    except Exception:
        return None

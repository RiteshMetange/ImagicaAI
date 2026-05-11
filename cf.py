import json
import os
import re
from urllib import error, parse, request
from datetime import datetime
from pathlib import Path

BOT_MODEL = "imagica-hybrid"
PEXELS_API_URL = "https://api.pexels.com/v1/search"
OPENAI_CHAT_API_URL = "https://api.openai.com/v1/chat/completions"
GROQ_CHAT_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_GENERATE_API_URL = "https://generativelanguage.googleapis.com/v1beta/{model}:generateContent"
DEFAULT_OPENAI_CHAT_MODEL = "gpt-4o-mini"
DEFAULT_GROQ_CHAT_MODEL = "llama-3.1-8b-instant"
DEFAULT_GEMINI_CHAT_MODEL = "gemini-2.5-flash"
DEFAULT_IMAGE_COUNT = 6
ROOT = Path(__file__).parent
LLM_PROVIDER_OPENAI = "openai"
LLM_PROVIDER_GEMINI = "gemini"
DEFAULT_LLM_PROVIDER = LLM_PROVIDER_OPENAI

QUESTION_STARTERS = {
    "what",
    "what's",
    "why",
    "how",
    "who",
    "when",
    "where",
    "which",
    "can",
    "could",
    "should",
    "would",
    "will",
    "do",
    "does",
    "did",
    "is",
    "are",
    "am",
    "explain",
    "tell",
    "write",
    "draft",
    "make",
    "create",
    "convert",
    "calculate",
    "solve",
}

BARE_IMAGE_BLOCKERS = {
    "i",
    "me",
    "my",
    "you",
    "your",
    "we",
    "our",
    "is",
    "are",
    "am",
    "was",
    "were",
    "be",
    "being",
    "do",
    "does",
    "did",
    "can",
    "could",
    "should",
    "would",
    "will",
    "need",
    "want",
    "have",
    "has",
    "had",
    "help",
    "please",
}

CAPITALS = {
    "australia": "Canberra",
    "brazil": "Brasilia",
    "canada": "Ottawa",
    "china": "Beijing",
    "france": "Paris",
    "germany": "Berlin",
    "india": "New Delhi",
    "italy": "Rome",
    "japan": "Tokyo",
    "mexico": "Mexico City",
    "russia": "Moscow",
    "south africa": "Pretoria",
    "spain": "Madrid",
    "united kingdom": "London",
    "uk": "London",
    "england": "London",
    "united states": "Washington, DC",
    "united states of america": "Washington, DC",
    "usa": "Washington, DC",
    "us": "Washington, DC",
}

SIMPLE_DEFINITIONS = {
    "ai": "AI means artificial intelligence: software that can perform tasks that usually need human-like reasoning, language, vision, or pattern recognition.",
    "api": "An API is a way for one program to request data or actions from another program using a defined interface.",
    "chatbot": "A chatbot is software that replies to messages in a conversational way.",
    "css": "CSS is the language used to style web pages: colors, layout, spacing, fonts, and responsive behavior.",
    "html": "HTML is the markup language that gives a web page its structure and content.",
    "javascript": "JavaScript is a programming language commonly used to make websites interactive.",
    "pexels": "Pexels is a stock photo and video service. This bot uses its API to search image results.",
    "python": "Python is a programming language known for readable syntax and strong support for scripting, automation, data work, and web backends.",
}

UNIT_ALIASES = {
    "c": "c",
    "celsius": "c",
    "f": "f",
    "fahrenheit": "f",
    "kg": "kg",
    "kilogram": "kg",
    "kilograms": "kg",
    "g": "g",
    "gram": "g",
    "grams": "g",
    "lb": "lb",
    "lbs": "lb",
    "pound": "lb",
    "pounds": "lb",
    "km": "km",
    "kilometer": "km",
    "kilometers": "km",
    "mi": "mi",
    "mile": "mi",
    "miles": "mi",
    "m": "m",
    "meter": "m",
    "meters": "m",
    "cm": "cm",
    "centimeter": "cm",
    "centimeters": "cm",
    "in": "in",
    "inch": "in",
    "inches": "in",
    "ft": "ft",
    "foot": "ft",
    "feet": "ft",
    "l": "l",
    "liter": "l",
    "liters": "l",
    "litre": "l",
    "litres": "l",
    "gal": "gal",
    "gallon": "gal",
    "gallons": "gal",
}

UNIT_LABELS = {
    "c": "C",
    "f": "F",
    "kg": "kg",
    "g": "g",
    "lb": "lb",
    "km": "km",
    "mi": "mi",
    "m": "m",
    "cm": "cm",
    "in": "in",
    "ft": "ft",
    "l": "L",
    "gal": "gal",
}

CHAT_SYSTEM_PROMPT = (
    "You are Imagica, a friendly local chatbot inside a small web app. "
    "Help with everyday questions, greetings, light troubleshooting, simple writing, "
    "and small problem-solving tasks. Keep replies concise and practical. "
    "When the user asks for images or photos, let the app use Pexels instead of "
    "pretending to generate images."
)

PLACEHOLDER_SECRETS = {
    "your_gemini_api_key_here",
    "your_google_api_key_here",
    "your_openai_api_key_here",
    "your_openai_or_groq_api_key_here",
    "your_pexels_api_key_here",
}


class ChatbotConfigError(RuntimeError):
    pass


class PexelsAPIError(RuntimeError):
    pass


class LLMProviderError(RuntimeError):
    pass


def load_env_file(path=ROOT / ".env"):
    if not path.is_file():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


load_env_file()


def get_pexels_api_key():
    api_key = os.getenv("PEXELS_API_KEY", "").strip()
    if not is_configured_secret(api_key):
        raise ChatbotConfigError("PEXELS_API_KEY is not set.")

    return api_key


def is_configured_secret(value):
    cleaned = value.strip()
    return bool(cleaned) and cleaned.lower() not in PLACEHOLDER_SECRETS


def has_pexels_api_key():
    return is_configured_secret(os.getenv("PEXELS_API_KEY", ""))


def first_configured_env(*names):
    for name in names:
        value = os.getenv(name, "").strip()
        if is_configured_secret(value):
            return value
    return ""


def get_openai_api_key():
    return first_configured_env("OPENAI_API_KEY", "GROQ_API_KEY")


def has_openai_api_key():
    return bool(get_openai_api_key())


def get_gemini_api_key():
    return first_configured_env(
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "GOOGLE_AI_API_KEY",
        "GEMENI_API_KEY",
        "GEMENI_CHAT_MODEL",
    )


def has_gemini_api_key():
    return bool(get_gemini_api_key())


def is_groq_api_key(api_key):
    return api_key.startswith("gsk_")


def normalize_llm_provider(provider=None):
    provider_id = str(provider or "").strip().lower()
    if provider_id in {LLM_PROVIDER_OPENAI, LLM_PROVIDER_GEMINI}:
        return provider_id
    return DEFAULT_LLM_PROVIDER


def get_default_llm_provider():
    configured_provider = normalize_llm_provider(os.getenv("LLM_PROVIDER", DEFAULT_LLM_PROVIDER))
    if has_llm_provider_key(configured_provider):
        return configured_provider
    for provider_id in (LLM_PROVIDER_OPENAI, LLM_PROVIDER_GEMINI):
        if has_llm_provider_key(provider_id):
            return provider_id
    return configured_provider


def get_chat_provider(provider=None):
    return normalize_llm_provider(provider or get_default_llm_provider())


def get_openai_chat_api_url():
    configured_url = os.getenv("OPENAI_CHAT_API_URL", "").strip()
    if configured_url:
        return configured_url

    if is_groq_api_key(get_openai_api_key()):
        return GROQ_CHAT_API_URL

    return OPENAI_CHAT_API_URL


def get_openai_chat_model():
    configured_model = os.getenv("OPENAI_CHAT_MODEL", "").strip()
    if configured_model:
        return configured_model

    if is_groq_api_key(get_openai_api_key()):
        return DEFAULT_GROQ_CHAT_MODEL

    return DEFAULT_OPENAI_CHAT_MODEL


def get_gemini_chat_model():
    configured_model = (
        os.getenv("GEMINI_CHAT_MODEL", "").strip()
        or os.getenv("GOOGLE_CHAT_MODEL", "").strip()
    )
    return configured_model or DEFAULT_GEMINI_CHAT_MODEL


def get_chat_model(provider=None):
    provider_id = get_chat_provider(provider)
    if provider_id == LLM_PROVIDER_GEMINI:
        return get_gemini_chat_model()
    return get_openai_chat_model()


def has_llm_provider_key(provider):
    provider_id = normalize_llm_provider(provider)
    if provider_id == LLM_PROVIDER_GEMINI:
        return has_gemini_api_key()
    return has_openai_api_key()


def get_llm_provider_label(provider):
    provider_id = normalize_llm_provider(provider)
    if provider_id == LLM_PROVIDER_GEMINI:
        return "Gemini"
    return "OpenAI"


def get_llm_provider_statuses():
    return [
        {
            "id": LLM_PROVIDER_OPENAI,
            "label": "OpenAI",
            "configured": has_openai_api_key(),
            "model": get_openai_chat_model(),
        },
        {
            "id": LLM_PROVIDER_GEMINI,
            "label": "Gemini",
            "configured": has_gemini_api_key(),
            "model": get_gemini_chat_model(),
        },
    ]


def has_any_llm_provider():
    return any(provider["configured"] for provider in get_llm_provider_statuses())


def get_bot_mode():
    if has_any_llm_provider() and has_pexels_api_key():
        return "chat-and-pexels"
    if has_any_llm_provider():
        return "chat"
    if has_pexels_api_key():
        return "basic-chat-and-pexels"
    return "basic-chat"


def is_chat_ready():
    return True


def get_model(provider=None):
    provider_id = get_chat_provider(provider)
    if has_llm_provider_key(provider_id):
        return get_chat_model(provider_id)
    return BOT_MODEL


def extract_image_query(text):
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return ""

    patterns = [
        r"^(?:show|find|search|get|bring|give|display)\s+(?:me\s+)?(?:some\s+)?(?:images?|pictures?|photos?)\s+(?:of|for)\s+(.+)$",
        r"^(?:show|find|search|get|bring|give|display)\s+(?:me\s+)?(?:some\s+)?(?:images?|pictures?|photos?)\s+(.+)$",
        r"^(?:images?|pictures?|photos?)\s+(?:of|for)\s+(.+)$",
        r"^(?:pexels\s+)?(?:image|photo|picture)\s+search\s+(?:for\s+)?(.+)$",
        r"^(?:search|find)\s+pexels\s+(?:for\s+)?(.+)$",
        r"^(?:generate|make|create)\s+(?:an?\s+)?(?:images?|pictures?|photos?)\s+(?:of|for)\s+(.+)$",
    ]

    for pattern in patterns:
        match = re.search(pattern, cleaned, re.I)
        if match:
            return match.group(1).strip(" .?!")

    if is_likely_bare_image_query(cleaned):
        return cleaned.strip(" .?!")

    return ""


def is_likely_bare_image_query(text):
    """Keep short visual prompts like "mountains sunset" working for Pexels."""
    if text.endswith("?") or re.search(r"[=:+*/%]", text):
        return False

    lowered = text.lower().strip(" .!")
    words = re.findall(r"[a-zA-Z][a-zA-Z'-]*", lowered)
    if not words or len(words) > 5:
        return False

    if words[0] in QUESTION_STARTERS:
        return False

    if any(word in BARE_IMAGE_BLOCKERS for word in words):
        return False

    return bool(re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9\s,'-]{0,80}", text.strip()))


def search_pexels_images(query, per_page=DEFAULT_IMAGE_COUNT):
    api_key = get_pexels_api_key()
    params = parse.urlencode({"query": query, "per_page": per_page})
    api_request = request.Request(
        f"{PEXELS_API_URL}?{params}",
        headers={"Authorization": api_key, "User-Agent": "AI-BOT/1.0"},
    )

    try:
        with request.urlopen(api_request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        if exc.code in {401, 403}:
            raise PexelsAPIError("Pexels rejected the API key.") from exc
        if exc.code == 429:
            raise PexelsAPIError("Pexels rate limit reached. Try again later.") from exc
        raise PexelsAPIError(f"Pexels request failed with HTTP {exc.code}.") from exc
    except error.URLError as exc:
        raise PexelsAPIError(f"Could not reach Pexels: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise PexelsAPIError("Pexels returned an unreadable response.") from exc

    images = []
    for photo in payload.get("photos", []):
        src = photo.get("src", {})
        images.append(
            {
                "id": photo.get("id"),
                "alt": photo.get("alt") or query,
                "photographer": photo.get("photographer") or "Pexels photographer",
                "photographerUrl": photo.get("photographer_url") or "",
                "sourceUrl": photo.get("url") or "",
                "imageUrl": src.get("large") or src.get("medium") or src.get("original"),
                "thumbnailUrl": src.get("medium") or src.get("small") or src.get("large"),
                "width": photo.get("width"),
                "height": photo.get("height"),
            }
        )

    return [image for image in images if image["imageUrl"]]


def build_openai_messages(user_input, history=None):
    messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]

    for item in (history or [])[-12:]:
        if not isinstance(item, dict):
            continue

        role = item.get("role")
        content = str(item.get("content", "")).strip()
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content[:1600]})

    messages.append({"role": "user", "content": user_input})
    return messages


def parse_api_error(raw_body):
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        return raw_body.strip() or "Unknown API error."

    api_error = payload.get("error")
    if isinstance(api_error, dict):
        return str(api_error.get("message") or "Unknown API error.")

    return str(api_error or "Unknown API error.")


def coerce_text_content(content):
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
            elif item:
                parts.append(str(item))
        return "\n".join(parts).strip()

    return ""


def build_gemini_contents(user_input, history=None):
    contents = []

    for item in (history or [])[-12:]:
        if not isinstance(item, dict):
            continue

        role = item.get("role")
        content = str(item.get("content", "")).strip()
        if not content:
            continue

        if role == "user":
            gemini_role = "user"
        elif role == "assistant":
            gemini_role = "model"
        else:
            continue

        contents.append({"role": gemini_role, "parts": [{"text": content[:1600]}]})

    contents.append({"role": "user", "parts": [{"text": user_input}]})
    return contents


def parse_llm_response_body(response):
    return json.loads(response.read().decode("utf-8"))


def call_openai_chat(user_input, history=None):
    api_key = get_openai_api_key()
    if not api_key:
        raise LLMProviderError("OpenAI API key is missing.")

    payload = {
        "model": get_openai_chat_model(),
        "messages": build_openai_messages(user_input, history=history),
        "temperature": 0.7,
        "max_tokens": 500,
    }

    try:
        api_request = request.Request(
            get_openai_chat_api_url(),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "Imagica/1.0",
            },
            method="POST",
        )
        with request.urlopen(api_request, timeout=30) as response:
            response_payload = parse_llm_response_body(response)
    except error.HTTPError as exc:
        raw_body = exc.read().decode("utf-8", errors="replace")
        raise LLMProviderError(parse_api_error(raw_body)) from exc
    except error.URLError as exc:
        raise LLMProviderError(f"Could not reach OpenAI: {exc.reason}") from exc
    except ValueError as exc:
        raise LLMProviderError("The OpenAI chat API URL is invalid. Check OPENAI_CHAT_API_URL in .env.") from exc
    except json.JSONDecodeError as exc:
        raise LLMProviderError("OpenAI returned an unreadable response.") from exc

    choices = response_payload.get("choices", [])
    if not choices:
        raise LLMProviderError("OpenAI did not return a message.")

    message = choices[0].get("message", {})
    content = coerce_text_content(message.get("content", ""))
    if not content:
        raise LLMProviderError("OpenAI returned an empty message.")

    return content


def get_gemini_model_path():
    model = get_gemini_chat_model().strip().strip("/")
    if model.startswith(("models/", "tunedModels/")):
        return model
    return f"models/{model}"


def call_gemini_chat(user_input, history=None):
    api_key = get_gemini_api_key()
    if not api_key:
        raise LLMProviderError("Gemini API key is missing.")

    model_path = parse.quote(get_gemini_model_path(), safe="/")
    payload = {
        "systemInstruction": {"parts": [{"text": CHAT_SYSTEM_PROMPT}]},
        "contents": build_gemini_contents(user_input, history=history),
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 500,
        },
    }

    try:
        api_request = request.Request(
            GEMINI_GENERATE_API_URL.format(model=model_path),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
                "User-Agent": "Imagica/1.0",
            },
            method="POST",
        )
        with request.urlopen(api_request, timeout=30) as response:
            response_payload = parse_llm_response_body(response)
    except error.HTTPError as exc:
        raw_body = exc.read().decode("utf-8", errors="replace")
        raise LLMProviderError(parse_api_error(raw_body)) from exc
    except error.URLError as exc:
        raise LLMProviderError(f"Could not reach Gemini: {exc.reason}") from exc
    except ValueError as exc:
        raise LLMProviderError("The Gemini API URL is invalid.") from exc
    except json.JSONDecodeError as exc:
        raise LLMProviderError("Gemini returned an unreadable response.") from exc

    candidates = response_payload.get("candidates", [])
    if not candidates:
        raise LLMProviderError("Gemini did not return a message.")

    first_candidate = candidates[0]
    parts = first_candidate.get("content", {}).get("parts", [])
    content = coerce_text_content(parts)
    if not content:
        finish_reason = first_candidate.get("finishReason")
        detail = f" Finish reason: {finish_reason}." if finish_reason else ""
        raise LLMProviderError(f"Gemini returned an empty message.{detail}")

    return content


LLM_PROVIDER_HANDLERS = {
    LLM_PROVIDER_OPENAI: call_openai_chat,
    LLM_PROVIDER_GEMINI: call_gemini_chat,
}


def get_llm_provider_candidates(requested_provider):
    requested_provider = normalize_llm_provider(requested_provider)
    candidates = [requested_provider]
    candidates.extend(
        provider_id
        for provider_id in (LLM_PROVIDER_OPENAI, LLM_PROVIDER_GEMINI)
        if provider_id != requested_provider
    )
    return candidates


def get_llm_reply(user_input, history=None, provider=None):
    requested_provider = normalize_llm_provider(provider or get_default_llm_provider())
    errors = []

    for provider_id in get_llm_provider_candidates(requested_provider):
        provider_label = get_llm_provider_label(provider_id)
        if not has_llm_provider_key(provider_id):
            errors.append(f"{provider_label} API key is missing")
            continue

        try:
            reply = LLM_PROVIDER_HANDLERS[provider_id](user_input, history=history)
        except LLMProviderError as exc:
            errors.append(f"{provider_label}: {exc}")
            continue

        return {
            "reply": reply,
            "provider": provider_id,
            "providerLabel": provider_label,
            "model": get_chat_model(provider_id),
            "fallback": provider_id != requested_provider,
            "errors": errors,
        }

    raise LLMProviderError("; ".join(errors) or "No LLM provider is configured.")


def get_openai_reply(user_input, history=None):
    if not get_openai_api_key():
        return None
    return call_openai_chat(user_input, history=history)


def calculate_expression(text):
    expression = text.lower().strip()
    expression = re.sub(
        r"^(please\s+)?(calculate|calc|solve|what is|what's)\s+", "", expression
    )
    expression = expression.replace("x", "*")

    if not re.fullmatch(r"[0-9+\-*/().%\s]+", expression):
        return None
    if not re.search(r"\d\s*[+\-*/%]\s*\d", expression):
        return None

    try:
        result = eval(expression, {"__builtins__": {}}, {})
    except ZeroDivisionError:
        return "Division by zero is not allowed."
    except Exception:
        return None

    if isinstance(result, float) and result.is_integer():
        result = int(result)
    return f"The answer is {result}."


def format_number(value):
    formatted = f"{value:.4f}".rstrip("0").rstrip(".")
    return formatted or "0"


def convert_value(amount, from_unit, to_unit):
    if from_unit == to_unit:
        return amount

    conversion_pairs = {
        ("kg", "lb"): lambda value: value * 2.2046226218,
        ("lb", "kg"): lambda value: value / 2.2046226218,
        ("g", "kg"): lambda value: value / 1000,
        ("kg", "g"): lambda value: value * 1000,
        ("km", "mi"): lambda value: value * 0.6213711922,
        ("mi", "km"): lambda value: value / 0.6213711922,
        ("m", "ft"): lambda value: value * 3.280839895,
        ("ft", "m"): lambda value: value / 3.280839895,
        ("cm", "in"): lambda value: value / 2.54,
        ("in", "cm"): lambda value: value * 2.54,
        ("l", "gal"): lambda value: value * 0.2641720524,
        ("gal", "l"): lambda value: value / 0.2641720524,
        ("c", "f"): lambda value: (value * 9 / 5) + 32,
        ("f", "c"): lambda value: (value - 32) * 5 / 9,
    }

    converter = conversion_pairs.get((from_unit, to_unit))
    if not converter:
        return None

    return converter(amount)


def get_conversion_reply(text):
    unit_pattern = "|".join(sorted((re.escape(unit) for unit in UNIT_ALIASES), key=len, reverse=True))
    match = re.search(
        rf"\b(?:convert\s+)?(-?\d+(?:\.\d+)?)\s*({unit_pattern})\s+(?:to|in)\s+({unit_pattern})\b",
        text,
        re.I,
    )
    if not match:
        return None

    amount = float(match.group(1))
    from_unit = UNIT_ALIASES[match.group(2).lower()]
    to_unit = UNIT_ALIASES[match.group(3).lower()]
    result = convert_value(amount, from_unit, to_unit)
    if result is None:
        return "I can convert common temperature, weight, distance, length, and volume units."

    return (
        f"{format_number(amount)} {UNIT_LABELS[from_unit]} is "
        f"{format_number(result)} {UNIT_LABELS[to_unit]}."
    )


def get_capital_reply(text):
    match = re.search(r"\bcapital\s+of\s+(?:the\s+)?([a-zA-Z ]+)[?.!]*$", text, re.I)
    if not match:
        return None

    country = " ".join(match.group(1).lower().split())
    capital = CAPITALS.get(country)
    if capital:
        return f"The capital of {country.title()} is {capital}."

    return None


def get_definition_reply(text):
    match = re.search(
        r"^(?:what\s+is|what's|define|meaning\s+of)\s+(?:an?\s+)?([a-zA-Z+# ]+)[?.!]*$",
        text.strip(),
        re.I,
    )
    if not match:
        return None

    term = " ".join(match.group(1).lower().split())
    return SIMPLE_DEFINITIONS.get(term)


def get_list_or_plan_reply(text):
    plan_match = re.search(
        r"\b(?:make|create|give|write)\s+(?:me\s+)?(?:a\s+)?(?:quick\s+)?(?:plan|todo list|to-do list|checklist)\s+(for|to)\s+(.+)",
        text,
        re.I,
    )
    if plan_match:
        connector = plan_match.group(1).lower()
        topic = plan_match.group(2).strip(" .?!")
        return (
            f"Here is a simple plan {connector} {topic}:\n"
            "1. Define the exact goal and deadline.\n"
            "2. List the next three small actions.\n"
            "3. Do the fastest action first.\n"
            "4. Check what is blocked, missing, or confusing.\n"
            "5. Finish with one clear next step."
        )

    email_match = re.search(
        r"\b(?:write|draft)\s+(?:a\s+)?(?:short\s+)?(?:email|message)\s+(?:for|about|to)\s+(.+)",
        text,
        re.I,
    )
    if email_match:
        topic = email_match.group(1).strip(" .?!")
        return (
            f"Subject: {topic.title()}\n\n"
            "Hi,\n\n"
            f"I wanted to share a quick note about {topic}. Please let me know "
            "what details you would like me to add or adjust.\n\n"
            "Thanks"
        )

    return None


def get_troubleshooting_reply(text):
    lowered = text.lower()

    if (
        any(word in lowered for word in ["wifi", "wi-fi", "network"])
        or re.search(r"\binternet\s+(?:is\s+)?not\s+working\b", lowered)
    ):
        return (
            "Try this quick internet checklist:\n"
            "1. Turn Wi-Fi off and on again on the device.\n"
            "2. Restart the router if other devices are also affected.\n"
            "3. Forget and reconnect to the network.\n"
            "4. Check airplane mode, VPN, and proxy settings.\n"
            "5. If only one app fails, test another website or app first."
        )

    if re.search(r"\b(?:computer|laptop|pc|phone)\s+(?:is\s+)?slow\b", lowered):
        return (
            "For a slow device, start with the low-risk fixes:\n"
            "1. Restart it.\n"
            "2. Close heavy apps and browser tabs.\n"
            "3. Check free storage space.\n"
            "4. Install pending updates.\n"
            "5. Run a malware scan if the slowdown is sudden."
        )

    if any(word in lowered for word in ["battery draining", "battery drain", "battery issue"]):
        return (
            "For battery drain, check screen brightness, background apps, location services, "
            "battery health, and recent apps you installed. A restart is also worth trying first."
        )

    return None


def find_remembered_name(history):
    for item in reversed(history or []):
        if not isinstance(item, dict) or item.get("role") != "user":
            continue

        content = str(item.get("content", ""))
        match = re.search(r"\bmy name is\s+([a-zA-Z][a-zA-Z ]{0,40})", content, re.I)
        if match:
            return match.group(1).strip().title()

    return None


def get_local_reply(user_input, history=None):
    text = user_input.strip()
    lowered = text.lower()

    math_reply = calculate_expression(text)
    if math_reply:
        return math_reply

    conversion_reply = get_conversion_reply(text)
    if conversion_reply:
        return conversion_reply

    capital_reply = get_capital_reply(text)
    if capital_reply:
        return capital_reply

    definition_reply = get_definition_reply(text)
    if definition_reply:
        return definition_reply

    plan_reply = get_list_or_plan_reply(text)
    if plan_reply:
        return plan_reply

    troubleshooting_reply = get_troubleshooting_reply(text)
    if troubleshooting_reply:
        return troubleshooting_reply

    name_match = re.search(r"\bmy name is\s+([a-zA-Z][a-zA-Z ]{0,40})", text, re.I)
    if name_match:
        name = name_match.group(1).strip().title()
        return f"Nice to meet you, {name}. I will remember that in this chat."

    if "what is my name" in lowered or "who am i" in lowered:
        name = find_remembered_name(history)
        if name:
            return f"You told me your name is {name}."
        return "I do not know yet. Tell me with: my name is ..."

    if "who are you" in lowered or "what are you" in lowered:
        return "I am Imagica, your local chatbot for quick questions, small tasks, and Pexels image searches."

    words = set(re.findall(r"[a-z']+", lowered))
    if words & {"hi", "hello", "hey"}:
        return "Hello. Ask me a quick question, give me a small problem to solve, or ask for photos from Pexels."

    if "help" in lowered or "what can you do" in lowered:
        return (
            "I can chat normally, answer greetings, remember your name in this chat, "
            "handle simple math, convert common units, answer date/time questions, "
            "draft small notes, troubleshoot basic device issues, and search Pexels for images."
        )

    if "time" in lowered:
        return f"The current time is {datetime.now().strftime('%I:%M %p')}."

    if "date" in lowered or "day" in lowered:
        return f"Today is {datetime.now().strftime('%A, %B %d, %Y')}."

    if "thank" in lowered:
        return "You are welcome."

    if any(word in lowered for word in ["bye", "goodbye", "see you"]):
        return "Goodbye. I will be here when you run the app again."

    return None


def get_local_fallback_reply(user_input):
    text = user_input.strip()
    lowered = text.lower()

    if lowered.endswith("?"):
        return (
            "I can help with simpler questions locally. For this one, try asking in a more specific way, "
            "or add OPENAI_API_KEY or GEMINI_API_KEY to .env to enable fuller general chat replies."
        )

    if any(word in lowered for word in ["problem", "issue", "stuck", "not working", "error"]):
        return (
            "A good first step is to isolate the problem:\n"
            "1. Write down the exact thing that fails.\n"
            "2. Note what changed right before it started.\n"
            "3. Try the smallest repeatable test.\n"
            "4. Share the exact error or symptom with me, and I can help narrow it down."
        )

    return (
        "I can handle basic chat locally. Try greetings, simple math like '24 * 7', "
        "unit conversions like '10 km to miles', quick plans, date/time questions, "
        "or image requests like 'photos of mountains'. For broader open-ended answers, "
        "add OPENAI_API_KEY or GEMINI_API_KEY to .env."
    )


def get_general_chat_response(user_input, history=None, provider=None):
    requested_provider = get_chat_provider(provider)
    try:
        llm_result = get_llm_reply(user_input, history=history, provider=requested_provider)
    except LLMProviderError as exc:
        requested_label = get_llm_provider_label(requested_provider)
        return {
            "reply": (
                f"I could not use {requested_label}: {exc}\n\n"
                f"{get_local_fallback_reply(user_input)}"
            ),
            "images": [],
            "model": BOT_MODEL,
            "provider": requested_provider,
            "providerLabel": requested_label,
            "fallback": True,
            "llmError": str(exc),
        }

    if llm_result["fallback"]:
        requested_label = get_llm_provider_label(requested_provider)
        llm_result["reply"] = (
            f"{requested_label} was unavailable, so I used {llm_result['providerLabel']} instead.\n\n"
            f"{llm_result['reply']}"
        )

    return {
        "reply": llm_result["reply"],
        "images": [],
        "model": llm_result["model"],
        "provider": llm_result["provider"],
        "providerLabel": llm_result["providerLabel"],
        "fallback": llm_result["fallback"],
    }


def get_general_chat_reply(user_input, history=None, provider=None):
    return get_general_chat_response(user_input, history=history, provider=provider)["reply"]


def get_bot_response(user_input, history=None, provider=None):
    user_input = user_input.strip()
    if not user_input:
        raise ValueError("Message is empty.")

    provider_id = get_chat_provider(provider)
    provider_label = get_llm_provider_label(provider_id)

    local_reply = get_local_reply(user_input, history=history)
    if local_reply:
        return {
            "reply": local_reply,
            "images": [],
            "model": get_model(provider_id),
            "provider": provider_id,
            "providerLabel": provider_label,
            "fallback": False,
        }

    image_query = extract_image_query(user_input)
    if image_query:
        if not has_pexels_api_key():
            return {
                "reply": "PEXELS_API_KEY is not set on the server. Add your Pexels key to .env first.",
                "images": [],
                "model": get_model(provider_id),
                "provider": provider_id,
                "providerLabel": provider_label,
                "fallback": False,
            }

        images = search_pexels_images(image_query)
        if not images:
            return {
                "reply": f"I could not find Pexels images for \"{image_query}\".",
                "images": [],
                "model": get_model(provider_id),
                "provider": provider_id,
                "providerLabel": provider_label,
                "fallback": False,
            }

        return {
            "reply": f"Found {len(images)} Pexels image results for \"{image_query}\".",
            "images": images,
            "model": get_model(provider_id),
            "provider": provider_id,
            "providerLabel": provider_label,
            "fallback": False,
        }

    return get_general_chat_response(user_input, history=history, provider=provider_id)


def get_ai_reply(user_input, history=None, model=None):
    return get_bot_response(user_input, history=history, provider=model)["reply"]


def chat_with_ai():
    model = get_model()
    history = []

    print("AI: Hello! I am your chatbot. Type 'quit' or 'exit' to leave.")
    
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        
        if not user_input:
            continue

        if user_input.lower() in {"quit", "exit"}:
            break

        try:
            response = get_bot_response(user_input, history=history)
            reply = response["reply"]
        except ChatbotConfigError as exc:
            print(f"AI: {exc} Set it before running this chatbot.")
            break
        except PexelsAPIError as exc:
            print(f"AI: Sorry, I could not reach Pexels: {exc}")
            continue

        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": reply})
        print(f"AI: {reply}")

if __name__ == "__main__":
    chat_with_ai()

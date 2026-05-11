import json
import sys

from cf import (
    ChatbotConfigError,
    PexelsAPIError,
    get_bot_mode,
    get_bot_response,
    get_chat_provider,
    get_default_llm_provider,
    get_llm_provider_statuses,
    get_model,
    has_gemini_api_key,
    has_openai_api_key,
    has_pexels_api_key,
    is_chat_ready,
)


def status_payload():
    default_provider = get_default_llm_provider()
    return {
        "configured": is_chat_ready(),
        "mode": get_bot_mode(),
        "model": get_model(default_provider),
        "provider": get_chat_provider(default_provider),
        "defaultProvider": default_provider,
        "llmProviders": get_llm_provider_statuses(),
        "openaiConfigured": has_openai_api_key(),
        "geminiConfigured": has_gemini_api_key(),
        "pexelsConfigured": has_pexels_api_key(),
    }


def read_payload():
    raw_body = sys.stdin.read()
    if not raw_body.strip():
        return {}
    return json.loads(raw_body)


def write_response(body, status=200):
    print(json.dumps({"status": status, "body": body}))


def handle_status():
    write_response(status_payload())


def handle_chat():
    payload = read_payload()
    message = str(payload.get("message", "")).strip()
    history = payload.get("history", [])
    provider = str(payload.get("provider", "")).strip()
    response = get_bot_response(message, history=history, provider=provider)
    write_response(response)


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else ""

    try:
        if action == "status":
            handle_status()
        elif action == "chat":
            handle_chat()
        else:
            write_response({"error": "Unknown bridge action."}, status=404)
    except json.JSONDecodeError:
        write_response({"error": "Request body must be valid JSON."}, status=400)
    except ValueError as exc:
        write_response({"error": str(exc)}, status=400)
    except ChatbotConfigError as exc:
        write_response({"error": str(exc)}, status=503)
    except PexelsAPIError as exc:
        write_response({"error": f"Pexels request failed: {exc}"}, status=502)


if __name__ == "__main__":
    main()

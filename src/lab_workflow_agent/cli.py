import argparse
import json
import logging
import sys
from dataclasses import asdict

from .config import AppError, Settings, load_settings
from .provider import MoonshotProvider
from .service import chat, extract_intent


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="labops-agent")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Validate local configuration without network access")
    for name in ("models", "chat", "extract-intent", "smoke"):
        command = commands.add_parser(name)
        command.add_argument("--live", action="store_true", help="Explicitly authorize live provider requests")
        if name in ("chat", "extract-intent"):
            command.add_argument("prompt")
    return root


def emit(value: object, settings: Settings, *, error: bool = False) -> None:
    text = value if isinstance(value, str) else json.dumps(value, indent=2)
    # Also redact any accidental echo in provider content/metadata.
    print(text.replace(settings.api_key.get_secret_value(), "[REDACTED]"), file=sys.stderr if error else sys.stdout)


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    # SDK debug output can contain headers. Do not enable provider logging here.
    for name in ("openai", "httpx", "httpcore"):
        logger = logging.getLogger(name)
        logger.handlers = [logging.NullHandler()]
        logger.propagate = False
        logger.disabled = True
    provider = None
    try:
        if args.command != "doctor" and not args.live:
            raise AppError("Live provider access requires --live. No request was sent.")
        if hasattr(args, "prompt") and (not args.prompt.strip() or len(args.prompt) > 2000):
            raise AppError("Prompt must contain 1–2000 characters.")
        settings = load_settings()
        if args.command == "doctor":
            emit({"api_key": "present", "base_url": settings.base_url, "model": settings.model,
                  "max_completion_tokens": settings.max_completion_tokens, "thinking": settings.thinking,
                  "network": "not used"}, settings)
            return 0
        provider = MoonshotProvider(settings)
        if args.command == "models":
            emit({"models": provider.models()}, settings)
        elif args.command == "chat":
            emit(asdict(chat(provider, args.prompt)), settings)
        elif args.command == "extract-intent":
            intent, completion = extract_intent(provider, args.prompt)
            metadata = asdict(completion)
            metadata.pop("content")
            emit({"intent": intent.model_dump(), "metadata": metadata}, settings)
        else:
            # Exactly three HTTP requests on success; stop immediately on any failure.
            models = provider.models()
            emit({"check": "models", "models": models, "requests_completed": 1}, settings)
            if settings.model not in models:
                raise AppError("Configured model was not listed. Choose an available model before continuing.")
            emit({"check": "chat", "result": asdict(chat(provider, "Explain an API in one short sentence.")),
                  "requests_completed": 2}, settings)
            intent, completion = extract_intent(provider, "Find twenty passed QC control samples.")
            if intent.intent != "find_material" or intent.quantity != 20 or intent.qc_status != "passed" or not intent.material_query:
                raise AppError("Smoke response parsed but did not match the requested intent.")
            emit({"check": "extract-intent", "result": intent.model_dump(),
                  "model": completion.model, "finish_reason": completion.finish_reason,
                  "usage": completion.usage, "requests_completed": 3}, settings)
        return 0
    except AppError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        if provider is not None:
            provider.close()

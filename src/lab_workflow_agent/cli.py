import argparse
import json
import logging
import sys
from dataclasses import asdict

from .config import AppError, Settings, load_settings, load_source_settings
from .provider import MoonshotProvider
from .service import chat, extract_intent
from .source_client import LabStorageClient
from .coordinator import ask
from .draft import DraftSession, interact
from .submission import interact_order


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="labops-agent")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Validate local configuration without network access")
    for name in ("models", "chat", "extract-intent", "smoke"):
        command = commands.add_parser(name)
        command.add_argument("--live", action="store_true", help="Explicitly authorize live provider requests")
        if name in ("chat", "extract-intent"):
            command.add_argument("prompt")
    question = commands.add_parser("ask", help="Read-only local material/location question")
    question.add_argument("prompt")
    question.add_argument("--live", action="store_true", help="Authorize provider and local source reads")
    question.add_argument("--include-archived", action="store_true", help="Explicitly authorize archived reads")
    draft = commands.add_parser("draft", help="Build one in-memory draft; never create an order")
    draft.add_argument("prompt")
    draft.add_argument("--live", action="store_true", help="Authorize provider interpretation and local source reads")
    order = commands.add_parser("order", help="Preview and explicitly confirm one local order submission")
    order.add_argument("prompt")
    order.add_argument("--live", action="store_true", help="Authorize live draft reads; submission requires exact confirmation")
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
    source = None
    source_settings = None
    try:
        if args.command != "doctor" and not args.live:
            raise AppError("Live provider access requires --live. No request was sent.")
        if hasattr(args, "prompt") and (not args.prompt.strip() or len(args.prompt) > 2000):
            raise AppError("Prompt must contain 1–2000 characters.")
        settings = load_settings()
        if args.command == "doctor":
            doctor_source = load_source_settings()
            emit({"api_key": "present", "base_url": settings.base_url, "model": settings.model,
                  "max_completion_tokens": settings.max_completion_tokens, "thinking": settings.thinking,
                  "source": {"api_url": doctor_source.api_url,
                             "timeout_seconds": doctor_source.timeout_seconds,
                             "bearer_token": "present" if doctor_source.token_present else "missing"},
                  "network": "not used"}, settings)
            return 0
        if args.command in ("ask", "draft", "order"):
            source_settings = load_source_settings(require_token=True)
            source = LabStorageClient(source_settings)
        provider = MoonshotProvider(settings)
        if args.command in ("draft", "order"):
            secret = source_settings.bearer_token.get_secret_value()
            def draft_emit(value):
                emit(str(value).replace(secret, "[REDACTED]"), settings)
            session = DraftSession(provider, source, args.prompt)
            flow = interact_order if args.command == "order" else interact
            flow(session, args.prompt, draft_emit, input)
        elif args.command == "ask":
            result = ask(provider, source, args.prompt, allow_archived=args.include_archived)
            output = json.dumps(asdict(result), indent=2)
            output = output.replace(source_settings.bearer_token.get_secret_value(), "[REDACTED]")
            emit(output, settings)
        elif args.command == "models":
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
    except KeyboardInterrupt:
        print("Interrupted; clients closed.", file=sys.stderr)
        return 130
    except AppError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        try:
            if provider is not None:
                provider.close()
        finally:
            if source is not None:
                source.close()

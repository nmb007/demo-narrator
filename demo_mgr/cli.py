"""CLI entrypoint."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from demo_mgr.mux import mux_demo
from demo_mgr.rewrite import rewrite_demo
from demo_mgr.transcribe import transcribe_demo
from demo_mgr.tts import generate_voice


def _load_env() -> None:
    load_dotenv()
    load_dotenv(Path.cwd() / ".env")


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("demo_dir", help="Path to demo folder, e.g. demos/login-flow")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-run even when outputs already exist",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="demo-mgr",
        description="Transcribe, rewrite, voice, and mux screen recordings.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    transcribe_parser = subparsers.add_parser("transcribe", help="Extract audio and transcribe with Whisper")
    _add_common_args(transcribe_parser)
    transcribe_parser.add_argument(
        "--input",
        help="Explicit source video path (default: source.mov then source.mp4 in demo folder)",
    )
    transcribe_parser.add_argument(
        "--model",
        default=os.getenv("WHISPER_MODEL", "small"),
        help="faster-whisper model size (default: small)",
    )

    rewrite_parser = subparsers.add_parser("rewrite", help="Rewrite chunks with Groq")
    _add_common_args(rewrite_parser)

    voice_parser = subparsers.add_parser("voice", help="Generate Edge TTS clips and aligned narration")
    _add_common_args(voice_parser)
    voice_parser.add_argument(
        "--voice",
        default=os.getenv("DEFAULT_VOICE", "en-US-AndrewNeural"),
        help="Edge TTS voice name (default: en-US-AndrewNeural)",
    )
    voice_parser.add_argument(
        "--max-atempo",
        type=float,
        default=1.20,
        help="Maximum speech speed-up when TTS exceeds its window (default: 1.20)",
    )

    mux_parser = subparsers.add_parser("mux", help="Replace video audio with narration.wav")
    _add_common_args(mux_parser)

    run_parser = subparsers.add_parser("run", help="Run transcribe -> rewrite -> voice -> mux")
    _add_common_args(run_parser)
    run_parser.add_argument("--input", help="Explicit source video path")
    run_parser.add_argument(
        "--model",
        default=os.getenv("WHISPER_MODEL", "small"),
        help="faster-whisper model size (default: small)",
    )
    run_parser.add_argument(
        "--voice",
        default=os.getenv("DEFAULT_VOICE", "en-US-AndrewNeural"),
        help="Edge TTS voice name (default: en-US-AndrewNeural)",
    )
    run_parser.add_argument(
        "--max-atempo",
        type=float,
        default=1.20,
        help="Maximum speech speed-up when TTS exceeds its window (default: 1.20)",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    _load_env()
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "transcribe":
            transcribe_demo(
                args.demo_dir,
                model_name=args.model,
                input_path=args.input,
                force=args.force,
            )
        elif args.command == "rewrite":
            rewrite_demo(args.demo_dir, force=args.force)
        elif args.command == "voice":
            generate_voice(
                args.demo_dir,
                voice=args.voice,
                max_atempo=args.max_atempo,
                force=args.force,
            )
        elif args.command == "mux":
            mux_demo(args.demo_dir, force=args.force)
        elif args.command == "run":
            transcribe_demo(
                args.demo_dir,
                model_name=args.model,
                input_path=args.input,
                force=args.force,
            )
            rewrite_demo(args.demo_dir, force=args.force)
            generate_voice(
                args.demo_dir,
                voice=args.voice,
                max_atempo=args.max_atempo,
                force=args.force,
            )
            mux_demo(args.demo_dir, force=args.force)
        else:
            parser.error(f"Unknown command: {args.command}")
            return 2
    except Exception as exc:  # noqa: BLE001 - CLI should print a clean message
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0

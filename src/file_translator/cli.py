from __future__ import annotations

import argparse
from pathlib import Path

from .core import translate_file


def main() -> None:
    ap = argparse.ArgumentParser(description="Format-preserving file translator")
    ap.add_argument("input", help="input file path")
    ap.add_argument("output", help="output file path")
    ap.add_argument("--src", required=True, help="source language, e.g. zh-CN")
    ap.add_argument("--tgt", required=True, help="target language, e.g. en")
    ap.add_argument("--engine", default="mock", help="translation engine key: mock|xfyun|llm_kimi")
    ap.add_argument("--domain", default=None, help="terminology domain")
    ap.add_argument("--max-workers", type=int, default=4)

    args = ap.parse_args()
    in_path = Path(args.input)
    out_path = Path(args.output)

    translate_file(
        in_path=in_path,
        out_path=out_path,
        src=args.src,
        tgt=args.tgt,
        engine=args.engine,
        domain=args.domain,
        max_workers=max(1, args.max_workers),
    )
    print(f"OK: translated {in_path} -> {out_path}")


if __name__ == "__main__":
    main()

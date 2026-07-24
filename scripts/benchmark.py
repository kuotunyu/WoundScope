"""Benchmark fixed-spatial ONNX inference and emit machine-readable latency statistics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from woundscope.benchmarking import benchmark_onnx
from woundscope.config import load_config


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/base.yaml"))
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="cpu")
    parser.add_argument("--image-size", type=int, default=None)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--iterations", type=int, default=50)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    config = load_config(args.config)
    image_size = args.image_size or int(config["data"]["image_size"])
    result = benchmark_onnx(
        args.model,
        device=args.device,
        image_size=image_size,
        warmup=args.warmup,
        iterations=args.iterations,
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""CLI: python -m app.main --config config/base.toml  ->  outputs/<run_id>/"""

import argparse
import sys
import tomllib

from app.data import DataError, load_config
from app.model import InfeasibleError, SolverError
from app.pipeline import run
from app.report import summary_text


def apply_override(cfg: dict, item: str) -> None:
    """Apply 'section.key=value' (value parsed as TOML, falling back to a plain string)."""
    path, sep, raw = item.partition("=")
    if not sep or not path:
        raise DataError(f"--set expects section.key=value, got {item!r}")
    try:
        value = tomllib.loads(f"v = {raw}")["v"]
    except tomllib.TOMLDecodeError:
        value = raw
    *parents, leaf = path.split(".")
    node = cfg
    for k in parents:
        node = node.setdefault(k, {})
    node[leaf] = value


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Optimise the SAF supply chain in Kalimantan.")
    ap.add_argument("--config", default="config/base.toml")
    ap.add_argument("--run-id", default=None, help="output folder name (default: timestamp)")
    ap.add_argument("--quiet", action="store_true", help="hide the Gurobi log")
    ap.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="override a config value, e.g. --set model.time_limit_s=120 (repeatable)",
    )
    args = ap.parse_args(argv)
    try:
        cfg = load_config(args.config)
        for item in args.set:
            apply_override(cfg, item)
        res = run(cfg, run_id=args.run_id, verbose=not args.quiet)
    except (DataError, InfeasibleError, SolverError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(summary_text(res.out_dir / "costs.json"))
    print(f"outputs: {res.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

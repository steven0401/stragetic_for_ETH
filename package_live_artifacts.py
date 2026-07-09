from __future__ import annotations

import zipfile
from pathlib import Path

import config

OUTPUT = config.BASE_DIR / "live_artifacts.zip"
REQUIRED_FILES = [
    config.STORAGE_FEATURES / "ETHUSDT_1d_validation_report.json",
    *sorted(config.STORAGE_MODELS.glob("ETHUSDT_1d_target_atr_fold*.pkl")),
]


def main() -> None:
    missing = [path for path in REQUIRED_FILES if not path.exists()]
    if missing:
        missing_text = "\n".join(str(path) for path in missing)
        raise FileNotFoundError(f"Missing required live artifacts:\n{missing_text}")

    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in REQUIRED_FILES:
            zf.write(path, arcname=path.relative_to(config.BASE_DIR))

    print(f"Created {OUTPUT}")
    for path in REQUIRED_FILES:
        print(f"  - {path.relative_to(config.BASE_DIR)}")


if __name__ == "__main__":
    main()

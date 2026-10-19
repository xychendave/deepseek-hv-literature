"""Save an OpenAlex key using hidden input; never accept it in argv or print it."""
import getpass
import json
import os
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parent


def main():
    config_path = ROOT / "config.json"
    if not config_path.exists():
        raise SystemExit("Run ./hv-literature init first.")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    path = Path(config["credential_file"]).expanduser()
    key = getpass.getpass("OpenAlex API key (hidden): ").strip()
    if not key:
        raise SystemExit("Empty key; no changes made.")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix=".openalex-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump({"openalex_api_key":key}, stream)
            stream.write("\n")
        temporary.chmod(0o600)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Saved credential with permissions 0600: {path}")


if __name__ == "__main__":
    main()

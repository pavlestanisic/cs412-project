"""Allow python3 -m delivery."""

from delivery.core.entrypoint import main

if __name__ == "__main__":
    raise SystemExit(main())

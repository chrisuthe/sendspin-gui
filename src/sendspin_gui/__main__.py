"""Entry point for the Sendspin GUI application."""

from __future__ import annotations

import sys


def main() -> int:
    """Run the Sendspin GUI application."""
    try:
        from .app import SendspinGUIApp
    except ImportError as e:
        print(f"Error importing application: {e}")
        print("\nMake sure you have installed all dependencies:")
        print("  pip install -e .")
        print("\nOr install dependencies directly:")
        print("  pip install aiosendspin customtkinter pillow")
        return 1

    app = SendspinGUIApp()
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())

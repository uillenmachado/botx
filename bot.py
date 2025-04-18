"""Entry point kept for backward‑compatibility.
It simply imports and runs main.create_app()."""
from main import app  # noqa: F401

# When executed directly, run the Flask dev server (respecting ENVIRONMENT variable)
if __name__ == "__main__":
    import os
    debug_mode = os.getenv("ENVIRONMENT") == "development"
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=debug_mode)
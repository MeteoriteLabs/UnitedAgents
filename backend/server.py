"""United Agents — FastAPI application entry point.

This is the thin entry point for the Uvicorn server.
The full application is defined in src.main.
"""

from src.main import app  # noqa: F401

if __name__ == "__main__":
    import uvicorn
    import os
    from dotenv import load_dotenv
    load_dotenv()
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run("src.main:app", host="0.0.0.0", port=port, reload=True)

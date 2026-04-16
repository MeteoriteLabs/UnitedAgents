"""United Agents — Heartbeat engine module entrypoint.

Invoked by Procfile: `python -m heartbeat`
"""

import asyncio
import sys
import os
import logging

# Add parent to path so we can import src.*
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from heartbeat.engine import start_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

if __name__ == "__main__":
    try:
        asyncio.run(start_engine())
    except KeyboardInterrupt:
        logging.info("Heartbeat engine stopped by user")

import json
import os

from fastapi import Depends
from fastapi_limiter.depends import RateLimiter

# Read configuration from a file
with open("config.json") as config_file:
    config = json.load(config_file)

ORIGINS = config["origins"]
MAX_REQUESTS = [Depends(RateLimiter(times=config["max_requests"], seconds=1))] if os.getenv('DEV') else []
TEMP_DIR = config["temp_dir"]

os.makedirs(TEMP_DIR, exist_ok=True)

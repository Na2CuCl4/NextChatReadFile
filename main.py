import json
import os
import time
from contextlib import asynccontextmanager

import aiohttp
import redis.asyncio as redis
from azure.core.credentials import AzureKeyCredential
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from markitdown import MarkItDown
from openai import AzureOpenAI
from pydantic import BaseModel

from log import log

# Read configuration from a file
with open("config.json") as config_file:
    config = json.load(config_file)
ORIGINS = config["origins"]
MAX_REQUESTS = [Depends(RateLimiter(times=config["max_requests"], seconds=1))]


# FastAPI Limiter initialization
@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_connection = redis.from_url("redis://localhost", encoding="utf-8", decode_responses=True)
    await FastAPILimiter.init(redis_connection)
    yield
    await FastAPILimiter.close()


# FastAPI 实例
if os.getenv("DEV"):
    print("Running in development mode")
    app = FastAPI(lifespan=lifespan)
else:
    print("Running in production mode")
    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 数据模型
class FilePayload(BaseModel):
    http_url: str


# 创建 temp 文件夹
TEMP_DIR = "temp"
os.makedirs(TEMP_DIR, exist_ok=True)

# 初始化 MarkItDown 转换器
client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-10-01-preview"
)
md = MarkItDown(
    docintel_endpoint=os.getenv("AZURE_DOCINTEL_ENDPOINT"),
    docintel_credential=AzureKeyCredential(os.getenv("AZURE_DOCINTEL_API_KEY")),
    llm_client=client,
    llm_model="gpt-4o"
)


@app.get("/", dependencies=MAX_REQUESTS)
async def startup(request: Request):
    log(200, "Server is running", request.client.host)
    return {"message": "Server is running", "version": "1.0.0"}


@app.post("/read_file", dependencies=MAX_REQUESTS)
async def read_file(request: Request, payload: FilePayload):
    http_url = payload.http_url

    # 生成文件名（使用时间戳）
    timestamp = str(int(time.time()))
    file_path = os.path.join(TEMP_DIR, f"{timestamp}.docx")

    # 下载文件
    print(f"Downloading file from {http_url}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(http_url) as response:
                if response.status != 200:
                    log(404, f"File download from {http_url} failed with status {response.status}", request.client.host)
                    raise HTTPException(status_code=404, detail="File download failed.")
                with open(file_path, "wb") as f:
                    f.write(await response.read())
    except Exception as e:
        log(404, f"File downloaded from {http_url} failed: {e}", request.client.host)
        raise HTTPException(status_code=404, detail="File download failed.")
    print(f"File downloaded to {file_path}")

    # 转换文件为 Markdown
    print(f"Converting file {file_path} to Markdown")
    try:
        result = md.convert(file_path)
        text_content = result.text_content
    except Exception as e:
        # 删除临时文件
        os.remove(file_path)
        log(500, f"File converted from {http_url} failed: {e}", request.client.host)
        raise HTTPException(status_code=400, detail="File conversion failed.")
    print(f"File converted successfully to Markdown")

    # 删除临时文件
    print(f"Deleting temporary file {file_path}")
    os.remove(file_path)
    print(f"Temporary file {file_path} deleted")

    # 返回结果
    log(200, f"File converted from {http_url} successfully", request.client.host)
    return {"result": text_content}

import os
import time
from contextlib import asynccontextmanager

import aiohttp
import redis.asyncio as redis
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi_limiter import FastAPILimiter
from markitdown import MarkItDown

from config import TEMP_DIR, MAX_REQUESTS, ORIGINS
from log import log
from model import BaseResponse, FilePayload


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

# 初始化 MarkItDown 转换器
md = MarkItDown()


@app.post("/read_file", dependencies=MAX_REQUESTS)
async def read_file(request: Request, payload: FilePayload):
    # 检查 http_url 是否存在
    if not payload.http_url:
        log(400, "http_url is not provided", request.client.host)
        return BaseResponse(code=-1, msg="http_url is not provided.", status_code=400)
    http_url = payload.http_url

    # 生成文件名（使用时间戳）
    timestamp = str(time.time())
    file_path = os.path.join(TEMP_DIR, f"{timestamp}")

    # 下载文件
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(http_url) as response:
                if response.status != 200:
                    log(404, f"File download from {http_url} failed with status {response.status}", request.client.host)
                    return BaseResponse(code=1, msg="File download failed.", status_code=404)
                with open(file_path, "wb") as f:
                    f.write(await response.read())
    except Exception as e:
        log(404, f"File downloaded from {http_url} failed: {e}", request.client.host)
        return BaseResponse(code=1, msg="File download failed.", status_code=404)

    # 转换文件为 Markdown
    try:
        # 使用 MarkItDown 转换文件
        result = md.convert(file_path)
        text_content = result.text_content
    except Exception as e:
        # 删除临时文件
        os.remove(file_path)
        log(500, f"File converted from {http_url} failed: {e}", request.client.host)
        return BaseResponse(code=-4, msg="File conversion failed.", status_code=500)

    # 删除临时文件
    os.remove(file_path)

    # 返回结果
    log(200, f"File converted from {http_url} successfully", request.client.host)
    return BaseResponse(msg="File converted successfully", data=text_content)

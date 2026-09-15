import logging
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .auth.routes import router as auth_router
from .auth.wechat import login_mode_message
from .record.routes import router as record_router

logger = logging.getLogger(__name__)

def configure_app_logging() -> None:
    """让应用自己的日志在宿主下真的看得见。

    uvicorn / gunicorn 只给自己的 logger 配 handler：应用 logger 会掉进级别停在 WARNING、
    又没有 handler 的 root，于是启动日志里的登录模式静默消失（lastResort 只兜 WARNING+）。
    所以打开应用自己的包 logger（__package__ == "app"，是所有应用 logger 的共同祖先），
    并只在 root 没 handler 时补一个 —— 不动宿主的 root 级别。
    """
    logging.getLogger(__package__ or "app").setLevel(logging.INFO)
    if not logging.getLogger().handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s:     %(message)s"))
        logging.getLogger().addHandler(handler)

configure_app_logging()

@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info(login_mode_message())  # 启动日志：当前是真实微信还是开发降级
    yield

app = FastAPI(title="懂宝 API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

@app.middleware("http")
async def request_id(request: Request, call_next):
    request.state.request_id = request.headers.get("X-Request-ID", str(uuid4()))
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response

@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "request_error", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content={"error": detail, "request_id": request.state.request_id})

@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    fields = [{key: item[key] for key in ("type", "loc", "msg") if key in item} for item in exc.errors()]
    return JSONResponse(status_code=422, content={"error": {"code": "validation_error", "message": "请检查填写内容", "fields": fields}, "request_id": request.state.request_id})

app.include_router(record_router)
app.include_router(auth_router)

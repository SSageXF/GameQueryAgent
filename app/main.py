import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .agent import Agent
from .config import ROOT, Settings, load_settings
from .llm import AgentError
from .schemas import ChatRequest, ChatResponse


class BodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        chunks, size = [], 0
        while True:
            event = await receive()
            if event["type"] == "http.disconnect":
                return
            size += len(event.get("body", b""))
            if size > 262144:
                response = JSONResponse({"error": {"code": "body_too_large", "message": "这段对话超过了256KB，试着缩短一点，或清空对话后再聊吧。"}}, status_code=413)
                return await response(scope, receive, send)
            chunks.append(event)
            if not event.get("more_body", False):
                break
        async def replay():
            if chunks:
                return chunks.pop(0)
            return await receive()
        await self.app(scope, replay, send)


def create_app(settings: Settings | None = None, agent: Agent | None = None) -> FastAPI:
    settings = settings or load_settings()
    logger = logging.getLogger("gamequery")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    app = FastAPI(title="弈宝 · 王者万象棋问答", version="0.1.0")
    app.add_middleware(BodyLimit)
    app.state.agent = agent or Agent(settings)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse({"error": {"code": "invalid_input", "message": "这条消息没能提交成功。问题需要1—1000字，历史最多24条、合计24000字，只能包含玩家和向导的消息；调整后就可以继续聊。"}}, status_code=422)

    @app.exception_handler(AgentError)
    async def model_error(request: Request, exc: AgentError):
        logging.getLogger("gamequery").warning("agent_error code=%s", exc.code)
        return JSONResponse({"error": {"code": exc.code, "message": exc.message}}, status_code=exc.http_status)

    @app.middleware("http")
    async def headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'self'"
        return response

    @app.get("/api/health")
    async def health():
        records = app.state.agent.retriever.records
        return {"mode": settings.mode, "retrieval_backend": settings.retrieval_backend, "model_configured": settings.ready, "knowledge_count": len(records), "snapshot_date": max(r["collected_at"] for r in records), "request_timeout_seconds": settings.timeout+settings.planner_timeout, "query_planning": "combined_intent_and_search" if settings.mode=='live' else 'mock_rules'}

    @app.post("/api/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest):
        return await app.state.agent.chat(request)

    @app.get("/")
    async def index():
        return FileResponse(ROOT / "static/index.html")

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        return RedirectResponse(url="/static/favicon.svg")

    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
    return app


app = create_app()

import traceback

try:
    from app.main import app
except Exception as e:
    err_str = traceback.format_exc()
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    
    app = FastAPI()
    
    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
    async def catch_all(path: str):
        return HTMLResponse(content=f"<h1>Vercel Import Error</h1><pre>{err_str}</pre>", status_code=500)


"""Entry point for the cloud API server."""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "src.api.server:app",
        host="0.0.0.0",
        port=8080,
        reload=False,
        log_level="info",
    )

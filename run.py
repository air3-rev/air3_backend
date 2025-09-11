#!/usr/bin/env python3
"""
Simple Python API Runner
Run this script to start the API server
"""

import uvicorn
from app.config import settings

if __name__ == "__main__":
    assert settings.lens_url, "Missing LENS_URL from environment"  
    assert settings.lens_token, "Missing LENS_TOKEN from environment"
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info"
    )
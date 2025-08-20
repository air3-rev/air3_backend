#!/usr/bin/env python3
"""
Simple Python API Runner
Run this script to start the API server
"""

import uvicorn
from app.config import settings

if __name__ == "__main__":
    assert settings.LENS_URL, "Missing LENS_URL from environment"  
    assert settings.LENS_TOKEN, "Missing LENS_TOKEN from environment"
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info"
    )
from fastapi import APIRouter

from app.api.v1.endpoints import health_router, ocr_router
from app.api.v1.endpoints.cases import router as cases_router
# from app.api.v1.endpoints.excel_upload import router as excel_router  # Temporarily disabled
from app.api.v1.endpoints.navigation import router as navigation_router
from app.api.v1.endpoints.batch import router as batch_router

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(ocr_router, prefix="/ocr", tags=["ocr"])
api_router.include_router(cases_router, prefix="/cases", tags=["cases"])
# api_router.include_router(excel_router, prefix="/excel", tags=["excel"])  # Temporarily disabled
api_router.include_router(navigation_router, prefix="/navigation", tags=["navigation"])  # Word-to-document navigation
api_router.include_router(batch_router, prefix="/batch", tags=["batch"])  # PDF batch processing

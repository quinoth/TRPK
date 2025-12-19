from fastapi import APIRouter, Request, HTTPException
from httpx import AsyncClient
from app.config.services import SERVICES


router = APIRouter()

@router.api_route("/{service}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(service: str, path: str, request: Request):
    if service not in SERVICES:
        raise HTTPException(404, "Service not found")

    url = f"{SERVICES[service]}/{path}"
    headers = dict(request.headers)
    token = headers.get("authorization", "").replace("Bearer ", "")

    # Проверяем JWT только если нужно
    if service in ["chat", "workflow", "admin"] and not token:
        raise HTTPException(401, "Token required")

    async with AsyncClient() as client:
        response = await client.request(
            method=request.method,
            url=url,
            content=await request.body(),
            headers=headers,
            params=request.query_params
        )
        return response.json(), response.status_code

from fastapi import FastAPI
from app.routes import gateway, bff
import uvicorn
import os
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="API Gateway & BFF")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


print("\n Проверка модулей...")
print("bff module:", bff)
print("bff.router:", getattr(bff, "router", None))
print("bff attributes:", dir(bff))


if hasattr(bff, "router") and bff.router is not None:
    app.include_router(bff.router)
    print(" BFF роутер подключён")
else:
    print(" BFF роутер НЕ подключён: bff.router не найден")

if hasattr(gateway, "router") and gateway.router is not None:
    app.include_router(gateway.router)
    print(" Gateway роутер подключён")
else:
    print(" Gateway роутер не найден (игнорируется)")

@app.on_event("startup")
async def list_routes():
    print("\nЗарегистрированные маршруты:")
    for route in app.routes:
        methods = ', '.join(route.methods) if hasattr(route, 'methods') else 'N/A'
        print(f"  {methods} {route.path}")

@app.get("/")
def root():
    return {"message": "Gateway & BFF OK", "routes": [str(r.path) for r in app.routes]}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app.main:app", host="localhost", port=port, reload=True)
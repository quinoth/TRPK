from fastapi import FastAPI
from app.init_db import init_admin
from events.producer import close_kafka_producer
from routes.auth import router as auth_router
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI(title="Auth Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[ "http://localhost:3000",   
        "http://127.0.0.1:3000",
        "http://localhost:5173",   
        "http://127.0.0.1:5173",
        ],
    allow_credentials=True,
    allow_methods=["*"],  # разрешить все методы (GET, POST, OPTIONS и т.д.)
    allow_headers=["*"], 
    )# разрешить все заголовки 


app.include_router(auth_router, prefix="/auth", tags=["Authentication"])

@app.on_event("startup")
def on_startup():
    init_admin() 

@app.on_event("shutdown")
async def on_shutdown():
    await close_kafka_producer()
    
@app.get("/")
def root():
    return {
        "message": "Auth Service запущен",
        "docs": "/docs",
        "status": "ok"
    }
    
print(" Все модули импортированы")
import sys
print("\n Текущая директория:", sys.path[0])
print("\n sys.path:")
for i, p in enumerate(sys.path):
    print(f"  {i}: {p}")

try:
    import shared
    print(f"\n shared найден: {shared.__file__}")
except ImportError as e:
    print(f"\n Не удалось импортировать shared: {e}") 
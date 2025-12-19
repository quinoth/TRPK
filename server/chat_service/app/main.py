
from fastapi import FastAPI
from app.routes import chat, files
from app.utils.database import engine
from shared.database import Base
from shared.models.user import User
from app.models.chat import ChatGroup, GroupMember, Message  
from fastapi.middleware.cors import CORSMiddleware

# Создаём все таблицы
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Chat Service")



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
app.include_router(chat.router)
app.include_router(files.router)

@app.get("/")
def root():
    return {"message": "Chat Service"}
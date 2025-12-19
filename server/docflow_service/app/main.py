from fastapi import FastAPI
from app.routes.documents import router as docs_router
from app.utils.database import engine
from app.models.document import Base
from fastapi.middleware.cors import CORSMiddleware
Base.metadata.create_all(bind=engine)

app = FastAPI(title="DocuFlow AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3000", 
                   "http://127.0.0.1:3000",
                   "http://localhost:5173",   
                   "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(docs_router)

"""@app.on_event("shutdown")
async def shutdown_event():
    if producer:
        await producer.stop()"""
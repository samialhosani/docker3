import uuid
from pathlib import Path
import shutil
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import load_config, AppConfig
from providers import LLMProviderFactory
from student_profile import get_student_profile
from chat_manager import ChatDatabase
from rag_manager import RAGManager, MaterialFile
from agent import EducationAgent

system_config: AppConfig = None
llm = None
chat_db: ChatDatabase = None
rag_manager: RAGManager = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Modern FastAPI lifecycle manager"""
    global system_config, llm, chat_db, rag_manager
    print("🚀 Starting up AI Microservice...")
    
    system_config = load_config()
    llm = LLMProviderFactory.create_llm(system_config.active_llm_config)
    chat_db = ChatDatabase(system_config.mysql_db_url) 
    rag_manager = RAGManager(system_config.vector_db_path)
    
    print("✅ All AI services initialized successfully!")
    yield
    print("🛑 Shutting down AI Microservice...")

app = FastAPI(
    title="Educational AI Assistant API",
    description="Microservice dedicated strictly to LLM chat generation and RAG ingestion.",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    student_id: str
    message: str
    course_id: str = "GENERAL"

class ChatResponse(BaseModel):
    course_id: str
    reply: str

@app.get("/health", tags=["System"])
def health_check():
    """Check if the microservice is running."""
    return {"status": "ok", "mode": system_config.mode}

@app.post("/chat", response_model=ChatResponse, tags=["Agent"])
def chat_with_agent(req: ChatRequest):
    """
    Receives proxied chat messages from Laravel.
    Builds the student's context, fetches history, and runs the AI Agent.
    """
    profile = get_student_profile(req.student_id, laravel_db_url=system_config.mysql_db_url)
    if not profile:
        raise HTTPException(status_code=404, detail="Student not found in Laravel Database.")
    
    
    agent = EducationAgent(
        llm=llm,
        profile=profile,
        db=chat_db,
        rag_manager=rag_manager,
    )
    
    try:
        reply = agent.send_message(req.message, course_id=req.course_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent Error: {str(e)}")
        
    return ChatResponse(
        course_id=req.course_id,
        reply=reply
    )

@app.post("/materials/ingest", tags=["Materials"])
async def ingest_lecture_materials(
    course_id: str = Form(...), 
    lesson_id: str = Form(...),
    file: UploadFile = File(...)
):
    """
    Receives forwarded files from Laravel, saves them, and ingests them into the AI Vector DB.
    Standardized course_id to accept Laravel's stringified numeric IDs (e.g., '5').
    """
    # Create directory structure: materials/{course_id}/{lesson_id}/
    save_dir = Path(system_config.materials_dir) / course_id / lesson_id
    save_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = save_dir / file.filename
    
    # Save the uploaded file to disk
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Create MaterialFile object for RAG processing
    mat_file = MaterialFile(
        file_name=file.filename,
        file_path=str(file_path),
        extension=file_path.suffix.lower()
    )
    
    try:
        rag_manager.ingest_materials(course_id, [mat_file])
        return {
            "status": "success", 
            "message": f"Successfully ingested '{file.filename}' into Course {course_id} Lesson {lesson_id}."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
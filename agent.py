import uuid
from typing import List, Dict, Optional
from pydantic import BaseModel, Field

# LangChain Agent Components
from langchain_core.tools import StructuredTool
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage

# Local Modules
from student_profile import StudentProfile, get_student_profile
from rag_manager import RAGManager
from chat_manager import ChatDatabase
from providers import LLMProviderFactory
from config import load_config

# --- Tool Input Schemas ---
class SearchInput(BaseModel):
    query: str = Field(description="The specific academic question or topic to search for in the course materials.")
    course_id: str = Field(description="The numeric ID of the course (e.g., '5').")

class EducationAgent:
    """An autonomous Agent that uses tools to fetch RAG context and database records."""
    
    def __init__(self, llm, profile: StudentProfile, db: ChatDatabase, rag_manager: RAGManager):
        self.llm = llm
        self.profile = profile
        self.db = db
        self.rag_manager = rag_manager


        self.tools = [
            StructuredTool.from_function(
                func=self._search_course_materials,
                name="search_course_materials",
                description="Search the vector database for course materials, lecture notes, and syllabus info to answer academic questions.",
                args_schema=SearchInput
            ),
            StructuredTool.from_function(
                func=self._get_upcoming_deadlines,
                name="get_upcoming_deadlines",
                description="Fetch the student's upcoming exams and pending assignments.",
            ),
            StructuredTool.from_function(
                func=self._get_student_profile_info,
                name="get_student_profile_info",
                description="Get general profile information about the student like enrolled courses.",
            )
        ]

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", 
             "You are an AI teaching assistant for an educational platform.\n"
             "You are currently helping the student: {student_name}.\n\n"
             "Guidelines:\n"
             "1. ALWAYS use the 'search_course_materials' tool when the student asks about course content, concepts, or lectures. Pass the specific numeric course_id they are asking about.\n"
             "2. Use the 'get_upcoming_deadlines' tool when they ask about what's due, assignments, or exams.\n"
             "3. Use 'get_student_profile_info' for general questions about their academic status.\n"
             "4. Do not make up answers about deadlines or materials. If a tool returns no data, inform the student honestly.\n"
             "5. Keep responses encouraging, academic, and concise."
            ),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        self.agent = create_tool_calling_agent(self.llm, self.tools, self.prompt)
        self.agent_executor = AgentExecutor(agent=self.agent, tools=self.tools, verbose=True)
    
    def _search_course_materials(self, query: str, course_id: str) -> str:
        """Tool: Uses RAGManager to search for course concepts."""
        print(f"\n🔍 [Tool Execution] Searching RAG for: '{query}' in Course {course_id}...")
        try:
            retriever = self.rag_manager.get_retriever(course_id)
            docs = retriever.invoke(query)
            if not docs:
                return "No relevant course material found in the database."
            
            context = "\n\n".join([f"Source: {doc.metadata.get('source', 'Unknown')}\nExcerpt: {doc.page_content}" for doc in docs])
            return context
        except Exception as e:
            return f"Error searching materials: {str(e)}"

    def _get_upcoming_deadlines(self) -> str:
        """Tool: Retrieves Pending Assignments from StudentProfile."""
        print("\n📅 [Tool Execution] Fetching student deadlines...")
        lines = []
        if self.profile.pending_assignments:
            lines.append("Pending Assignments:")
            for pa in self.profile.pending_assignments:
                lines.append(f"- Course {pa.course_id} ({pa.course_name}): Assignment '{pa.title}' is pending.")
        else:
            lines.append("No pending assignments.")
            
        return "\n".join(lines)

    def _get_student_profile_info(self) -> str:
        """Tool: Retrieves basic academic profile details."""
        print("\n🎓 [Tool Execution] Fetching student profile info...")
        return self.profile.get_context_string()

    def send_message(self, user_input: str, course_id: str = "GENERAL") -> str:
        """Sends a message to the agent, handles DB history, and returns the response."""
        
        # Pull history from Laravel's MySQL
        raw_history = self.db.get_history(self.profile.student_id, limit=10)
        
        chat_history = []
        for msg in raw_history:
            if msg["role"] == "user":
                chat_history.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "ai":
                chat_history.append(AIMessage(content=msg["content"]))

        # Invoke Agent
        try:
            response = self.agent_executor.invoke({
                "input": user_input,
                "chat_history": chat_history,
                "student_name": self.profile.full_name
            })
            ai_reply = response["output"]
        except Exception as e:
            print(f"\n❌ Agent Execution Error: {e}")
            ai_reply = "I'm sorry, but I encountered an error while processing your request."

        return ai_reply

if __name__ == "__main__":
    print("1. Loading Config and LLM...")
    config = load_config()
    
    llm = LLMProviderFactory.create_llm(config.active_llm_config)

    print("2. Initializing Databases & Managers...")
    db = ChatDatabase(config.mysql_db_url)
    rag = RAGManager(config.vector_db_path)
    
    # Use a dummy email or ID here that matches a user in your Laravel database
    dummy_student_email = "student@example.com"
    print(f"3. Fetching Student Profile ({dummy_student_email})...")
    profile = get_student_profile(dummy_student_email, laravel_db_url=config.mysql_db_url)
    
    if not profile:
        print(f"❌ Student {dummy_student_email} not found in the Laravel database.")
        print("Please ensure your MySQL database is seeded and running.")
        exit()

    print("\n" + "="*50)
    print("🤖 Education Agent Initialized!")
    print(f"👤 Logged in as: {profile.full_name}")
    print("💡 Try asking:")
    print("   - 'Do I have any pending assignments?'")
    print("   - 'What courses am I enrolled in?'")
    print("Type 'quit' to exit.")
    print("="*50 + "\n")

    agent = EducationAgent(llm=llm, profile=profile, db=db, rag_manager=rag)

    while True:
        user_msg = input("\nYou: ")
        if user_msg.lower() in ["quit", "exit"]:
            print("Ending session.")
            break

        ai_response = agent.send_message(user_msg, course_id="GENERAL")
        
        print(f"\n🎓 AI Assistant: {ai_response}")
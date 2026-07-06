from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy import create_engine, text

# --- Models ---
class EnrolledCourse(BaseModel):
    course_id: str
    course_name: str
    status: str = "enrolled"

class PendingAssignment(BaseModel):
    assignment_id: str
    course_id: str 
    course_name: str
    title: str
    status: str = "pending"

class StudentProfile(BaseModel):
    student_id: str
    full_name: str
    email: str
    role: str
    enrolled_courses: List[EnrolledCourse] = []
    pending_assignments: List[PendingAssignment] = []

    def get_context_string(self) -> str:
        courses = ", ".join([c.course_name for c in self.enrolled_courses]) or "No active enrollments"
        return (
            f"Student Name: {self.full_name}\n"
            f"Role: {self.role.capitalize()}\n"
            f"Enrolled Courses: {courses}"
        )

# --- Laravel Database Adapter ---
def get_student_profile(identifier: str, laravel_db_url: str) -> Optional[StudentProfile]:
    """Fetches real-time student context directly from the Laravel Source of Truth."""
    
    engine = create_engine(laravel_db_url)
    
    with engine.connect() as conn:
        # 1. Fetch User from Laravel's `users` table
        user_query = text("SELECT id, name, email, role FROM users WHERE id = :id OR email = :id")
        user_row = conn.execute(user_query, {"id": identifier}).mappings().fetchone()
        
        if not user_row:
            return None
            
        user_id = user_row["id"]
        
        # 2. Fetch Enrollments from Laravel's `enrollments` + `courses` tables
        enrollment_query = text("""
            SELECT c.id as course_id, c.title as course_name 
            FROM enrollments e 
            JOIN courses c ON e.course_id = c.id 
            WHERE e.user_id = :user_id
        """)
        enrollment_rows = conn.execute(enrollment_query, {"user_id": user_id}).mappings().fetchall()
        
        enrolled_courses = [
            EnrolledCourse(course_id=str(r["course_id"]), course_name=r["course_name"])
            for r in enrollment_rows
        ]
        
        # 3. Fetch Pending Assignments
        # Gets assignments for the user's courses WHERE the user HAS NOT submitted it yet in `assignment_submissions`
        assignments_query = text("""
            SELECT a.id as assignment_id, a.title, c.id as course_id, c.title as course_name
            FROM assignments a
            JOIN courses c ON a.course_id = c.id
            JOIN enrollments e ON c.id = e.course_id
            WHERE e.user_id = :user_id
            AND NOT EXISTS (
                SELECT 1 FROM assignment_submissions sub 
                WHERE sub.assignment_id = a.id AND sub.user_id = :user_id
            )
        """)
        assignment_rows = conn.execute(assignments_query, {"user_id": user_id}).mappings().fetchall()
        
        pending_assignments = [
            PendingAssignment(
                assignment_id=str(r["assignment_id"]),
                course_id=str(r["course_id"]),
                course_name=r["course_name"],
                title=r["title"]
            )
            for r in assignment_rows
        ]

        return StudentProfile(
            student_id=str(user_id),
            full_name=user_row["name"],
            email=user_row["email"],
            role=user_row["role"],
            enrolled_courses=enrolled_courses,
            pending_assignments=pending_assignments
        )
<?php

namespace App\Http\Controllers\Api\Instructor;

use App\Http\Controllers\Controller;
use App\Models\AssignmentSubmission;
use App\Models\Enrollment;
use App\Models\Quiz;
use Illuminate\Http\Request;

use App\Models\Course;
use App\Models\Lesson;
use App\Models\Task;
use App\Models\Assignment;

class InstructorController extends Controller
{
    // عرض كورسات المدرس
    public function myCourses(Request $request)
    {
        $courses = Course::where('user_id', $request->user()->id)->get();

        return response()->json($courses);
    }

    // إضافة كورس
    public function addCourse(Request $request)
    {
        $request->validate([
            'title' => 'required|string',
            'description' => 'nullable|string',
            'thumbnail' => 'nullable|string',
            'price' => 'nullable|numeric|min:0'
        ]);

        $course = Course::create([
            'user_id' => $request->user()->id,
            'title' => $request->title,
            'description' => $request->description,
            'thumbnail' => $request->thumbnail,
            'price' => $request->price
        ]);

        return response()->json([
            'message' => 'Course created successfully',
            'course' => $course
        ]);
    }

    // تعديل كورس
    public function updateCourse(Request $request, $id)
    {
        $course = Course::where('user_id', $request->user()->id)
            ->findOrFail($id);

        $course->update(
            $request->only('title', 'description', 'thumbnail', 'price')
        );

        return response()->json([
            'message' => 'Course updated successfully',
            'course' => $course
        ]);
    }

    // حذف كورس
    public function deleteCourse(Request $request, $id)
    {
        $course = Course::where('user_id', $request->user()->id)
            ->findOrFail($id);

        $course->delete();

        return response()->json([
            'message' => 'Course deleted successfully'
        ]);
    }

    // إضافة درس
    public function addLesson(Request $request, $id)
    {
        $request->validate([
            'title' => 'required|string',
            'video_url' => 'nullable|string',
            'content' => 'nullable|string'
        ]);

        $lesson = Lesson::create([
            'course_id' => $id,
            'title' => $request->title,
            'video_url' => $request->video_url,
            'content' => $request->content
        ]);

        if ($request->hasFile('material_file')) {
            $file = $request->file('material_file');

            try {
                Http::attach(
                    'file', file_get_contents($file), $file->getClientOriginalName()
                )->post('http://127.0.0.1:8000/materials/ingest', [
                    'course_id' => (string) $id,
                    'lesson_id' => (string) $lesson->id
                ]);
            } catch (\Exception $e) {
                // Log failure but don't break the Laravel lesson creation
                Log::error('AI Material Ingestion failed: ' . $e->getMessage());
            }
        }

        return response()->json([
            'message' => 'Lesson added successfully',
            'lesson' => $lesson
        ]);
    }

    // إنشاء Task
    public function createTask(Request $request)
    {
        $request->validate([
            'course_id' => 'required|exists:courses,id',
            'title' => 'required|string',
            'description' => 'nullable|string',
            'due_date' => 'nullable|date'
        ]);

        $task = Task::create([
            'course_id' => $request->course_id,
            'title' => $request->title,
            'description' => $request->description,
            'due_date' => $request->due_date
        ]);

        return response()->json([
            'message' => 'Task created successfully',
            'task' => $task
        ]);
    }

    // إنشاء Assignment
    public function createAssignment(Request $request)
    {
        $request->validate([
            'id' => 'required|exists:id',
            'title' => 'required|string',
            'description' => 'nullable|string'
        ]);

        $assignment = Assignment::create([
            'id' => $request->id,
            'title' => $request->title,
            'description' => $request->description
        ]);

        return response()->json([
            'message' => 'Assignment created successfully',
            'assignment' => $assignment
        ]);
    }

    public function index()
    {
        $assignments = Assignment::with('course')
            ->latest()
            ->get();

        return response()->json($assignments);
    }

    public function show($id)
    {
        $assignment = Assignment::with([
            'course',
            'submissions'
        ])->findOrFail($id);

        return response()->json($assignment);
    }
    public function reports(Request $request)
    {
        $courses = Course::where(
            'user_id',
            $request->user()->id
        )->pluck('id');

        return response()->json([
            'courses' => $courses->count(),
            'assignments' => Assignment::whereIn('course_id', $courses)->count(),
            'quizzes' => Quiz::whereIn('course_id', $courses)->count(),
            'students' => Enrollment::whereIn('course_id', $courses)->count()
        ]);
    }

    public function students(Request $request)
    {
        // الكورسات الخاصة بالدكتور
        $courseIds = $request->user()
            ->courses()
            ->pluck('id');

        $students = Enrollment::with(['user', 'course'])
            ->whereIn('course_id', $courseIds)
            ->get()
            ->map(function ($enrollment) {

                $totalAssignments = Assignment::where(
                    'course_id',
                    $enrollment->course_id
                )->count();

                $submittedAssignments = AssignmentSubmission::where(
                    'user_id',
                    $enrollment->user_id
                )
                    ->whereIn(
                        'assignment_id',
                        Assignment::where('course_id', $enrollment->course_id)
                            ->pluck('id')
                    )
                    ->count();

                return [
                    'student_id' => $enrollment->user->id,
                    'name' => $enrollment->user->name,
                    'email' => $enrollment->user->email,
                    'course_name' => $enrollment->course->title,
                    'submitted_assignments' => $submittedAssignments,
                    'total_assignments' => $totalAssignments
                ];
            });

        return response()->json($students);
    }
}
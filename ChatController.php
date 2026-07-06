<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use Illuminate\Http\Request;
use App\Models\ChatMessage;

class ChatController extends Controller
{
    public function sendMessage(Request $request)
    {
        $request->validate([
            'message' => 'required|string',
            'course_id' => 'nullable|string' // Optional: if chat is scoped to a specific course
        ]);

        $user = $request->user();

        // 1. Save user message
        ChatMessage::create([
            'user_id' => $user->id,
            'sender' => 'user',
            'message' => $request->message
        ]);

        // 2. Call the Python AI Agent
        try {
            $response = Http::timeout(30)->post('http://127.0.0.1:8000/chat', [
                'student_id' => (string) $user->id, 
                'message' => $request->message,
                'course_id' => $request->course_id ?? 'GENERAL'
            ]);

            if ($response->successful()) {
                $botReply = $response->json('reply');
            } else {
                Log::error('Python AI Error: ' . $response->body());
                $botReply = "I'm sorry, I'm having trouble connecting to my knowledge base right now.";
            }
        } catch (\Exception $e) {
            Log::error('FastAPI Connection Error: ' . $e->getMessage());
            $botReply = "Error connecting to the AI assistant server.";
        }

        // 3. Save Bot Reply
        ChatMessage::create([
            'user_id' => $user->id,
            'sender' => 'bot',
            'message' => $botReply
        ]);

        return response()->json([
            'success' => true,
            'reply' => $botReply
        ]);
    }

    public function history(Request $request)
    {
        return response()->json(
            ChatMessage::where('user_id', $request->user()->id)
                ->orderBy('created_at')
                ->get()
        );
    }

    private function getSmartReply($message)
    {
        $message = strtolower($message);

        if (str_contains($message, 'hello')) {
            return 'Hello! How can I help you?';
        }

        if (str_contains($message, 'course')) {
            return 'You can view your courses from My Courses page.';
        }

        if (str_contains($message, 'assignment')) {
            return 'Please check the assignments section.';
        }

        return 'I understand your question. Please provide more details.';
    }
}
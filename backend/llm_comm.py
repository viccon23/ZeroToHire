from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sock import Sock
from datasets import load_dataset
from huggingface_hub import hf_hub_download
import torch
from llama_cpp import Llama
import json
import os
from datetime import datetime
import re
from dotenv import load_dotenv
from database import Database

# Load environment variables
load_dotenv()

class CodingTutor:
    def __init__(self, model_path, db: Database):
        """Initialize the coding tutor with database storage."""
        self.db = db
        
        # Load conversation history from database (LIMIT to recent messages only to prevent context overflow)
        self.conversation_history = self.db.get_conversation_history(limit=10)
        
        # Load current problem from database
        self.current_problem = self.db.get_current_problem()
        
        print(f"Loaded session with {len(self.conversation_history)} recent messages")
        
        # Load model configuration from environment
        n_ctx = int(os.getenv('MODEL_N_CTX', 4096))
        n_threads = int(os.getenv('MODEL_N_THREADS', 4))
        n_gpu_layers = int(os.getenv('MODEL_N_GPU_LAYERS', -1))
        n_batch = int(os.getenv('MODEL_N_BATCH', 512))
        
        # Load the model
        print("Loading model...")
        print("Checking CUDA availability...")
        print(f"PyTorch CUDA available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"GPU device: {torch.cuda.get_device_name(0)}")
        
        self.llm = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_threads=n_threads,
            n_gpu_layers=n_gpu_layers,  
            verbose=True,    
            n_batch=n_batch,     
            use_mmap=True,    
            use_mlock=False   
        )
        print("Model loaded successfully!")
    
    def _add_message_to_history(self, role: str, content: str):
        """Add message to history and save to database."""
        message = {
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat()
        }
        self.conversation_history.append(message)
        
        # Save to database
        problem_id = self.current_problem.get('id') if self.current_problem else None
        self.db.save_message(role, content, problem_id)
    
    def set_problem(self, problem_data):
        """Set a new coding problem"""
        self.current_problem = {
            'title': problem_data.get('title', 'Unknown'),
            'description': problem_data.get('description', ''),
            'difficulty': problem_data.get('difficulty', 'Unknown'),
            'problem_types': problem_data.get('problem_types', []),
            'id': problem_data.get('id')
        }
        
        # Save problem to database
        self.db.set_problem(
            self.current_problem['id'],
            self.current_problem['title'],
            self.current_problem['difficulty']
        )
        
        # Add system message about the new problem
        problem_title = self.current_problem['title']
        system_msg = f"New coding problem started: {problem_title}"
        self._add_message_to_history('system', system_msg)
        
        # Check if this is the first problem or a new problem in an existing session
        has_previous_conversation = len([msg for msg in self.conversation_history if msg['role'] in ['user', 'assistant', 'alex']]) > 0
        
        if has_previous_conversation:
            # Continuing session with new problem
            response = f"Great! Let's work on '{problem_title}'. I can see you have the problem description. Before we dive into coding, let's make sure we understand what we're being asked to do. Can you tell me in your own words what this problem is asking for? Let me know if you have any questions!"
        else:
            # First problem in session
            response = f"Hello! I'm Alex, your coding assistant. I see you're working on '{problem_title}'. Before we start coding, let's make sure we understand the problem. Can you read through the problem description and tell me what you think it's asking us to do? Let me know if you have any questions!"
        
        # Add the response directly to history
        self._add_message_to_history('alex', response)
        
        return response
    
    def mark_problem_completed(self, problem_id):
        """Mark a problem as completed in database."""
        self.db.mark_problem_complete(problem_id)
        return True

    def mark_problem_uncompleted(self, problem_id):
        """Mark a problem as incomplete in database."""
        self.db.mark_problem_incomplete(problem_id)
        return True
    
    def is_problem_completed(self, problem_id):
        """Check if problem is completed."""
        return self.db.is_problem_completed(problem_id)
    
    def chat(self, user_message, is_initial=False, code_context=None):
        """Continue the conversation with Alex
        
        Args:
            user_message: The user's message
            is_initial: Whether this is an initial message
            code_context: Optional code context to include automatically
        """
        self._add_message_to_history('user', user_message)
        
        # Build the full conversation context
        conversation_context = self._build_conversation_context(
            user_message if is_initial else None,
            code_context=code_context
        )
        
        # Get model parameters from environment
        max_tokens = int(os.getenv('MODEL_MAX_TOKENS', 400))
        temperature = float(os.getenv('MODEL_TEMPERATURE', 0.7))
        top_p = float(os.getenv('MODEL_TOP_P', 0.9))
        
        # Generate response with error handling
        try:
            print(f"Generating response (context: ~{len(conversation_context)//4} tokens)...")
            response = self.llm(
                conversation_context,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                echo=False,
                stop=["Student:", "User:", "Alex:", "\n\nAlex:", "\nAlex:"]
            )
            print("Response generated successfully!")
        except Exception as e:
            print(f"ERROR during model generation: {str(e)}")
            print(f"Context length was: {len(conversation_context)} chars (~{len(conversation_context)//4} tokens)")
            print("Context may be too large or model encountered an error.")
            # Return a safe fallback response
            fallback = "I apologize, but I encountered a technical issue. Could you try rephrasing your question? If this persists, try using 'Clear Chat' to start fresh."
            self._add_message_to_history('alex', fallback)
            return fallback
        
        # Extract response text and clean it up
        raw_response = response['choices'][0]['text'].strip()
        
        # Remove any leaked internal reasoning tags
        if '</thought>' in raw_response:
            raw_response = raw_response.split('</thought>', 1)[1].strip()
        raw_response = re.sub(r'</?thought>', '', raw_response)
        raw_response = re.sub(r'</?response>', '', raw_response)
        
        # Aggressively stop at any role markers that leaked through
        role_markers = ['Alex:', 'Student:', 'User:']
        for marker in role_markers:
            if marker in raw_response:
                raw_response = raw_response.split(marker)[0].strip()
                break

        response = self._clean_response(raw_response)
        
        # Add response to history
        self._add_message_to_history('alex', response)
        
        return response
    
    def chat_stream(self, user_message, is_initial=False, code_context=None):
        """Stream the assistant's response token-by-token."""
        self._add_message_to_history('user', user_message)
        
        conversation_context = self._build_conversation_context(
            user_message if is_initial else None,
            code_context=code_context
        )
        
        max_tokens = int(os.getenv('MODEL_MAX_TOKENS', 400))
        temperature = float(os.getenv('MODEL_TEMPERATURE', 0.7))
        top_p = float(os.getenv('MODEL_TOP_P', 0.9))
        
        accumulated_chunks = []
        try:
            print(f"Streaming response (context: ~{len(conversation_context)//4} tokens)...")
            stream = self.llm(
                conversation_context,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                echo=False,
                stop=["Student:", "User:", "Alex:", "\n\nAlex:", "\nAlex:"],
                stream=True
            )
            for chunk in stream:
                token = chunk['choices'][0].get('text', '')
                if not token:
                    continue
                accumulated_chunks.append(token)
                yield {'type': 'token', 'token': token}
        except Exception as e:
            print(f"ERROR during streaming generation: {str(e)}")
            print(f"Context length was: {len(conversation_context)} chars (~{len(conversation_context)//4} tokens)")
            fallback = "I apologize, but I encountered a technical issue. Could you try rephrasing your question? If this persists, try using 'Clear Chat' to start fresh."
            self._add_message_to_history('alex', fallback)
            yield {'type': 'error', 'error': fallback}
            return
        
        raw_response = ''.join(accumulated_chunks).strip()
        if '</thought>' in raw_response:
            raw_response = raw_response.split('</thought>', 1)[1].strip()
        raw_response = re.sub(r'</?thought>', '', raw_response)
        raw_response = re.sub(r'</?response>', '', raw_response)
        
        role_markers = ['Alex:', 'Student:', 'User:']
        for marker in role_markers:
            if marker in raw_response:
                raw_response = raw_response.split(marker)[0].strip()
                break
        
        response = self._clean_response(raw_response)
        self._add_message_to_history('alex', response)
        
        yield {'type': 'final', 'message': response}
    
    def _clean_response(self, response):
        """Clean up the response while preserving code blocks and line breaks.

        Important: Do NOT strip parentheses or collapse whitespace globally,
        as that destroys code formatting. Only clean non-code text segments.
        """
        # Split out fenced code blocks so we don't touch them
        code_pattern = re.compile(r"```[\s\S]*?```", re.MULTILINE)
        code_blocks = code_pattern.findall(response)
        parts = code_pattern.split(response)

        cleaned_parts = []
        for part in parts:
            text = part
            # Remove light-weight stage directions in asterisks or brackets (non-greedy, single-line)
            text = re.sub(r"\*[^^\n*]{0,80}\*", "", text)
            text = re.sub(r"\[[^\]\n]{0,80}\]", "", text)
            # Remove common meta phrases
            text = re.sub(r"\b(let me think|thinking|pondering|considering)\b", "", text, flags=re.IGNORECASE)
            # Remove duplicated role prefixes at start of lines
            text = re.sub(r"(^|\n)\s*Alex:\s*", r"\1", text)
            # Normalize excessive blank lines but keep line structure
            text = re.sub(r"\n{3,}", "\n\n", text)
            # Trim trailing spaces per line
            lines = [ln.rstrip() for ln in text.splitlines()]
            text = "\n".join(lines)
            cleaned_parts.append(text)

        # Reassemble, interleaving preserved code blocks
        rebuilt = []
        for i, part in enumerate(cleaned_parts):
            rebuilt.append(part)
            if i < len(code_blocks):
                rebuilt.append(code_blocks[i])

        cleaned = "".join(rebuilt).strip()
        # Final minor cleanup: remove a trailing colon at end of entire message only
        cleaned = re.sub(r":\s*$", "", cleaned)
        return cleaned
    
    
    def _build_conversation_context(self, initial_prompt=None, code_context=None):
        """Build the full conversation context for the model
        
        Args:
            initial_prompt: Optional initial prompt to use
            code_context: Optional code context to include
        """
        if initial_prompt:
            return initial_prompt
        
        '''
        Here's where we'll let the llm know of what it should and shouldn't do. Finetuning would be good for getting it to sound more human, 
        but I'm too lazy to create a dataset of conversations for that.
        '''
        context_parts = []
        
        # Core Role and Instructions
        context_parts.append("You are Alex, an expert coding tutor specializing in LeetCode problems.")
        context_parts.append("The user is the student.")
        context_parts.append("Your goal is to guide the user to a solution, providing hints and asking questions to foster discovery, but provide the solution with explanation and Python code if they explicitly give up or request it.")
        
        # LeetCode-Specific Guidance
        context_parts.append("For LeetCode problems, summarize key constraints (e.g., input size, edge cases) and guide the student to consider time and space complexity.")
        context_parts.append("Encourage exploration of algorithmic patterns (e.g., two-pointer, dynamic programming, greedy) when relevant.")
        context_parts.append("If the student submits code, analyze it for correctness, efficiency, and edge cases. Provide specific feedback and suggest improvements without rewriting unless requested.")
        
        # Communication Style
        context_parts.append("COMMUNICATION STYLE:")
        context_parts.append("- Be direct, honest, and natural. If you don't understand something, ask for clarification.")
        context_parts.append("- Maintain an encouraging tone, especially when the student is frustrated, and celebrate small wins.")
        context_parts.append("- Keep responses concise and focused. Ask ONE clear question at a time, NOT multiple questions.")
        context_parts.append("- Avoid repeating the same question or concept multiple times in one response.")
        
        # Tutoring Approach
        context_parts.append("TUTORING APPROACH:")
        context_parts.append("- Ask questions to guide student discovery.")
        context_parts.append("- Let students work through problems themselves, providing hints only when stuck.")
        context_parts.append("- If the student says they cannot complete the problem or gives up, switch to concrete examples or simpler analogies.")
        context_parts.append("- Stay focused on the current problem. If the student asks about off-topic subjects, briefly acknowledge but guide them back to the current problem.")
        context_parts.append("- If the student wants to work on a different problem, suggest they use the 'Browse Problems' button to find and select it.")
        
        # Staying On Topic
        context_parts.append("STAYING FOCUSED:")
        context_parts.append("- Your primary role is to help with the current LeetCode problem.")
        context_parts.append("- For brief off-topic questions (like simple coding concepts), give a concise answer then redirect to the current problem.")
        context_parts.append("- If asked about other problems, say something like 'You can use the Browse Problems button to search for that specific problem if you'd like to work on it instead.'")
        context_parts.append("- Keep the conversation centered on solving the problem at hand.")
        
        # Platform Integration
        context_parts.append("PLATFORM FEATURES:")
        context_parts.append("- Format code in clear Python code blocks for display in the website's code editor.")
        context_parts.append("- Suggest test cases the student can run to verify their solution.")
        context_parts.append("- The student can use 'Browse Problems' button to search for and select different problems.")
        context_parts.append("- When relevant, suggest external resources (e.g., LeetCode problem URL, Python documentation).")
        
        # Never Do
        context_parts.append("NEVER DO:")
        context_parts.append("- Overuse conceptual questions when the student needs concrete examples.")
        context_parts.append("- Refuse to help when the student explicitly gives up.")
        context_parts.append("- Get sidetracked into long discussions unrelated to the current problem.")
        context_parts.append("- Try to solve different problems that the student mentions - direct them to use the problem browser instead.")
        
        # Add code context if provided
        if code_context and code_context.get('code', '').strip():
            context_parts.append("")
            context_parts.append("STUDENT'S CURRENT CODE:")
            context_parts.append("```python")
            context_parts.append(code_context['code'])
            context_parts.append("```")
            context_parts.append("Note: The student has this code in their editor. Consider it when providing guidance.")
            context_parts.append("")
        
        # Problem and User Context
        if self.current_problem:
            context_parts.append(f"CURRENT PROBLEM: {self.current_problem['title']}")
            context_parts.append(f"Difficulty: {self.current_problem.get('difficulty', 'Not specified')}")
            context_parts.append("Focus all tutoring efforts on helping the student solve THIS specific problem.")
            context_parts.append("")
        else:
            context_parts.append("No problem is currently loaded. Encourage the student to use the 'Browse Problems' button to select a problem to work on.")
            context_parts.append("")

        # CRITICAL: Limit conversation history to prevent context overflow
        # Estimate: System prompt ~1000 tokens, each message ~100-200 tokens
        # With 4096 context and 400 max_tokens output, we need ~3600 tokens max for input
        # Keep only last 5 messages (10 turns) to be safe - roughly 1000-2000 tokens
        history_limit = 5
        recent_history = self.conversation_history[-history_limit:] if len(self.conversation_history) > history_limit else self.conversation_history

        for msg in recent_history:
            if msg['role'] == 'user':
                context_parts.append(f"Student: {msg['content']}")
            elif msg['role'] == 'alex':
                context_parts.append(f"Alex: {msg['content']}")
        context_parts.append("")
        context_parts.append("Alex:")
        
        context = "\n".join(context_parts)
        
        # Safety check: Rough token estimate (4 chars ≈ 1 token)
        estimated_tokens = len(context) // 4
        max_input_tokens = 3500  # Leave room for output (4096 - 400 - buffer)
        
        if estimated_tokens > max_input_tokens:
            print(f"WARNING: Context too large (~{estimated_tokens} tokens). Reducing history...")
            # Reduce to last 3 messages only
            history_limit = 3
            context_parts = context_parts[:context_parts.index("")+1]  # Keep system prompt
            recent_history = self.conversation_history[-history_limit:]
            for msg in recent_history:
                if msg['role'] == 'user':
                    context_parts.append(f"Student: {msg['content']}")
                elif msg['role'] == 'alex':
                    context_parts.append(f"Alex: {msg['content']}")
            context_parts.append("")
            context_parts.append("Alex:")
            context = "\n".join(context_parts)
        
        return context
    
    def clear_chat(self):
        """Clear the current conversation history"""
        self.conversation_history = []
        problem_id = self.current_problem.get('id') if self.current_problem else None
        self.db.clear_conversation_history(problem_id)
        print("Chat cleared!")

    def evaluate_code(self, code, language="python"):
        """Evaluate user's code attempt"""
        if not self.current_problem:
            return "No problem is currently loaded."
        
        eval_prompt = f"""The student submitted the following {language} code for the problem "{self.current_problem['title']}":
            ```{language}
            {code}
            ```

            As Alex, their coding assistant, analyze this code for correctness and relevance to the problem.
            - If the code is just a default template or boilerplate (e.g., `def solution(): pass`), gently encourage the user to start writing their actual solution.
            - If the code is valid but doesn't logically contribute to solving the problem (e.g., printing a random string, performing unrelated calculations), gently point this out and guide the user back to the problem's requirements.
            - If the code is incorrect or doesn't solve the problem, guide them toward a better solution.
            - If the code is a good start, encourage them and ask what the next step is.
            - Use the Socratic method to guide, don't just give the answer.
            - Be encouraging and focus on helping them learn."""
        
        # Use internal chat method that doesn't show the prompt to user
        return self._chat_internal(eval_prompt)
    
    def _chat_internal(self, prompt):
        """Internal chat method that doesn't add the prompt to conversation history"""
        # Build the full conversation context
        conversation_context = self._build_conversation_context()
        
        # Add the evaluation prompt to the context
        full_context = conversation_context + "\n\n" + prompt + "\n\nAlex:"
        
        # Generate response with error handling
        try:
            response = self.llm(
                full_context,
                max_tokens=800,
                temperature=0.7,
                top_p=0.9,
                echo=False,
                stop=["Student:", "User:", "Alex:", "\n\nAlex:"]
            )
        except Exception as e:
            print(f"ERROR during code evaluation: {str(e)}")
            fallback = "I encountered a technical issue while evaluating your code. Could you try submitting it again? If this persists, try 'Clear Chat'."
            self._add_message_to_history('alex', fallback)
            return fallback
        
        # Extract and clean response
        raw_response = response['choices'][0]['text'].strip()
        
        # Remove any leaked internal reasoning tags
        if '</thought>' in raw_response:
            raw_response = raw_response.split('</thought>', 1)[1].strip()
        raw_response = re.sub(r'</?thought>', '', raw_response)
        raw_response = re.sub(r'</?response>', '', raw_response)
        
        # Remove any duplicate "Alex:" prefixes
        raw_response = re.sub(r'^Alex:\s*', '', raw_response)
        
        # Split by "Alex:" and take only the first response
        if 'Alex:' in raw_response:
            raw_response = raw_response.split('Alex:')[0].strip()

        response = self._clean_response(raw_response)
        
        # Add only the response to history
        self._add_message_to_history('alex', response)
        
        return response
    
    def extract_function_signature(self, python_solution):
        """Extract function signature from the complete solution"""
        try:
            lines = python_solution.strip().split('\n')
            
            for line in lines:
                line = line.strip()
                # Look for function definition
                if line.startswith('def ') and ':' in line:
                    # Extract the function signature
                    if line.endswith(':'):
                        return line + '\n    pass'
                    else:
                        # Handle multi-line function definitions
                        func_def = line
                        # You might need to handle cases where the signature spans multiple lines
                        return func_def + ':\n    pass'
                        
                # Also look for class-based solutions
                elif line.startswith('class Solution:'):
                    # Look for the method definition in the next few lines
                    line_idx = lines.index(line)
                    for i, next_line in enumerate(lines[line_idx:line_idx+10]):
                        if next_line.strip().startswith('def ') and ':' in next_line:
                            method_line = next_line.strip()
                            if method_line.endswith(':'):
                                return f"class Solution:\n    {method_line}\n        pass"
                            else:
                                return f"class Solution:\n    {method_line}:\n        pass"
            
            # Fallback if no function found
            return "def solution():\n    pass"
            
        except Exception as e:
            print(f"Error extracting function signature: {e}")
            return "def solution():\n    pass"

# Initialize Flask app
app = Flask(__name__)
sock = Sock(app)

# Configure CORS from environment variables
allowed_origins = os.getenv('ALLOWED_ORIGINS', 'http://localhost:3000').split(',')
CORS(app, origins=allowed_origins)

# Initialize database
print("Initializing database...")
db_path = os.getenv('DATABASE_PATH', 'data/zerotohire.db')
db = Database(db_path)
print(f"Database initialized at {db_path}")

# Initialize the assistant (this will take a moment)
print("Initializing AI Assistant...")

# Get model configuration from environment
model_repo = os.getenv('HUGGINGFACE_MODEL_REPO', 'Qwen/Qwen2.5-Coder-14B-Instruct-GGUF')
model_filename = os.getenv('HUGGINGFACE_MODEL_FILENAME', 'qwen2.5-coder-14b-instruct-q4_k_m.gguf')

model_path = hf_hub_download(repo_id=model_repo, filename=model_filename)
tutor = CodingTutor(model_path, db)

# Load your enhanced LeetCode dataset from Hugging Face
print("Loading LeetCode dataset from Hugging Face...")
dataset_name = os.getenv('LEETCODE_DATASET', 'viccon23/leetcode')
dataset = load_dataset(dataset_name)

print("Loaded, lets roll.")
print(f"Dataset contains {len(dataset['train'])} problems")

print("Backend ready!")

@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat messages from the frontend"""
    try:
        data = request.json
        
        # Validate input
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        message = data.get('message', '').strip()
        if not message:
            return jsonify({'error': 'No message provided'}), 400
        
        # Get optional code context
        code_context = data.get('codeContext')  # {'code': '...', 'includeInContext': true}

        # Handle simple slash commands without invoking the LLM
        lower = message.lower()
        if lower.startswith('/done') or lower.startswith('/complete') or lower == 'mark as complete':
            if tutor.current_problem is None:
                # No current problem to complete
                sys_msg = {
                    'role': 'system',
                    'content': 'No problem is currently loaded to mark as complete.',
                    'timestamp': datetime.now().isoformat()
                }
                tutor.conversation_history.append(sys_msg)
                tutor.save_session()
                return jsonify({
                    'response': sys_msg['content'],
                    'conversation_history': tutor.conversation_history,
                    'current_problem': tutor.current_problem,
                    'problem_changed': False
                })

            pid = tutor.current_problem.get('id')
            if pid is not None:
                tutor.mark_problem_completed(pid)
            sys_msg = {
                'role': 'system',
                'content': f"Problem '{tutor.current_problem.get('title','')}' marked as completed.",
                'timestamp': datetime.now().isoformat()
            }
            tutor.conversation_history.append(sys_msg)
            tutor.save_session()
            return jsonify({
                'response': sys_msg['content'],
                'conversation_history': tutor.conversation_history,
                'current_problem': tutor.current_problem,
                'problem_changed': False
            })
        
        # Pass code context if provided and enabled
        context = None
        if code_context and code_context.get('includeInContext', False):
            context = code_context
        
        response = tutor.chat(message, code_context=context)
        
        return jsonify({
            'response': response,
            'conversation_history': tutor.conversation_history,
            'current_problem': tutor.current_problem,
            'problem_changed': False
        })
    
    except ValueError as e:
        return jsonify({'error': f'Invalid input: {str(e)}'}), 400
    except Exception as e:
        print(f"Error in chat endpoint: {str(e)}")
        return jsonify({'error': 'An error occurred processing your message. Please try again.'}), 500


@sock.route('/ws/chat')
def chat_socket(ws):
    """WebSocket endpoint for streaming chatbot responses."""
    while True:
        try:
            payload_raw = ws.receive()
        except Exception as exc:
            print(f"WebSocket receive error: {exc}")
            break

        if payload_raw is None:
            break

        try:
            payload = json.loads(payload_raw)
        except json.JSONDecodeError:
            ws.send(json.dumps({'type': 'error', 'error': 'Invalid JSON payload'}))
            continue

        message = payload.get('message', '').strip()
        if not message:
            ws.send(json.dumps({'type': 'error', 'error': 'No message provided'}))
            continue

        code_context_payload = payload.get('codeContext')
        context = None
        if code_context_payload and code_context_payload.get('includeInContext'):
            context = code_context_payload

        lower = message.lower()
        if lower.startswith('/done') or lower.startswith('/complete') or lower == 'mark as complete':
            if tutor.current_problem is None:
                response_text = 'No problem is currently loaded to mark as complete.'
            else:
                pid = tutor.current_problem.get('id')
                if pid is not None:
                    tutor.mark_problem_completed(pid)
                response_text = f"Problem '{tutor.current_problem.get('title','')}' marked as completed."

            ws.send(json.dumps({
                'type': 'final',
                'message': response_text,
                'conversation_history': tutor.conversation_history,
                'current_problem': tutor.current_problem,
                'problem_changed': False
            }))
            continue

        for event in tutor.chat_stream(message, code_context=context):
            if event['type'] == 'token':
                ws.send(json.dumps({'type': 'token', 'token': event['token']}))
            elif event['type'] == 'error':
                ws.send(json.dumps({'type': 'error', 'error': event['error']}))
                break
            elif event['type'] == 'final':
                ws.send(json.dumps({
                    'type': 'final',
                    'message': event['message'],
                    'conversation_history': tutor.conversation_history,
                    'current_problem': tutor.current_problem,
                    'problem_changed': False
                }))


@app.route('/api/problems', methods=['GET'])
def get_problems():
    """Get all problems with optional filtering and pagination"""
    try:
        # Get query parameters for filtering
        difficulty_filters = request.args.getlist('difficulty')  # Can have multiple
        type_filters = request.args.getlist('type')              # Can have multiple
        search_query = request.args.get('search', '').lower()    # Search in title
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        
        problems = []
        for i, prob in enumerate(dataset["train"]):
            # Apply filters
            if difficulty_filters and prob.get('difficulty') not in difficulty_filters:
                continue
                
            # Check if ALL of the selected types are present in the problem's types (AND logic)
            if type_filters:
                problem_types_str = prob.get('problem_types', '')
                # Check that every selected type is present in the problem's types
                if not all(ptype in problem_types_str for ptype in type_filters):
                    continue
                
            if search_query and search_query not in prob['title'].lower():
                continue
            
            # Process problem types into an array
            problem_types_str = prob.get('problem_types', '')
            problem_types_array = []
            if problem_types_str:
                problem_types_array = [ptype.strip() for ptype in problem_types_str.split(',') if ptype.strip()]
            
            problems.append({
                'id': i,
                'title': prob['title'],
                'difficulty': prob.get('difficulty', 'Unknown'),
                'problem_types': problem_types_array,
                'completed': tutor.is_problem_completed(i)
            })
        
        # Apply pagination
        total_problems = len(problems)
        start_index = (page - 1) * per_page
        end_index = start_index + per_page
        paginated_problems = problems[start_index:end_index]
        
        return jsonify({
            'problems': paginated_problems,
            'total': total_problems,
            'page': page,
            'per_page': per_page,
            'has_more': end_index < total_problems
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/problems/<int:problem_id>', methods=['POST'])
def select_problem(problem_id):
    """Select a specific problem by ID"""
    try:
        if problem_id < 0 or problem_id >= len(dataset["train"]):
            return jsonify({'error': 'Invalid problem ID'}), 400
        
        selected_problem = dataset["train"][problem_id]
        
        # Process problem types into an array
        problem_types_str = selected_problem.get('problem_types', '')
        problem_types_array = []
        if problem_types_str:
            problem_types_array = [ptype.strip() for ptype in problem_types_str.split(',') if ptype.strip()]
        
        # Extract function signature from the python solution
        python_solution = selected_problem.get('python', '')
        template_code = tutor.extract_function_signature(python_solution)
        
        # Set the problem in the tutor session
        problem_data = {
            'id': problem_id,
            'title': selected_problem['title'],
            'description': selected_problem['content'],
            'problem_types': problem_types_array,
            'difficulty': selected_problem.get('difficulty', 'Unknown'),
            'completed': tutor.is_problem_completed(problem_id),
            'template_code': template_code
        }
        response = tutor.set_problem(problem_data)
        
        return jsonify({
            'response': response,
            'problem': problem_data,
            'conversation_history': tutor.conversation_history,
            'problem_changed': True
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@app.route('/api/problems/<int:problem_id>/completion', methods=['POST'])
def toggle_problem_completion(problem_id):

    try:
        if problem_id < 0 or problem_id >= len(dataset["train"]):
            return jsonify({'error': 'Invalid problem ID'}), 400
        data = request.json
        completed = data.get('completed', False)

        if completed:
            tutor.mark_problem_completed(problem_id)
        else:
            tutor.mark_problem_uncompleted(problem_id)
        
        return jsonify({
            'problem_id': problem_id,
            'completed': completed,
            'message': f'Problem {"completed" if completed else "uncompleted"} successfully'
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/filters', methods=['GET'])
def get_filters():
    """Get available filter options"""
    try:
        # Get unique difficulties
        difficulties = set()
        problem_types = set()
        
        for prob in dataset["train"]:
            difficulty = prob.get('difficulty')
            if difficulty:
                difficulties.add(difficulty)
            
            types = prob.get('problem_types', '')
            if types:
                # Split problem types and clean them
                for ptype in types.split(','):
                    cleaned_type = ptype.strip()
                    if cleaned_type:
                        problem_types.add(cleaned_type)
        
        return jsonify({
            'difficulties': sorted(list(difficulties)),
            'problem_types': sorted(list(problem_types))
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/evaluate-code', methods=['POST'])
def evaluate_code():
    """Evaluate user's code submission"""
    try:
        data = request.json
        code = data.get('code', '')
        language = data.get('language', 'python')
        
        if not code.strip():
            return jsonify({'error': 'No code provided'}), 400
        
        response = tutor.evaluate_code(code, language)
        
        return jsonify({
            'response': response,
            'conversation_history': tutor.conversation_history
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/clear-chat', methods=['POST'])
def clear_session():
    """Clear the current chat"""
    try:
        tutor.clear_chat()
        return jsonify({'message': 'Session cleared successfully'})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/problem/reset', methods=['POST'])
def reset_problem():
    """Reset a problem completely: clear messages, delete code, mark as incomplete"""
    try:
        data = request.json
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        problem_id = data.get('problem_id')
        
        if problem_id is None:
            return jsonify({'error': 'Problem ID is required'}), 400
        
        db.reset_problem(problem_id)
        
        # If this is the current problem, clear the in-memory conversation history too
        if tutor.current_problem and tutor.current_problem.get('id') == problem_id:
            tutor.conversation_history = []
        
        return jsonify({'message': 'Problem reset successfully'}), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/code/save', methods=['POST'])
def save_code():
    """Save code snapshot for the current problem"""
    try:
        data = request.json
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        problem_id = data.get('problem_id')
        code = data.get('code', '')
        language = data.get('language', 'python')
        
        if problem_id is None:
            return jsonify({'error': 'Problem ID is required'}), 400
        
        db.save_code(problem_id, code, language)
        
        return jsonify({
            'message': 'Code saved successfully',
            'problem_id': problem_id
        })
    
    except Exception as e:
        print(f"Error in save_code endpoint: {str(e)}")
        return jsonify({'error': 'Failed to save code'}), 500


@app.route('/api/code/load/<int:problem_id>', methods=['GET'])
def load_code(problem_id):
    """Load the latest code for a problem"""
    try:
        code = db.get_latest_code(problem_id)
        
        return jsonify({
            'problem_id': problem_id,
            'code': code or ''
        })
    
    except Exception as e:
        print(f"Error in load_code endpoint: {str(e)}")
        return jsonify({'error': 'Failed to load code'}), 500


@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Get all user settings"""
    try:
        settings = db.get_all_settings()
        return jsonify(settings)
    
    except Exception as e:
        print(f"Error in get_settings endpoint: {str(e)}")
        return jsonify({'error': 'Failed to load settings'}), 500


@app.route('/api/settings/<setting_key>', methods=['POST'])
def save_setting(setting_key):
    """Save a user setting"""
    ALLOWED_SETTINGS = {'includeCodeInContext', 'theme', 'fontSize'}
    try:
        data = request.json
        
        if not data or 'value' not in data:
            return jsonify({'error': 'Value is required'}), 400
        
        if setting_key not in ALLOWED_SETTINGS:
            return jsonify({'error': 'Invalid setting key'}), 400
        
        db.save_setting(setting_key, data['value'])
        
        return jsonify({
            'message': 'Setting saved successfully',
            'key': setting_key,
            'value': data['value']
        })
    
    except Exception as e:
        print(f"Error in save_setting endpoint: {str(e)}")
        return jsonify({'error': 'Failed to save setting'}), 500


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get user statistics"""
    try:
        stats = db.get_user_stats()
        return jsonify(stats)
    
    except Exception as e:
        print(f"Error in get_stats endpoint: {str(e)}")
        return jsonify({'error': 'Failed to load statistics'}), 500


@app.route('/api/status', methods=['GET'])
def get_status():
    """Get current session status"""
    current = tutor.current_problem
    # Attach completion flag if there's a current problem
    if current is not None:
        current_with_flag = dict(current)
        pid = current.get('id')
        current_with_flag['completed'] = tutor.is_problem_completed(pid) if pid is not None else False
    else:
        current_with_flag = None
    return jsonify({
        'current_problem': current_with_flag,
        'conversation_history': tutor.conversation_history,
        'message_count': len(tutor.conversation_history)
    })

if __name__ == '__main__':
    # Get Flask configuration from environment
    host = os.getenv('FLASK_HOST', '127.0.0.1')
    port = int(os.getenv('FLASK_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    app.run(debug=debug, host=host, port=port)

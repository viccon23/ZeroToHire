from flask import Flask, request, jsonify
from flask_cors import CORS
from datasets import load_dataset
from huggingface_hub import hf_hub_download
import torch
from llama_cpp import Llama
import json
import os
from datetime import datetime
import re

class CodingTutor:
    def __init__(self, model_path, session_file="tutor_session.json"):
        self.session_file = session_file
        self.conversation_history = []
        self.current_problem = None
        
        # Load existing session if it exists
        self.load_session()
        
        # Load the model
        print("Loading model...")
        print("Checking CUDA availability...")
        print(f"PyTorch CUDA available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"GPU device: {torch.cuda.get_device_name(0)}")
        
        self.llm = Llama(
            model_path=model_path,
            n_ctx=4096,
            n_threads=4,
            n_gpu_layers=-1,  
            verbose=True,    
            n_batch=512,     
            use_mmap=True,    
            use_mlock=False   
        )
        print("Model loaded successfully!")
    
    def load_session(self):
        """Load previous conversation history from file"""
        if os.path.exists(self.session_file):
            try:
                with open(self.session_file, 'r', encoding='utf-8') as f:
                    session_data = json.load(f)
                    self.conversation_history = session_data.get('conversation_history', [])
                    self.current_problem = session_data.get('current_problem', None)
                print(f"Loaded previous session with {len(self.conversation_history)} messages")
            except Exception as e:
                print(f"Could not load session: {e}")
                self.conversation_history = []
    
    def save_session(self):
        """Save current conversation history to file"""
        session_data = {
            'conversation_history': self.conversation_history,
            'current_problem': self.current_problem,
            'last_updated': datetime.now().isoformat()
        }
        try:
            with open(self.session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Could not save session: {e}")
    
    def set_problem(self, problem_title, problem_desc):
        """Set a new coding problem"""
        self.current_problem = {
            'title': problem_title,
            'description': problem_desc
        }
        
        # Add system message about the new problem
        system_msg = f"New coding problem started: {problem_title}"
        self.conversation_history.append({
            'role': 'system',
            'content': system_msg,
            'timestamp': datetime.now().isoformat()
        })
        
        # Check if this is the first problem or a new problem in an existing session
        has_previous_conversation = len([msg for msg in self.conversation_history if msg['role'] in ['user', 'assistant', 'alex']]) > 0
        
        if has_previous_conversation:
            # Continuing session with new problem
            response = f"Great! Let's work on '{problem_title}'. I can see you have the problem description. Before we dive into coding, let's make sure we understand what we're being asked to do. Can you tell me in your own words what this problem is asking for? Let me know if you have any questions!"
        else:
            # First problem in session
            response = f"Hello! I'm Alex, your coding assistant. I see you're working on '{problem_title}'. Before we start coding, let's make sure we understand the problem. Can you read through the problem description and tell me what you think it's asking us to do? Let me know if you have any questions!"
        
        # Add the response directly to history instead of generating it
        self.conversation_history.append({
            'role': 'alex',
            'content': response,
            'timestamp': datetime.now().isoformat()
        })
        
        # Save session after adding the response
        self.save_session()
        
        return response
    
    def chat(self, user_message, is_initial=False):
        """Continue the conversation with Alex"""
        self.conversation_history.append({
            'role': 'user',
            'content': user_message,
            'timestamp': datetime.now().isoformat()
        })
        
        # Build the full conversation context
        conversation_context = self._build_conversation_context(user_message if is_initial else None)
        
        # Generate response
        response = self.llm(
            conversation_context,
            max_tokens= 400,
            temperature=0.7,
            top_p=0.9,
            echo=False,
            stop=["Student:", "User:", "Alex:", "\n\nAlex:", "\nAlex:"]
        )
        
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
        self.conversation_history.append({
            'role': 'alex',
            'content': response,
            'timestamp': datetime.now().isoformat()
        })
        
        # Save session after each interaction
        self.save_session()
        
        return response
    
    def _clean_response(self, response):
        """Clean up the response to remove stage directions and unwanted patterns"""
        import re
        
        # Remove stage directions in parentheses like "(pauses)", "(thinks)", etc, and common unwanted patterns and phrases.
        response = re.sub(r'\([^)]*\)', '', response)
        response = re.sub(r'\*[^*]*\*', '', response)  # Remove *action* text
        response = re.sub(r'\b(let me think|thinking|pondering|considering)\b', '', response, flags=re.IGNORECASE)
        
        # Remove trailing colons that might be conversation artifacts
        response = re.sub(r':\s*$', '', response)
        
        # Clean up extra whitespace and normalize spaces
        response = ' '.join(response.split())
        
        return response.strip()
    
    
    def _build_conversation_context(self, initial_prompt=None):
        """Build the full conversation context for the model"""
        if initial_prompt:
            return initial_prompt
        
        '''
        Here's where we'll let the llm know of what it should and shouldn't do. Finetuning would be good for getting it to sound more human, 
        but I'm too lazy to create a dataset of conversations for that.
        '''
        context_parts = []
        
        # Core Role and Instructions
        context_parts.append("You are Alex, an expert coding tutor specializing in LeetCode problems. Your name is Alex.")
        context_parts.append("The user is the student. Never refer to the user as 'Alex'.")
        context_parts.append("Your goal is to guide the user to a solution, providing hints and asking questions to foster discovery, but provide the solution with explanation and Python code if they explicitly give up or request it.")
        
        # LeetCode-Specific Guidance
        context_parts.append("For LeetCode problems, summarize key constraints (e.g., input size, edge cases) and guide the student to consider time and space complexity.")
        context_parts.append("Encourage exploration of algorithmic patterns (e.g., two-pointer, dynamic programming, greedy) when relevant.")
        context_parts.append("If the student submits code, analyze it for correctness, efficiency, and edge cases. Provide specific feedback and suggest improvements without rewriting unless requested.")
        
        # Communication Style
        context_parts.append("COMMUNICATION STYLE:")
        context_parts.append("- Be direct, honest, and natural. If you don't understand something, ask for clarification.")
        context_parts.append("- Maintain an encouraging tone, especially when the student is frustrated, and celebrate small wins.")
        context_parts.append("- Keep responses concise and focused. Ask ONE clear question at a time rather than multiple questions.")
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
        
        # Problem and User Context
        if self.current_problem:
            context_parts.append(f"CURRENT PROBLEM: {self.current_problem['title']}")
            context_parts.append(f"Difficulty: {self.current_problem.get('difficulty', 'Not specified')}")
            context_parts.append("Focus all tutoring efforts on helping the student solve THIS specific problem.")
            context_parts.append("")
        else:
            context_parts.append("No problem is currently loaded. Encourage the student to use the 'Browse Problems' button to select a problem to work on.")
            context_parts.append("")

        history_limit = 10
        recent_history = self.conversation_history
        recent_history_wlimit = recent_history[-history_limit:]

        for msg in recent_history_wlimit:
            if msg['role'] == 'user':
                context_parts.append(f"Student: {msg['content']}")
            elif msg['role'] == 'alex':
                context_parts.append(f"Alex: {msg['content']}")
        context_parts.append("")
        context_parts.append("Alex:")
        return "\n".join(context_parts)
    
    def clear_session(self):
        """Clear the current session and start fresh"""
        self.conversation_history = []
        self.current_problem = None
        if os.path.exists(self.session_file):
            os.remove(self.session_file)
        print("Session cleared!")

    def evaluate_code(self, code, language="python"):
        """Evaluate user's code attempt"""
        if not self.current_problem:
            return "No problem is currently loaded."
        
        eval_prompt = f"""The student has submitted the following {language} code for the problem "{self.current_problem['title']}":
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
        
        # Generate response
        response = self.llm(
            full_context,
            max_tokens=300,  # Much more conservative limit
            temperature=0.7,
            top_p=0.9,
            echo=False,
            stop=["Student:", "User:", "Alex:", "\n\nAlex:"]
        )
        
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
        self.conversation_history.append({
            'role': 'alex',
            'content': response,
            'timestamp': datetime.now().isoformat()
        })
        
        self.save_session()
        return response

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Initialize the assistant (this will take a moment)
print("Initializing AI Assistant...")
# Using Qwen 7B model for better general tutoring capabilities
model_path = hf_hub_download(repo_id="Qwen/Qwen2.5-Coder-7B-Instruct-GGUF", 
                            filename="qwen2.5-coder-7b-instruct-q4_k_m.gguf")
tutor = CodingTutor(model_path, session_file="backend_session.json")

# Load your enhanced LeetCode dataset from Hugging Face
print("Loading LeetCode dataset from Hugging Face...")
dataset = load_dataset("viccon23/leetcode")

print("Loaded, lets roll.")
print(f"Dataset contains {len(dataset['train'])} problems")

print("Backend ready!")

@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat messages from the frontend"""
    try:
        data = request.json
        message = data.get('message', '')
        
        if not message:
            return jsonify({'error': 'No message provided'}), 400
        
        # Regular chat response - no more automatic problem detection
        response = tutor.chat(message)
        
        return jsonify({
            'response': response,
            'conversation_history': tutor.conversation_history,
            'current_problem': tutor.current_problem,
            'problem_changed': False
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
                'problem_types': problem_types_array
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
        
        # Process problem types into an array (same as in get_problems)
        problem_types_str = selected_problem.get('problem_types', '')
        problem_types_array = []
        if problem_types_str:
            problem_types_array = [ptype.strip() for ptype in problem_types_str.split(',') if ptype.strip()]
        
        # Set the problem in the tutor session
        response = tutor.set_problem(selected_problem['title'], selected_problem['content'])
        
        return jsonify({
            'response': response,
            'problem': {
                'id': problem_id,
                'title': selected_problem['title'],
                'description': selected_problem['content'],
                'problem_types': problem_types_array,
                'difficulty': selected_problem.get('difficulty', 'Unknown')
            },
            'conversation_history': tutor.conversation_history,
            'problem_changed': True
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

@app.route('/api/clear-session', methods=['POST'])
def clear_session():
    """Clear the current session"""
    try:
        tutor.clear_session()
        return jsonify({'message': 'Session cleared successfully'})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get current session status"""
    return jsonify({
        'current_problem': tutor.current_problem,
        'conversation_history': tutor.conversation_history,
        'message_count': len(tutor.conversation_history)
    })

if __name__ == '__main__':
    app.run(debug=False, host='127.0.0.1', port=5000)

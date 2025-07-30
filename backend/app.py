from flask import Flask, request, jsonify
from flask_cors import CORS
from datasets import load_dataset
from huggingface_hub import hf_hub_download
import torch
from llama_cpp import Llama
import json
import os
from datetime import datetime
import random

# Backend for AI Coding Tutor using Llama model
# This code provides a Flask API for an AI coding tutor that helps users with coding problems.
# It allows users to chat with the tutor, load coding problems, evaluate code submissions, and manage session history.
# The tutor uses a pre-trained Llama model (wizardcoder-python-13b-v1.0)  (NOW Qwen 7b) to generate responses and guide users through coding challenges.

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
        """Set a new coding problem for tutoring"""
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
        has_previous_conversation = len([msg for msg in self.conversation_history if msg['role'] in ['user', 'assistant']]) > 0
        
        if has_previous_conversation:
            # Continuing session with new problem
            intro_prompt = f"""You are Alex, a coding tutor. The student wants to work on: {problem_title}

            Be a Socratic tutor - guide through questions, don't give away answers.

            Respond as Alex: "Great! Let's work on {problem_title}. I can see you have the problem description. Before we dive into coding, let's make sure we understand what we're being asked to do. Can you tell me in your own words what this problem is asking for?"

            Alex:"""
        else:
            # First problem in session
            intro_prompt = f"""You are Alex, a coding tutor starting a session. The student's first problem is: {problem_title}

            Be a Socratic tutor - guide through questions, don't give away answers.

            Respond as Alex: "Hello! I'm Alex, your coding tutor. I see you're working on {problem_title}. Before we start coding, let's make sure we understand the problem. Can you read through the problem description and tell me what you think it's asking us to do?"

            Alex:"""
        
        return self.chat(intro_prompt, is_initial=True)
    
    def chat(self, user_message, is_initial=False):
        """Continue the conversation with the tutor"""
        # Add user message to history (unless it's the initial problem setup)
        if not is_initial:
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
            max_tokens=800,
            temperature=0.7,
            top_p=0.9,
            echo=False,
            stop=["Human:", "User:", "Student:", "Alex:"]
        )
        
        # Extract response text and clean it up
        tutor_response = response['choices'][0]['text'].strip()
        
        
        # Add tutor response to history
        self.conversation_history.append({
            'role': 'tutor',
            'content': tutor_response,
            'timestamp': datetime.now().isoformat()
        })
        
        # Save session after each interaction
        self.save_session()
        
        return tutor_response
    
    
    def _build_conversation_context(self, initial_prompt=None):
        """Build the full conversation context for the model"""
        if initial_prompt:
            return initial_prompt
        
        context_parts = []
        
        context_parts.append("You are Alex, an expert coding tutor who uses the Socratic method.")
        context_parts.append("CRITICAL: Stay focused on the current problem. Don't introduce irrelevant topics.")
        context_parts.append("TUTORING APPROACH:")
        context_parts.append("- Ask questions to guide student discovery")
        context_parts.append("- Let students work through problems themselves")
        context_parts.append("- Give hints only when students are stuck")
        context_parts.append("- Correct misconceptions with gentle questions")
        context_parts.append("- Celebrate student insights and progress")
        context_parts.append("- Keep discussions relevant to the current problem")
        context_parts.append("NEVER DO:")
        context_parts.append("- Give away complete algorithms or solutions")
        context_parts.append("- List out all the steps to solve a problem")
        context_parts.append("- Introduce tangential topics (like overflow in other languages)")
        context_parts.append("- Discuss implementation details not relevant to the core problem")
        context_parts.append("- Provide code unless the student asks for help with syntax")
        context_parts.append("")
        
        if self.current_problem:
            context_parts.append(f"Current Problem: {self.current_problem['title']}")
            context_parts.append("")
        
        recent_history = self.conversation_history[-10:]
        
        for msg in recent_history:
            if msg['role'] == 'user':
                context_parts.append(f"Student: {msg['content']}")
            elif msg['role'] == 'tutor':
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
        
        # Analyze the code more thoroughly
        code_lines = [line.strip() for line in code.split('\n') if line.strip()]
        
        # Check if it's just boilerplate
        is_boilerplate = True
        meaningful_lines = []
        
        for line in code_lines:
            # Skip class definition, function signature, pass statements, and comments
            if (line.startswith('class ') or 
                line.startswith('def ') or 
                line == 'pass' or 
                line.startswith('#') or
                line.endswith(': None:') or
                line.endswith('-> None:')):
                continue
            else:
                meaningful_lines.append(line)
                is_boilerplate = False
        
        if is_boilerplate:
            # It's just boilerplate - guide them to start implementing
            eval_prompt = f"""The student submitted only the boilerplate code for "{self.current_problem['title']}":
                ```{language}
                {code}
                ```

                This is just the function signature with no implementation. As their Socratic tutor:
                - Ask them what the first step should be
                - Guide them to think about the problem requirements  
                - Don't give away the solution, but help them identify what they need to implement

                Be encouraging but point out they need to start implementing logic."""
        else:
            # There's actual implementation - analyze it properly
            eval_prompt = f"""The student has submitted the following {language} code for the problem "{self.current_problem['title']}":
                ```{language}
                {code}
                ```

                As their Socratic tutor, analyze this code:
                - Ask questions about their approach
                - If there are bugs, guide them to find them through questions
                - If it's correct, ask them to explain how it works
                - Suggest improvements through questioning, not direct answers

                Be encouraging and use questions to guide their learning."""
        return self.chat(eval_prompt)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Initialize the tutor (this will take a moment)
print("Initializing AI Tutor...")
# Using Qwen 7B model for better general tutoring capabilities
model_path = hf_hub_download(repo_id="Qwen/Qwen2.5-Coder-7B-Instruct-GGUF", 
                            filename="qwen2.5-coder-7b-instruct-q4_k_m.gguf")
tutor = CodingTutor(model_path, session_file="backend_session.json")

# Load LeetCode dataset
dataset = load_dataset("greengerong/leetcode")
print("Backend ready!")

@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat messages from the frontend"""
    try:
        data = request.json
        message = data.get('message', '')
        
        if not message:
            return jsonify({'error': 'No message provided'}), 400
        
        # Check if user is requesting a specific type of problem
        message_lower = message.lower()
        # More specific keywords to avoid false positives when asking for explanations
        problem_request_keywords = ['new problem', 'different problem', 'another problem', 'next problem',
                                  'give me an array problem', 'give me a string problem', 'give me a tree problem',
                                  'give me a linked list problem', 'give me a graph problem', 'give me a dynamic programming problem',
                                  'give me a sorting problem', 'give me a binary search problem', 'give me a hash problem',
                                  'give me a stack problem', 'give me a queue problem', 'random problem', 'give me a problem']
        
        # Also check for "can I get" and "I want" patterns
        additional_patterns = ['can i get', 'can you give me', 'i want a', 'i need a', 'show me a', 'find me a']
        
        is_problem_request = any(keyword in message_lower for keyword in problem_request_keywords)
        
        # Check for additional patterns combined with problem types
        if not is_problem_request:
            for pattern in additional_patterns:
                if pattern in message_lower and ('problem' in message_lower or 'question' in message_lower):
                    is_problem_request = True
                    break
        
        if is_problem_request:
            # Check if it's a random problem request
            if 'random' in message_lower or 'give me a problem' in message_lower:
                problem_type = ''  # Empty means random selection
            else:
                # Extract the type of problem they want
                problem_type = ''
                if 'array' in message_lower:
                    problem_type = 'arrays'
                elif 'string' in message_lower:
                    problem_type = 'strings'
                elif 'tree' in message_lower:
                    problem_type = 'trees'
                elif 'linked list' in message_lower:
                    problem_type = 'linked lists'
                elif 'graph' in message_lower:
                    problem_type = 'graphs'
                elif 'dynamic programming' in message_lower or 'dp' in message_lower:
                    problem_type = 'dynamic programming'
                elif 'sort' in message_lower:
                    problem_type = 'sorting'
                elif 'binary search' in message_lower:
                    problem_type = 'binary search'
                elif 'two pointer' in message_lower:
                    problem_type = 'two pointers'
                elif 'sliding window' in message_lower:
                    problem_type = 'sliding window'
                elif 'hash' in message_lower:
                    problem_type = 'hash tables'
                elif 'stack' in message_lower:
                    problem_type = 'stacks'
                elif 'queue' in message_lower:
                    problem_type = 'queues'
            
            # Get a problem of the requested type
            problem_data = get_requested_problem(problem_type)
            
            return jsonify({
                'response': problem_data['response'],
                'conversation_history': problem_data['conversation_history'],
                'current_problem': problem_data['problem'],
                'problem_changed': True  # Flag to indicate the problem changed
            })
        
        # Regular chat response
        response = tutor.chat(message)
        
        return jsonify({
            'response': response,
            'conversation_history': tutor.conversation_history[-10:],  # Last 10 messages
            'current_problem': tutor.current_problem
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/new-problem', methods=['POST'])
def new_problem():
    """Load a new random problem"""
    try:
        # Handle both JSON and non-JSON requests
        if request.is_json:
            data = request.json or {}
        else:
            # Handle requests without proper Content-Type header
            data = {}
            
        user_request = data.get('request', '')  # Optional user request for specific type
        
        print(f"New problem request: {user_request}")  # Debug logging
        
        if user_request.strip():
            # User requested a specific type of problem - let LLM choose
            response_data = get_requested_problem(user_request)
        else:
            # Get a random problem as before
            problem_index = random.randint(0, min(100, len(dataset["train"])-1))
            sample = dataset["train"][problem_index]
            
            print(f"Selected random problem: {sample['title']}")
            
            response = tutor.set_problem(sample['title'], sample['content'])
        
            response_data = {
                'response': response,
                'problem': {
                    'title': sample['title'],
                    'description': sample['content']
                },
                'conversation_history': tutor.conversation_history[-10:]
            }
        
        return jsonify(response_data)
    
    except Exception as e:
        print(f"Error in new_problem: {str(e)}")  # Debug logging
        import traceback
        traceback.print_exc()  # Print full stack trace
        return jsonify({'error': str(e)}), 500

def get_requested_problem(user_request):
    """Find and select a problem based on user's request"""
    try:
        print(f"Processing problem request: '{user_request}'")  # Debug logging
        
        # If no specific request or random request, pick any problem
        if not user_request.strip() or user_request.lower() in ['random', '']:
            problem_index = random.randint(0, min(100, len(dataset["train"])-1))
            selected_problem = dataset["train"][problem_index]
            tutor_message = "Here's a random problem for you to work on!"
        else:
            # Filter problems based on common keywords
            keywords = user_request.lower()
            filtered_problems = []
            
            print(f"Searching for problems with keywords: {keywords}")  # Debug logging
            
            # Search through first 200 problems for better variety
            for i in range(min(200, len(dataset["train"]))):
                problem = dataset["train"][i]
                title_lower = problem['title'].lower()
                content_lower = problem['content'].lower()
                
                # Check if the problem matches user's request
                if ('array' in keywords and ('array' in title_lower or 'array' in content_lower)) or \
                   ('string' in keywords and ('string' in title_lower or 'string' in content_lower)) or \
                   ('tree' in keywords and ('tree' in title_lower or 'binary tree' in content_lower)) or \
                   ('linked list' in keywords and ('linked list' in title_lower or 'listnode' in content_lower)) or \
                   ('graph' in keywords and ('graph' in title_lower or 'graph' in content_lower)) or \
                   ('dynamic programming' in keywords and ('dynamic' in content_lower or 'dp' in content_lower)) or \
                   ('sorting' in keywords and ('sort' in title_lower or 'sort' in content_lower)) or \
                   ('binary search' in keywords and ('binary search' in title_lower or 'binary search' in content_lower)) or \
                   ('two pointer' in keywords and ('two pointer' in content_lower or 'pointer' in title_lower)) or \
                   ('sliding window' in keywords and ('sliding window' in content_lower or 'window' in title_lower)) or \
                   ('hash' in keywords and ('hash' in title_lower or 'hash' in content_lower)) or \
                   ('stack' in keywords and ('stack' in title_lower or 'stack' in content_lower)) or \
                   ('queue' in keywords and ('queue' in title_lower or 'queue' in content_lower)):
                    filtered_problems.append(problem)
            
            print(f"Found {len(filtered_problems)} matching problems")  # Debug logging
            
            if not filtered_problems:
                # Fallback to random problem if no matches found
                problem_index = random.randint(0, min(100, len(dataset["train"])-1))
                selected_problem = dataset["train"][problem_index]
                tutor_message = f"I couldn't find a specific problem matching '{user_request}', so I picked this random one for you!"
            else:
                # Randomly select from filtered problems
                selected_problem = random.choice(filtered_problems)
                tutor_message = f"Perfect! I found a {user_request} problem for you. Here's what we'll work on:"
        
        print(f"Selected problem: {selected_problem['title']}")  # Debug logging
        
        # Set the problem and get tutor response
        tutor.set_problem(selected_problem['title'], selected_problem['content'])
        
        # Override the tutor's response to acknowledge the specific request
        tutor.conversation_history[-1]['content'] = tutor_message
        
        return {
            'response': tutor_message,
            'problem': {
                'title': selected_problem['title'],
                'description': selected_problem['content']
            },
            'conversation_history': tutor.conversation_history[-10:]
        }
        
    except Exception as e:
        print(f"Error in get_requested_problem: {str(e)}")  # Debug logging
        import traceback
        traceback.print_exc()
        
        # Fallback to random problem on error
        problem_index = random.randint(0, min(100, len(dataset["train"])-1))
        sample = dataset["train"][problem_index]
        response = tutor.set_problem(sample['title'], sample['content'])
        
        return {
            'response': f"I had trouble finding that specific type, but here's a good problem to work on!",
            'problem': {
                'title': sample['title'],
                'description': sample['content']
            },
            'conversation_history': tutor.conversation_history[-10:]
        }

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
            'conversation_history': tutor.conversation_history[-10:]
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
        'conversation_history': tutor.conversation_history[-10:],
        'message_count': len(tutor.conversation_history)
    })

if __name__ == '__main__':
    app.run(debug=False, host='127.0.0.1', port=5000)

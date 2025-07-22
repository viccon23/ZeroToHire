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
# The tutor uses a pre-trained Llama model (wizardcoder-python-13b-v1.0) to generate responses and guide users through coding challenges.

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
            n_gpu_layers=-1,  # Use all available GPU layers
            verbose=True,     # Enable verbose output to see GPU usage
            n_batch=512,      # Increase batch size for better GPU utilization
            use_mmap=True,    # Use memory mapping
            use_mlock=False   # Don't lock memory
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
            intro_prompt = f"""You are a coding tutor named Alex. The student wants to work on a new problem: {problem_title}

Say something like "Great! Let's work on a new problem. Here's what we'll be tackling next:" and then briefly introduce the problem.

Tutor:"""
        else:
            # First problem in session
            intro_prompt = f"""You are a coding tutor named Alex. A student has just started their first coding session with the problem: {problem_title}

Say: "Hello! I'm Alex, your coding tutor. I'm here to help you learn and practice coding problems step by step. Let's start with this problem!" Then ask if they'd like to see the problem statement.

Tutor:"""
        
        return self.chat(intro_prompt, is_initial=True)
    
    def get_function_signature(self, problem_desc):
        """Extract or generate function signature from problem description"""
        title_lower = self.current_problem['title'].lower()
        
        # Common LeetCode function patterns with class Solution wrapper
        if "two sum" in title_lower:
            return "class Solution:\n    def twoSum(self, nums: List[int], target: int) -> List[int]:"
        elif "add two numbers" in title_lower:
            return "class Solution:\n    def addTwoNumbers(self, l1: Optional[ListNode], l2: Optional[ListNode]) -> Optional[ListNode]:"
        elif "longest substring" in title_lower:
            return "class Solution:\n    def lengthOfLongestSubstring(self, s: str) -> int:"
        elif "longest valid parentheses" in title_lower or ("longest" in title_lower and "parenthes" in title_lower):
            return "class Solution:\n    def longestValidParentheses(self, s: str) -> int:"
        elif "median" in title_lower:
            return "class Solution:\n    def findMedianSortedArrays(self, nums1: List[int], nums2: List[int]) -> float:"
        elif "palindrom" in title_lower:
            return "class Solution:\n    def longestPalindrome(self, s: str) -> str:"
        elif "zigzag" in title_lower:
            return "class Solution:\n    def convert(self, s: str, numRows: int) -> str:"
        elif "reverse" in title_lower and "integer" in title_lower:
            return "class Solution:\n    def reverse(self, x: int) -> int:"
        elif "atoi" in title_lower:
            return "class Solution:\n    def myAtoi(self, s: str) -> int:"
        elif "regular expression" in title_lower:
            return "class Solution:\n    def isMatch(self, s: str, p: str) -> bool:"
        elif "container" in title_lower:
            return "class Solution:\n    def maxArea(self, height: List[int]) -> int:"
        elif "valid" in title_lower and "number" in title_lower:
            return "class Solution:\n    def isNumber(self, s: str) -> bool:"
        elif "subset" in title_lower:
            return "class Solution:\n    def subsets(self, nums: List[int]) -> List[List[int]]:"
        elif "roman" in title_lower:
            if "to" in title_lower:
                return "class Solution:\n    def romanToInt(self, s: str) -> int:"
            else:
                return "class Solution:\n    def intToRoman(self, num: int) -> str:"
        elif "valid parentheses" in title_lower:
            return "class Solution:\n    def isValid(self, s: str) -> bool:"
        elif "merge" in title_lower and "sorted" in title_lower:
            return "class Solution:\n    def merge(self, nums1: List[int], m: int, nums2: List[int], n: int) -> None:"
        elif "climbing stairs" in title_lower:
            return "class Solution:\n    def climbStairs(self, n: int) -> int:"
        else:
            # Generate based on problem title
            # Convert title to camelCase function name
            words = self.current_problem['title'].lower().split()
            func_name = words[0] + ''.join(word.capitalize() for word in words[1:])
            # Remove special characters
            func_name = ''.join(c for c in func_name if c.isalnum())
            return f"class Solution:\n    def {func_name}(self) -> None:"
    
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
            max_tokens=250,  # Increased from 150 to allow full problem descriptions
            temperature=0.7,
            top_p=0.9,
            echo=False,
            stop=["Human:", "User:", "Student:", "\nUser:", "\nHuman:", "\nStudent:", "\n\nStudent:", "\n\nUser:", "\n\nHuman:", "Student:", "User:", "Human:"]
        )
        
        # Extract response text and clean it up
        tutor_response = response['choices'][0]['text'].strip()
        
        # Additional cleaning to prevent the tutor from continuing its own conversation
        lines = tutor_response.split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if line.startswith(('Student:', 'User:', 'Human:', 'Tutor:')):
                break
            if line:
                cleaned_lines.append(line)
        
        tutor_response = '\n'.join(cleaned_lines).strip()
        
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
        
        context_parts.append("You are a patient and encouraging coding tutor. Your goal is to have natural conversations while guiding students through coding problems step-by-step.")
        context_parts.append("CRITICAL RULES:")
        context_parts.append("- ALWAYS respond directly to what the student just said")
        context_parts.append("- Be completely honest - if you can't see something, say so")
        context_parts.append("- You can only see code when the student submits it, not while they're typing")
        context_parts.append("- If they ask a question, answer that specific question")
        context_parts.append("- If they say they're stuck, ask ONE small question to help them think")
        context_parts.append("- Keep responses short and conversational (1-2 sentences max)")
        context_parts.append("- Ask only ONE question at a time, never multiple questions")
        context_parts.append("- Never give long explanations or multiple concepts at once")
        context_parts.append("- Be encouraging and celebrate any progress")
        context_parts.append("- When asked for the problem, share ONLY the problem statement")
        context_parts.append("")
        
        if self.current_problem:
            context_parts.append(f"Current Problem: {self.current_problem['title']}")
            context_parts.append("")
        
        recent_history = self.conversation_history[-10:]
        
        for msg in recent_history:
            if msg['role'] == 'user':
                context_parts.append(f"Student: {msg['content']}")
            elif msg['role'] == 'tutor':
                context_parts.append(f"Tutor: {msg['content']}")
        
        context_parts.append("")
        context_parts.append("Tutor:")
        
        return "\n".join(context_parts)
    
    def clear_session(self):
        """Clear the current session and start fresh"""
        self.conversation_history = []
        self.current_problem = None
        if os.path.exists(self.session_file):
            os.remove(self.session_file)
        print("Session cleared!")
    
    # Note to self, going to change this function soon. Instead of checking for a solution, I'll have the model overlook the current code and provide feedback.
    # This will allow for more interactive learning and guidance.

    def evaluate_code(self, code, language="python"):
        """Evaluate user's code attempt"""
        if not self.current_problem:
            return "No problem is currently loaded."
        
        # Add the code to conversation context for evaluation
        eval_prompt = f"""The student has submitted the following {language} code for the problem "{self.current_problem['title']}":

```{language}
{code}
```

As their tutor, analyze this code and provide feedback:
- Is it correct?
- Are there any issues or bugs?
- If it's not complete, what should they work on next?
- If it's correct, congratulate them and suggest improvements or optimizations

Be encouraging and provide specific, actionable feedback. Don't just give them the answer."""
        
        return self.chat(eval_prompt)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Initialize the tutor (this will take a moment)
print("Initializing AI Tutor...")
model_path = hf_hub_download(repo_id="TheBloke/WizardCoder-Python-13B-V1.0-GGUF", 
                            filename="wizardcoder-python-13b-v1.0.Q4_K_M.gguf")
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
        problem_request_keywords = ['new problem', 'different problem', 'array problem', 'string problem', 
                                  'tree problem', 'linked list problem', 'graph problem', 'dynamic programming',
                                  'sorting problem', 'binary search', 'two pointer', 'sliding window', 'hash problem',
                                  'stack problem', 'queue problem', 'random problem', 'give me a problem']
        
        is_problem_request = any(keyword in message_lower for keyword in problem_request_keywords)
        
        if is_problem_request and ('problem' in message_lower or 'question' in message_lower):
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
                'function_signature': problem_data['function_signature'],
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
        data = request.json or {}
        user_request = data.get('request', '')  # Optional user request for specific type
        
        if user_request.strip():
            # User requested a specific type of problem - let LLM choose
            response_data = get_requested_problem(user_request)
        else:
            # Get a random problem as before
            problem_index = random.randint(0, min(100, len(dataset["train"])-1))
            sample = dataset["train"][problem_index]
            
            response = tutor.set_problem(sample['title'], sample['content'])
            function_signature = tutor.get_function_signature(sample['content'])
            
            response_data = {
                'response': response,
                'problem': {
                    'title': sample['title'],
                    'description': sample['content']
                },
                'function_signature': function_signature,
                'conversation_history': tutor.conversation_history[-10:]
            }
        
        return jsonify(response_data)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def get_requested_problem(user_request):
    """Find and select a problem based on user's request"""
    try:
        # If no specific request or random request, pick any problem
        if not user_request.strip() or user_request.lower() in ['random', '']:
            problem_index = random.randint(0, min(100, len(dataset["train"])-1))
            selected_problem = dataset["train"][problem_index]
            tutor_message = "Here's a random problem for you to work on!"
        else:
            # Filter problems based on common keywords
            keywords = user_request.lower()
            filtered_problems = []
            
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
            
            if not filtered_problems:
                # Fallback to random problem if no matches found
                problem_index = random.randint(0, min(100, len(dataset["train"])-1))
                selected_problem = dataset["train"][problem_index]
                tutor_message = f"I couldn't find a specific problem matching '{user_request}', so I picked this random one for you!"
            else:
                # Randomly select from filtered problems
                selected_problem = random.choice(filtered_problems)
                tutor_message = f"Perfect! I found an {user_request} problem for you. Here's what we'll work on:"
        
        # Set the problem and get tutor response
        tutor.set_problem(selected_problem['title'], selected_problem['content'])
        
        # Override the tutor's response to acknowledge the specific request
        tutor.conversation_history[-1]['content'] = tutor_message
        
        function_signature = tutor.get_function_signature(selected_problem['content'])
        
        return {
            'response': tutor_message,
            'problem': {
                'title': selected_problem['title'],
                'description': selected_problem['content']
            },
            'function_signature': function_signature,
            'conversation_history': tutor.conversation_history[-10:]
        }
        
    except Exception as e:
        # Fallback to random problem on error
        problem_index = random.randint(0, min(100, len(dataset["train"])-1))
        sample = dataset["train"][problem_index]
        response = tutor.set_problem(sample['title'], sample['content'])
        function_signature = tutor.get_function_signature(sample['content'])
        
        return {
            'response': f"I had trouble finding that specific type, but here's a good problem to work on!",
            'problem': {
                'title': sample['title'],
                'description': sample['content']
            },
            'function_signature': function_signature,
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

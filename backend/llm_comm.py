from flask import Flask, request, jsonify
from flask_cors import CORS
from datasets import load_dataset, Dataset
from huggingface_hub import hf_hub_download
import torch
from llama_cpp import Llama
import json
import os
from datetime import datetime
import random
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
        has_previous_conversation = len([msg for msg in self.conversation_history if msg['role'] in ['user', 'assistant', 'tutor']]) > 0
        
        if has_previous_conversation:
            # Continuing session with new problem
            tutor_response = f"Great! Let's work on '{problem_title}'. I can see you have the problem description. Before we dive into coding, let's make sure we understand what we're being asked to do. Can you tell me in your own words what this problem is asking for? Let me know if you have any questions!"
        else:
            # First problem in session
            tutor_response = f"Hello! I'm Alex, your coding tutor. I see you're working on '{problem_title}'. Before we start coding, let's make sure we understand the problem. Can you read through the problem description and tell me what you think it's asking us to do? Let me know if you have any questions!"
        
        # Add the tutor response directly to history instead of generating it
        self.conversation_history.append({
            'role': 'tutor',
            'content': tutor_response,
            'timestamp': datetime.now().isoformat()
        })
        
        # Save session after adding the response
        self.save_session()
        
        return tutor_response
    
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
            max_tokens=1500,
            temperature=0.7,
            top_p=0.9,
            echo=False,
            stop=["Student:", "User:"]
        )
        
        # Extract response text and clean it up
        raw_response = response['choices'][0]['text'].strip()
        # Remove any leaked internal reasoning tags like <thought>...</thought>
        if '</thought>' in raw_response:
            # Keep only content after the closing thought tag
            raw_response = raw_response.split('</thought>', 1)[1].strip()
        # Strip any residual tags
        raw_response = re.sub(r'</?thought>', '', raw_response)
        raw_response = re.sub(r'</?response>', '', raw_response)

        tutor_response = self._clean_response(raw_response)
        
        # Add tutor response to history
        self.conversation_history.append({
            'role': 'tutor',
            'content': tutor_response,
            'timestamp': datetime.now().isoformat()
        })
        
        # Save session after each interaction
        self.save_session()
        
        return tutor_response
    
    def _clean_response(self, response):
        """Clean up the tutor response to remove stage directions and unwanted patterns"""
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
        context_parts.append("You are Alex, an expert coding tutor specializing in LeetCode problems, using the Socratic method.")
        context_parts.append("Your goal is to guide the user to a solution, providing hints and asking questions to foster discovery, but provide the solution with explanation and Python code if they explicitly give up or request it.")
        
        # LeetCode-Specific Guidance
        context_parts.append("For LeetCode problems, summarize key constraints (e.g., input size, edge cases) and guide the student to consider time and space complexity.")
        context_parts.append("Encourage exploration of algorithmic patterns (e.g., two-pointer, dynamic programming, greedy) when relevant.")
        context_parts.append("If the student submits code, analyze it for correctness, efficiency, and edge cases. Provide specific feedback and suggest improvements without rewriting unless requested.")
        
        # Communication Style
        context_parts.append("COMMUNICATION STYLE:")
        context_parts.append("- Be direct, honest, and natural. If you don't understand something, ask for clarification.")
        context_parts.append("- Maintain an encouraging tone, especially when the student is frustrated, and celebrate small wins.")
        
        # Tutoring Approach
        context_parts.append("TUTORING APPROACH:")
        context_parts.append("- Ask questions to guide student discovery.")
        context_parts.append("- Let students work through problems themselves, providing hints only when stuck.")
        context_parts.append("- If the student says they cannot complete the problem or know the, switch to concrete examples or simpler analogies.")
        context_parts.append("- If the student provides an incomplete problem description or switches problems, ask clarifying questions to confirm the context.")
        
        # Platform Integration
        context_parts.append("Format code in clear Python code blocks for display in the website's code editor.")
        context_parts.append("Suggest test cases the student can run to verify their solution.")
        context_parts.append("When relevant, suggest external resources (e.g., LeetCode problem URL, Python documentation).")
        
        # Never Do
        context_parts.append("NEVER DO:")
        context_parts.append("- Overuse conceptual questions when the student needs concrete examples.")
        context_parts.append("- Refuse to help when the student explicitly gives up.")
        context_parts.append("- Introduce tangential topics unrelated to the current problem.")
        
        # Problem and User Context
        if self.current_problem:
            context_parts.append(f"Current Problem: {self.current_problem['title']}")
            context_parts.append(f"Problem Constraints: {self.current_problem.get('constraints', 'Not specified')}")
            context_parts.append(f"Difficulty: {self.current_problem.get('difficulty', 'Not specified')}")
            context_parts.append("")

        history_limit = 10
        recent_history = self.conversation_history
        recent_history_wlimit = recent_history[-history_limit:]

        for msg in recent_history_wlimit:
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

# Load your enhanced LeetCode dataset from Hugging Face
print("Loading LeetCode dataset from Hugging Face...")
dataset = load_dataset("viccon23/leetcode")

print("Loaded, lets roll.")
print(f"Dataset contains {len(dataset['train'])} problems")

# Verify the problem_types column exists (Little debugging code)
# sample_problem = dataset['train'][0]
# print("Sample problem columns:", list(sample_problem.keys()))
# if 'problem_types' in sample_problem:
#     print(f"Sample problem types: {sample_problem['problem_types']}")
#     print("✅ Problem types column detected successfully!")
# else:
#     print("⚠️  Warning: problem_types column not found")

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
                'conversation_history': tutor.conversation_history,
                'current_problem': problem_data['problem'],
                'problem_changed': True  # Flag to indicate the problem changed
            })
        
        # Regular chat response
        response = tutor.chat(message)
        
        return jsonify({
            'response': response,
            'conversation_history': tutor.conversation_history,
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
                'conversation_history': tutor.conversation_history
            }
        
        return jsonify(response_data)
    
    except Exception as e:
        print(f"Error in new_problem: {str(e)}")  # Debug logging
        import traceback
        traceback.print_exc()  # Print full stack trace
        return jsonify({'error': str(e)}), 500

def get_requested_problem(user_request):
    """Find and select a problem based on user's request using AI-classified problem types"""
    try:
        print(f"Processing problem request: '{user_request}'")
        
        # If no specific request or random request, pick any problem
        if not user_request.strip() or user_request.lower() in ['random', '']:
            problem_index = random.randint(0, len(dataset["train"])-1)
            selected_problem = dataset["train"][problem_index]
            tutor_message = "Here's a random problem for you to work on!"
        else:
            # Map user requests to problem types
            keywords = user_request.lower()
            matching_types = []
            
            # Create mapping of user terms to actual problem types
            type_mappings = {
                'array': ['Array'],
                'string': ['String'],
                'tree': ['Tree', 'Binary Tree', 'Binary Search Tree'],
                'linked list': ['Linked List'],
                'graph': ['Graph', 'Depth-First Search', 'Breadth-First Search', 'Topological Sort'],
                'dynamic programming': ['Dynamic Programming'],
                'dp': ['Dynamic Programming'],
                'sorting': ['Sorting'],
                'binary search': ['Binary Search'],
                'two pointer': ['Two Pointers'],
                'sliding window': ['Sliding Window'],
                'hash': ['Hash Table', 'Hash Function'],
                'stack': ['Stack', 'Monotonic Stack'],
                'queue': ['Queue'],
                'heap': ['Heap'],
                'greedy': ['Greedy'],
                'math': ['Math', 'Number Theory'],
                'bit manipulation': ['Bit Manipulation', 'Bitmask'],
                'union find': ['Union Find'],
                'trie': ['Trie'],
                'segment tree': ['Segment Tree'],
                'matrix': ['Matrix'],
                'design': ['Design'],
                'simulation': ['Simulation'],
                'counting': ['Counting'],
                'prefix sum': ['Prefix Sum'],
                'geometry': ['Geometry']
            }
            
            # Find matching problem types
            for user_term, problem_types in type_mappings.items():
                if user_term in keywords:
                    matching_types.extend(problem_types)
            
            print(f"Matching problem types: {matching_types}")
            
            if matching_types:
                # Filter problems by matching types
                filtered_indices = []
                for i in range(len(dataset["train"])):
                    problem = dataset["train"][i]
                    problem_types_str = problem.get('problem_types', '')
                    
                    # Check if any of the matching types are in this problem's types
                    if any(ptype in problem_types_str for ptype in matching_types):
                        filtered_indices.append(i)
                
                print(f"Found {len(filtered_indices)} problems matching the criteria")
                
                if filtered_indices:
                    # Randomly select from filtered problems
                    selected_index = random.choice(filtered_indices)
                    selected_problem = dataset["train"][selected_index]
                    
                    # Get the actual matching types for this problem
                    actual_types = selected_problem.get('problem_types', '')
                    tutor_message = f"No problem, here's a {user_request} problem for you. Let me know if you have any questions!"
                else:
                    # Fallback to keyword search in title/content
                    return get_requested_problem_fallback(user_request)
            else:
                # Fallback to keyword search in title/content
                return get_requested_problem_fallback(user_request)
        
        print(f"Selected problem: {selected_problem['title']}")
        
        # Set the problem and get tutor response
        tutor.set_problem(selected_problem['title'], selected_problem['content'])
        
        # Override the tutor's response to acknowledge the specific request
        tutor.conversation_history[-1]['content'] = tutor_message
        
        return {
            'response': tutor_message,
            'problem': {
                'title': selected_problem['title'],
                'description': selected_problem['content'],
                'problem_types': selected_problem.get('problem_types', 'Not classified'),
                'difficulty': selected_problem.get('difficulty', 'Unknown')
            },
            'conversation_history': tutor.conversation_history
        }
        
    except Exception as e:
        print(f"Error in get_requested_problem: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Fallback to random problem on error
        return get_requested_problem_fallback(user_request)

def get_requested_problem_fallback(user_request):
    """Fallback function for problem selection using title/content search"""
    try:
        keywords = user_request.lower()
        filtered_problems = []
        
        # Search through problems for keywords in title/content
        for i in range(min(500, len(dataset["train"]))):  # Search more problems
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
               ('binary search' in keywords and ('binary search' in title_lower or 'binary search' in content_lower)):
                filtered_problems.append((i, problem))
        
        if filtered_problems:
            selected_index, selected_problem = random.choice(filtered_problems)
            tutor_message = f"I found a {user_request} problem for you using keyword search. Here's what we'll work on:"
        else:
            # Complete fallback to random
            problem_index = random.randint(0, min(100, len(dataset["train"])-1))
            selected_problem = dataset["train"][problem_index]
            tutor_message = f"I couldn't find a specific problem matching '{user_request}', so I picked this interesting one for you!"
        
        tutor.set_problem(selected_problem['title'], selected_problem['content'])
        tutor.conversation_history[-1]['content'] = tutor_message
        
        return {
            'response': tutor_message,
            'problem': {
                'title': selected_problem['title'],
                'description': selected_problem['content'],
                'problem_types': selected_problem.get('problem_types', 'Not classified'),
                'difficulty': selected_problem.get('difficulty', 'Unknown')
            },
            'conversation_history': tutor.conversation_history
        }
        
    except Exception as e:
        print(f"Error in fallback: {str(e)}")
        # Final fallback
        problem_index = random.randint(0, min(100, len(dataset["train"])-1))
        sample = dataset["train"][problem_index]
        response = tutor.set_problem(sample['title'], sample['content'])
        
        return {
            'response': "Here's a problem to work on!",
            'problem': {
                'title': sample['title'],
                'description': sample['content'],
                'problem_types': sample.get('problem_types', 'Not classified'),
                'difficulty': sample.get('difficulty', 'Unknown')
            },
            'conversation_history': tutor.conversation_history
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

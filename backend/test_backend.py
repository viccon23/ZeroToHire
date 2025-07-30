from flask import Flask, request, jsonify
from flask_cors import CORS
from datasets import load_dataset
import random

# Simplified backend for testing without LLAMA model
app = Flask(__name__)
CORS(app)

# Load LeetCode dataset
print("Loading dataset...")
dataset = load_dataset("greengerong/leetcode")
print(f"Dataset loaded! Train size: {len(dataset['train'])}")

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get current session status"""
    return jsonify({
        'current_problem': None,
        'conversation_history': [],
        'message_count': 0
    })

@app.route('/api/new-problem', methods=['POST'])
def new_problem():
    """Load a new random problem"""
    try:
        print("New problem request received")
        
        # Get a random problem
        problem_index = random.randint(0, min(100, len(dataset["train"])-1))
        sample = dataset["train"][problem_index]
        
        print(f"Selected problem: {sample['title']}")
        
        response_data = {
            'response': f"Here's a random problem: {sample['title']}",
            'problem': {
                'title': sample['title'],
                'description': sample['content']
            },
            'function_signature': f"class Solution:\n    def solve(self) -> None:\n        pass",
            'conversation_history': []
        }
        
        print("Returning response data")
        return jsonify(response_data)
    
    except Exception as e:
        print(f"Error in new_problem: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("Starting test backend...")
    app.run(debug=True, host='127.0.0.1', port=5001)
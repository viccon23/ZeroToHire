# ZeroToHire

ZeroToHire is an AI-powered coding tutor that provides an interactive way to practice LeetCode problems. Built with React and Flask, it uses a local Llama model specialized in coding to guide users through programming challenges step-by-step.

(This project is still under development. I have more features and things to tweak to have the LLM act more human-like, and to make the frontend and backend a more smooth experience. Just a heads up!)

## 🌟 Features

### Interactive AI Tutor
- **Personalized Guidance**: The AI tutor (Alex) provides hints and encouragement rather than direct solutions
- **Natural Conversations**: Ask questions, request specific problem types, or get help when stuck
- **Problem Selection**: Request problems by category ("give me an array problem") or ask for random challenges
- **Code Evaluation**: Submit your code for feedback and suggestions

### Smart Problem Management  
- **LeetCode Integration**: Curated dataset of real LeetCode problems
- **Function Signatures**: Automatically generates proper class Solution templates
- **Problem Filtering**: Search by data structures (arrays, trees, linked lists) or algorithms (dynamic programming, sorting, etc.)
- **Session Persistence**: Your conversation history and progress are saved

### Modern UI
- **Split-Panel Design**: Chat interface on the left, Monaco code editor on the right
- **Resizable Problem Descriptions**: Adjust the problem panel to your preference
- **Markdown Support**: Rich formatting for problem descriptions with syntax highlighting
- **Dark Theme**: Professional coding environment optimized for extended use

## 🚀 Technology Stack

### Frontend
- **React** - Component-based UI framework
- **Monaco Editor** - VS Code's editor for code editing
- **React Markdown** - Rich text rendering for problem descriptions
- **Custom CSS** - Responsive design with resizable panels

### Backend
- **Flask** - Python web framework with RESTful API
- **llama-cpp-python** - Local AI model inference with GPU acceleration
- **PyTorch CUDA** - GPU acceleration for faster response times
- **Hugging Face Dataset** - [LeetCode problem database](https://huggingface.co/datasets/greengerong/leetcode) A big thank you to greengerong for making this dataset and saving me from spending hours of making my own.

### AI Model
- **WizardCoder-Python-13B** - Specialized coding language model
- **Custom Prompt Engineering** - Tuned for patient, step-by-step tutoring
- **GPU Optimization** - This was configured for my local GPU, a 4070Ti, so please have this in consideration if you plan to clone and use. A more simpler model (7B) might be needed for less intense GPUs.

## 🎯 How It Works

1. **Start a Session**: The AI tutor introduces itself and offers problem categories
2. **Get Problems**: Request specific types ("array problems") or random challenges  
3. **Code Together**: Write solutions in the Monaco editor with proper function signatures
4. **Receive Guidance**: Get hints, feedback, and encouragement through natural conversation
5. **Learn Progressively**: Build skills through interactive problem-solving

## 🔧 Setup and Installation

### Prerequisites
- Python 3.8+
- Node.js 16+
- NVIDIA GPU with CUDA support (optional but recommended)

### Backend Setup
```bash
cd backend
pip install -r requirements.txt
python app.py
```

### Frontend Setup
```bash
cd frontend/coding-tutor-ui
npm install
npm start
```

The app will be available at `http://localhost:3000` with the backend running on `http://localhost:5000`.

## 💡 Example Interactions

- **"Give me an array problem"** → Gets a random array-based challenge
- **"I'm stuck on this approach"** → Provides hints without spoiling the solution
- **"Can you check my code?"** → Analyzes your implementation and gives feedback
- **"Show me the problem statement"** → Displays the full problem description
- **"Let's try something with trees"** → Switches to a tree-based problem


---

*This is a personal summer project focused on creating a more engaging way to practice algorithmic problem-solving with AI assistance.*

# ZeroToHire - AI Coding Tutor

ZeroToHire is an AI-powered coding tutor that provides an interactive way to practice LeetCode problems. Built with React and Flask, it uses a local huggingface model to guide users through programming challenges step-by-step.

I was inspired after watching Neetcode videos and thinking of how convenient it would be to have someone to guide me in the right direction to a solution when solving leetcode problems of my own.

## 🌟 Features

### Interactive AI Tutor
- **Personalized Guidance**: The tutor provides hints and encouragement rather than direct solutions
- **Natural Conversations**: Ask questions, request specific problem types, or get help when stuck
- **Code Evaluation**: Submit your code for feedback and suggestions
- **Automatic Code Context**: Toggle to automatically share your code with the AI for contextual feedback

### Real-time Experience
- **Streaming Responses**: Chat replies stream token-by-token over a persistent WebSocket connection so you can start reading guidance instantly.
- **Offline-safe Code Persistence**: Every keystroke is cached in `localStorage` (scoped per LeetCode problem) and synced to SQLite, so refreshes or crashes never nuke your work.

### Smart Problem Management  
- **LeetCode Integration**: Curated dataset of real LeetCode problems
- **Problem Filtering**: Search by difficulty, data structures, algorithms, and more
- **Session Persistence**: Your conversation history and progress are saved
- **Progress Tracking**: Mark problems as completed

### Modern UI
- **Split-Panel Design**: Chat interface on the left, Monaco code editor on the right
- **Monaco Editor**: VS Code's editor with syntax highlighting and auto-completion
- **Resizable Problem Descriptions**: Adjust the problem panel to your preference
- **Markdown Support**: Rich formatting for problem descriptions with code syntax highlighting
- **Dark Theme**: Professional coding environment optimized for extended use
- **Error Boundaries**: Graceful error handling with user-friendly messages

## 🚀 Technology Stack

### Frontend
- **React** - Component-based UI framework
- **Monaco Editor** - VS Code's editor for professional code editing
- **React Markdown** - Rich text rendering with code syntax highlighting
- **Axios** - HTTP client with interceptors for error handling
- **Custom CSS** - Responsive design with resizable panels

### Backend
- **Flask** - Python web framework with RESTful API
- **llama-cpp-python** - Local AI model inference with GPU acceleration
- **PyTorch CUDA** - GPU acceleration for faster response times
- **Hugging Face Dataset** - [LeetCode problem database](https://huggingface.co/datasets/greengerong/leetcode)
- **python-dotenv** - Environment variable management

### AI Model
- **Qwen/Qwen2.5-Coder-14B-Instruct-GGUF** - Specialized coding language model
- **Custom Prompt Engineering** - Tuned for patient, step-by-step tutoring
- **GPU Optimization** - Configured for NVIDIA GPUs (4070Ti tested)

## 🎯 How It Works

1. **Start a Session**: Browse problems or load your previous session
2. **Select a Problem**: Choose from the problem browser with filters
3. **Code Together**: Write solutions in the Monaco editor with proper function signatures
4. **Get Feedback**: Use "Get Code Review" or enable auto-context for continuous guidance
5. **Track Progress**: Mark problems as complete and continue learning

### Streaming & Persistence Pipeline

1. **WebSocket Handshake** – The React app opens `ws://<backend>/ws/chat` as soon as it mounts. Messages are serialized JSON payloads that mirror the REST body but stay on the socket.
2. **Token Streaming** – Flask + `flask-sock` push every token emitted by `llama_cpp` down the socket. The UI stitches them into an in-progress assistant bubble while the traditional REST response shape (`conversation_history`, `current_problem`) arrives as a `final` event.
3. **Graceful Fallbacks** – If the socket is unavailable, the UI automatically falls back to the existing `/api/chat` POST call so users never get stuck.
4. **Local Cache First** – Every problem gets a deterministic `localStorage` key. On load we hydrate from the browser cache, then silently reconcile with the server snapshot. Each edit rewrites the cache and a delayed autosave (30s after the last edit) still syncs to SQLite.
5. **Resilience** – Clearing chats or resetting problems also keeps the cache in sync, so what you see in Monaco always matches what survives a refresh.

## 🔧 Setup and Installation

### Prerequisites
- Python 3.8+
- Node.js 16+
- NVIDIA GPU with CUDA support (recommended but optional)

### Backend Setup

1. **Navigate to backend directory**
   ```bash
   cd backend
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv venv
   # Windows
   .\venv\Scripts\activate
   # Mac/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   # Copy the example env file
   cp .env.example .env
   # Edit .env to customize settings (optional)
   ```

5. **Run the backend**
   ```bash
   python llm_comm.py
   ```
   
   **Note**: The AI model (~8GB) will download on first run.

### Frontend Setup

1. **Navigate to frontend directory**
   ```bash
   cd frontend
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Configure environment**
   ```bash
   # Copy the example env file
   cp .env.example .env
   # Edit if backend runs on different port
   ```

4. **Run the frontend**
   ```bash
   npm start
   ```

The app will be available at `http://localhost:3000` with the backend on `http://127.0.0.1:5000`.

## ⚙️ Configuration

### Backend (`.env`)

```env
# Model Configuration
HUGGINGFACE_MODEL_REPO=Qwen/Qwen2.5-Coder-14B-Instruct-GGUF
MODEL_N_CTX=4096                    # Context window
MODEL_MAX_TOKENS=400                # Max response length
MODEL_TEMPERATURE=0.7               # Response creativity

# Server Configuration
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
FLASK_DEBUG=True

# CORS Configuration
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

### Frontend (`.env`)

```env
REACT_APP_API_URL=http://127.0.0.1:5000/api
REACT_APP_API_TIMEOUT=30000
REACT_APP_WS_URL=ws://127.0.0.1:5000/ws/chat # Optional override (auto-derived from API URL)
```

## 💡 Usage Tips

- **Auto Code Context**: Enable the toggle to automatically share your code with every message
- **Get Code Review**: Explicitly ask the AI to review your current code
- **Browse Problems**: Use filters to find problems by difficulty, type, or search term
- **Clear Chat**: Start fresh while keeping your selected problem
- **Mark Complete**: Track your progress by marking solved problems

## 🐛 Troubleshooting

### Backend Issues

**Model download is slow**
- First run downloads ~8GB model (one-time)
- Subsequent runs use cached model

**Out of memory**
- Reduce `MODEL_N_CTX` in `.env` (try 2048)
- Set `MODEL_N_GPU_LAYERS=0` for CPU-only mode

**Port conflicts**
- Change `FLASK_PORT` in backend `.env`
- Update `REACT_APP_API_URL` in frontend `.env`

### Frontend Issues

**Connection errors**
- Verify backend is running
- Check CORS settings in backend `.env`
- Confirm port numbers match

**Monaco Editor issues**
- Clear npm cache: `npm cache clean --force`
- Reinstall dependencies

## 🔮 Recent Improvements

**High Priority Features (✅ Implemented)**:
- ✅ Monaco Editor with syntax highlighting
- ✅ Automatic code context in chat messages
- ✅ Environment variable configuration
- ✅ Comprehensive error handling
- ✅ Error boundaries in React
- ✅ Better API error messages

**Realtime Upgrades (✅ Implemented)**:
- ✅ WebSocket streaming responses with graceful HTTP fallback
- ✅ Problem-scoped code persistence via `localStorage`

**Coming Soon**:
- Code execution with test cases
- State management improvements
- Migration to FastAPI

## 📄 Credits

- **LeetCode Dataset**: Based on [greengerong's dataset](https://huggingface.co/datasets/greengerong/leetcode) with modifications
- **AI Model**: Qwen/Qwen2.5-Coder from Hugging Face
- **Editor**: Monaco Editor from Microsoft

## 🤝 Contributing

This is a personal project, but contributions, suggestions, and bug reports are welcome!

---

*An interactive learning tool that makes algorithmic problem-solving more accessible with AI assistance. Runs entirely locally - your code never leaves your machine.*

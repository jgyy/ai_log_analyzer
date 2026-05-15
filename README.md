# 🤖 DevOps AI Log Analyzer (MVP)

## 🎯 Purpose
An AI-powered DevOps incident analysis system that ingests logs, identifies root causes, and generates structured mitigation plans. Designed for SREs, platform engineers, and DevOps teams to accelerate troubleshooting and incident response.

## 🏗 Architecture
[UI: Next.js] → (Paste/Upload Logs) → [Backend: FastAPI] → (Preprocess & Chunk) → [AI Engine] → (Structured JSON) → [UI Tabs]

- **Frontend**: Next.js 14 + Tailwind + Lucide Icons
- **Backend**: FastAPI + Pydantic validation + JWT Role Check
- **AI Layer**: Google Gemini 1.5 Flash (JSON schema enforced) + Extensible Model Router
- **Log Preprocessor**: Context-aware chunking, error sampling, deduplication
- **Output**: Strict Pydantic schema mapped to 3 exact UI tabs

## 🛠 Tech Stack
| Layer       | Tech                          |
|-------------|-------------------------------|
| Frontend    | Next.js 14, Tailwind, React   |
| Backend     | FastAPI, Pydantic, Uvicorn    |
| AI/ML       | Google Generative AI (Gemini) |
| Auth        | JWT Header-based (MVP)        |
| Infra       | Docker-ready, 16GB RAM compatible |

## 🚀 How to Use

### 1. Backend Setup
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export GEMINI_API_KEY="your-gemini-key"
export JWT_SECRET="your-secret"
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

Visit http://localhost:3000

### 3. Run Analysis
Paste logs or upload .log file
Select role (header-based for MVP)
Click Run Analysis
View structured results across 3 tabs

## Product Screenshots
### Home page
<img width="1261" height="744" alt="image" src="https://github.com/user-attachments/assets/af702089-d325-4a5b-8e22-a3dced4cac1d" />

### Analysis
<img width="1290" height="758" alt="image" src="https://github.com/user-attachments/assets/8c1c82ce-4730-41f1-b0e4-db651a7cef99" />

### Root cause identification
<img width="1266" height="749" alt="image" src="https://github.com/user-attachments/assets/a9e476f6-d280-4514-98dd-5cc5532d99b5" />

### Mitigation plan
<img width="1270" height="772" alt="image" src="https://github.com/user-attachments/assets/c6ae3e26-9485-417d-b790-c68a4e32334c" />


## 🔮 Extensibility Roadmap
Feature
Implementation Path
Local AI (16GB RAM)
Swap AIService to use ollama or vllm. Set model_name="llama3:8b" or mistral:7b
DB Integration
Add SQLAlchemy/PostgreSQL to store logs, results, user sessions
Solution Articles
Add /api/generate-docs that converts AnalysisResult → Markdown/Confluence
Simulations
Parse mitigation_plan → Generate Terraform/K8s manifests for safe practice labs
Real Auth
Replace header check with NextAuth + FastAPI python-jose JWT middleware
Multi-Domain
Add domain dropdown → dynamically inject domain-specific system prompts

## 📜 Security & Compliance
Logs are processed in-memory (no disk persistence in MVP)
AI output strictly validates against Pydantic schemas
Role-based access prevents unauthorized uploads
Ready for SOC2/ISO audit logging via middleware hooks

## 🐛 Troubleshooting
422 Unprocessable Entity: Check Pydantic schema alignment with Gemini JSON output
500 AI Analysis Failed: Verify GEMINI_API_KEY and network access to generativelanguage.googleapis.com
CORS Errors: Ensure allow_origins in main.py matches frontend URL

---

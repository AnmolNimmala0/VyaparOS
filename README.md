# VyaparOS
**AI-Native Business Operating System for Indian Retail**

VyaparOS simplifies everyday shop operations using voice and natural language (Hindi, Hinglish, & English). From voice-driven stock replenishment and inventory tracking to credit sales (*Udhaar*) and customer repayments (*Khata*), VyaparOS connects natural voice commands to atomic database transactions.

---

## ✨ Features

- **🎙️ Voice-First Shop Assistant**:
  - Powered by **Gnani Prisma STT** for accurate real-time transcription across Hindi, Hinglish, and English dialects.
  - **Live Speech Captions**: Real-time on-screen speech detection as the shopkeeper speaks.
  - **ChatGPT-Style Fluid Orb**: Buoyant, zero-g liquid water animations and glowing acoustic waves indicating idle, listening, and processing states.
  - **Hero Microphone & Audio File Upload**: Prominent one-tap recording interface along with direct audio file upload and drag-and-drop (.wav, .mp3, .m4a, .webm, .ogg, .flac).

- **🛡️ Safe, Operation-Aware Confirmations**:
  - All critical business mutations (stock adjustments, credit sales, cash sales, repayments) require explicit shopkeeper confirmation.
  - 3-column comparative view: **Current Balance/Stock** → **Proposed Change** → **Committed Result**.
  - Inline loading states to prevent duplicate submissions.

- **⚡ Live Dashboard & Atomic PostgreSQL Transactions**:
  - **Inventory Adjustments**: Automatically scrolls to affected products, renders animated quantity changes (`prev → next`), highlights the row with a pulsing blue glow, and displays real-time status badges.
  - **Customer Khata & Credit**: Tracks customer balances, outstanding credit, and repayments with atomic ledger movements.
  - **Real-Time Financial Metrics**: Daily revenue, cash collected, credit outstanding, and gross profit calculated directly from PostgreSQL.

---

## 🛠️ Architecture & Tech Stack

- **Frontend**:
  - Next.js (App Router, Turbopack)
  - TypeScript & Tailwind CSS
  - Web Audio API & Web Speech API integration
  - Figma-crafted Navy (`#0f172a`) & Crisp White design system

- **Backend**:
  - FastAPI (Python 3.12+)
  - SQLAlchemy 2.0 (Asyncpg)
  - PostgreSQL 16
  - FFmpeg for 16 kHz mono PCM WAV conversion

- **AI & Integrations**:
  - **Gnani.ai Prisma v3.0**: Production Speech-to-Text (`indic-auto` + Codemix) for Indian vernacular audio with retail keyword biasing.
  - **Gnani.ai Timbre v3.0**: Neural Text-to-Speech (`Shivani` voice @ 48 kHz) for natural Hindi & Indian English voice responses.
  - **LLM Intent Extraction**: Supports **Gnani.ai Evon v3.3** (OpenAI-compatible endpoint when configured via `EVON_BASE_URL`), with **Gemini** and **Groq** automatic failover.

> 📄 **Solution One-Pager**: See [PITCH.md](./PITCH.md) for a concise one-page overview of the problem, solution, architecture, and impact.

---

## 🚀 Getting Started

### Prerequisites
- Docker & Docker Compose
- Node.js 18+ & npm
- Python 3.11+
- FFmpeg (`brew install ffmpeg` on macOS)

### 1. Database Setup
```bash
cd backend
docker compose up -d
```

### 2. Backend Setup
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Fill in your API keys in .env (GNANI_API_KEY, GEMINI_API_KEY / GROQ_API_KEY, and optional EVON_BASE_URL / EVON_MODEL)

# Run database migrations
alembic upgrade head

# Seed the demo store, products, and customer credit ledger
python -m app.seed_demo

# Start API server
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 3. Frontend Setup
Open a new terminal window:
```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 🧪 Testing

Run backend logic and schema verification tests:
```bash
cd backend
source .venv/bin/activate
pytest app/tests/test_core_logic.py -v
```



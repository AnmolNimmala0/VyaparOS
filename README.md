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
  - **Gnani Prisma v3**: Production speech-to-text for Indian vernacular audio.
  - **Gemini / Groq LLMs**: Dual-engine intent classification, entity resolution, and parameter extraction with automatic sub-second failover.

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
docker-compose up -d
```

### 2. Backend Setup
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Fill in your database URL and API keys in .env

# Run database migrations
alembic upgrade head

# Start API server
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 3. Frontend Setup
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
pytest
```

---

## 📄 License
MIT License. Built for India's small businesses.


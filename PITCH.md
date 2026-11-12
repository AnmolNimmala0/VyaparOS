# VyaparOS — One-Page Solution Pitch

**Voice-First AI Operating System for Indian Retail**

---

## 1. The Problem
India’s retail backbone consists of over **60 million Kirana stores and micro-merchants**, yet ~85% still run on paper notebooks (*Bahi-Khata*) or memory. Traditional POS and ERP software is built for desktop-trained accountants—requiring English fluency, typing, barcode scanning, and multi-step forms. Behind a busy, noisy shop counter, a merchant cannot pause a queue of customers to manually log stock arrivals or calculate partial credit (*udhaar*). As a result, **stockouts go unnoticed, customer credit is forgotten or disputed, and daily margins remain invisible**.

---

## 2. The Solution
**VyaparOS** turns natural, everyday shopkeeper speech (**Hindi, Hinglish, or English**) into real-time, ACID-compliant business operations—with zero typing required.

- **Speak Naturally**: Ask *"Maggi ka stock kitna hai?"* or say *"Aaj supplier se Maggi ke 10 packets aaye hain, add kar do"* or *"We sold 20 packets of Maggi in cash."*
- **Human-in-the-Loop Safety**: Instead of letting an LLM mutate financial records blindly, VyaparOS presents an **Operation Confirmation Card** comparing **Current State → Proposed Change → Resulting State**.
- **Atomic Execution & Live UI**: On confirmation, PostgreSQL commits the transaction with row-level locks and an immutable audit log, automatically highlighting and animating the updated row on the dashboard.
- **Full-Duplex Voice Reply**: Replies aloud in the exact language the shopkeeper used.

---

## 3. Architecture & Model Stack
1. **Audio Conditioning (FFmpeg DSP)**: Applies dynamic loudness normalization (`dynaudnorm`) and converts any uploaded or recorded audio (`.mp3`, `.m4a`, `.wav`, `.webm`, `.ogg`) into 16 kHz mono PCM WAV.
2. **Speech-to-Text — Gnani.ai Prisma v3.0 (`indic-auto` + Codemix)**: Purpose-built for Indian accents and Hindi–English code-mixing, enhanced with retail keyword biasing (`stock`, `rate`, `udhaar`, `bikri`, `vasooli`).
3. **Intent & Semantic Extraction — Gnani.ai Evon v3.3 / Gemini / Groq**: Extracts strict schema-validated JSON actions (`record_sale`, `record_credit_sale`, `record_credit_repayment`, `adjust_inventory`, `check_inventory`, `get_daily_summary`) with zero-hallucination guardrails. Supports **Gnani Evon v3.3** (`EVON_BASE_URL`) as primary OpenAI-compatible provider with sub-second Gemini/Groq failover.
4. **Deterministic Ledger Engine (FastAPI + PostgreSQL)**: Resolves vernacular product/customer names via fuzzy matching, enforces stock and credit rules, and executes two-phase locked transactions.
5. **Voice Synthesis — Gnani.ai Timbre v3.0 (`Shivani` @ 48 kHz)**: Speaks responses back in natural, conversational Hindi or Indian English.

---

## 4. Why VyaparOS Wins
- **Zero Learning Curve**: If a shopkeeper can speak on WhatsApp, they can run VyaparOS.
- **100% Accounting Integrity**: LLMs parse intent; deterministic ACID SQL handles the money.
- **Built for Bharat**: Native Hinglish support, WhatsApp-style audio file upload, and instant spoken confirmations.

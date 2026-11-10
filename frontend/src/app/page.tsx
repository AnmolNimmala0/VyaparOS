"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";

const API = "/api/v1";

type Summary = {
  date: string;
  transaction_count: number;
  revenue_paise: number;
  collected_paise: number;
  outstanding_paise: number;
  cost_of_goods_sold_paise: number;
  gross_profit_paise: number;
};

type InventoryItem = {
  product_id: string;
  product_name: string;
  sku: string | null;
  unit: string;
  quantity: number;
  reorder_level: number;
  is_low_stock: boolean;
};

type Customer = {
  id: string;
  name: string;
  phone: string | null;
  is_active: boolean;
};

type CreditCustomer = {
  customer_id: string;
  customer_name: string;
  outstanding_paise: number;
};

type OperationPlanData = {
  operation_type?: string;
  product_id?: string;
  product_name?: string;
  unit?: string;
  quantity_delta?: number;
  previous_quantity?: number;
  new_quantity?: number;
  adjustment_direction?: "ADD" | "REMOVE";
  customer_id?: string | null;
  customer_name?: string | null;
  items?: Array<{
    product_id: string;
    product_name: string;
    quantity: number;
    unit_price_paise: number;
    line_total_paise: number;
  }>;
  total_amount_paise?: number;
  amount_paid_paise?: number;
  amount_due_paise?: number;
  amount_paise?: number;
  payment_method?: string | null;
  previous_outstanding_paise?: number;
  new_outstanding_paise?: number;
  previous_customer_balance_paise?: number | null;
  new_customer_balance_paise?: number | null;
  confirmation_message?: string;
};

type PendingOp = {
  id: string;
  operation_type?: string;
  confirmation_message?: string;
  status?: string;
  payload?: OperationPlanData;
};

type VoiceResult = {
  status: string;
  message: string;
  transcript: string;
  detected_language?: string | null;
  conversation_id: string;
  pending_operation?: PendingOp | null;
  operation_plan?: OperationPlanData | null;
  data?: Record<string, unknown> | null;
  clarification_questions?: string[];
};

function money(paise: number | undefined) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format((paise ?? 0) / 100);
}

function quantity(value: number) {
  return Number(value).toLocaleString("en-IN", {
    maximumFractionDigits: 2,
  });
}

function subscribeToDate() {
  return () => { };
}

function getClientDate() {
  return new Intl.DateTimeFormat("en-IN", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(new Date());
}

function getServerDate() {
  return "";
}

export default function Home() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [credit, setCredit] = useState<CreditCustomer[]>([]);
  const [totalCredit, setTotalCredit] = useState(0);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [activeView, setActiveView] = useState("Overview");

  // Voice & Chat Assistant States
  const [recording, setRecording] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [voiceResult, setVoiceResult] = useState<VoiceResult | null>(null);
  const [voiceError, setVoiceError] = useState("");
  const [commandText, setCommandText] = useState("");
  const [operationLoading, setOperationLoading] = useState(false);
  const [liveCaption, setLiveCaption] = useState("");
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);

  const speakMessage = useCallback((text: string, lang?: string | null) => {
    if (!text || typeof window === "undefined") return;

    // Stop any existing playback
    if (audioPlayerRef.current) {
      audioPlayerRef.current.pause();
      audioPlayerRef.current = null;
    }
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }

    setIsSpeaking(true);

    // 1. Primary: Gnani Timbre v3.0 Neural Voice
    fetch(`${API}/voice/speak`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text,
        language: lang === "hi" ? "hi" : "en",
        voice: "Devansh",
      }),
    })
      .then(async (res) => {
        if (!res.ok) throw new Error("Timbre TTS synthesis error");
        const blob = await res.blob();
        const audioUrl = URL.createObjectURL(blob);
        const audio = new Audio(audioUrl);
        audioPlayerRef.current = audio;

        audio.onended = () => {
          setIsSpeaking(false);
          URL.revokeObjectURL(audioUrl);
        };
        audio.onerror = () => {
          setIsSpeaking(false);
          URL.revokeObjectURL(audioUrl);
        };

        await audio.play();
      })
      .catch(() => {
        // 2. Client-side fallback: Web Speech Synthesis
        if (!("speechSynthesis" in window)) {
          setIsSpeaking(false);
          return;
        }

        const utterance = new SpeechSynthesisUtterance(text);
        const isHindi = lang === "hi";
        utterance.lang = isHindi ? "hi-IN" : "en-IN";
        utterance.rate = 1.0;
        utterance.pitch = 1.0;

        const voices = window.speechSynthesis.getVoices();
        const matchedVoice = voices.find((v) =>
          isHindi
            ? v.lang.startsWith("hi")
            : v.lang.startsWith("en-IN") ||
              v.lang.startsWith("en-GB") ||
              v.lang.startsWith("en")
        );
        if (matchedVoice) {
          utterance.voice = matchedVoice;
        }

        utterance.onstart = () => setIsSpeaking(true);
        utterance.onend = () => setIsSpeaking(false);
        utterance.onerror = () => setIsSpeaking(false);

        window.speechSynthesis.speak(utterance);
      });
  }, []);

  // Live Highlight & Operation-Aware Feedback
  const [highlightedId, setHighlightedId] = useState<string | null>(null);
  const [animatingChange, setAnimatingChange] = useState<{
    productId: string;
    prev: string;
    next: string;
  } | null>(null);
  const [toast, setToast] = useState<{ title: string; message: string } | null>(
    null
  );

  const today = useSyncExternalStore(
    subscribeToDate,
    getClientDate,
    getServerDate
  );

  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const speechRecognitionRef = useRef<any>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const loadDashboard = useCallback(async () => {
    setError("");

    try {
      const responses = await Promise.all([
        fetch(`${API}/dashboard/summary`),
        fetch(`${API}/dashboard/credit`),
        fetch(`${API}/inventory?limit=100&offset=0`),
        fetch(`${API}/customers`),
      ]);

      const failed = responses.find((response) => !response.ok);
      if (failed) {
        throw new Error(`Backend returned HTTP ${failed.status}`);
      }

      const [summaryData, creditData, inventoryData, customerData] =
        await Promise.all(responses.map((response) => response.json()));

      setSummary(summaryData);
      setTotalCredit(creditData.total_outstanding_paise ?? 0);
      setCredit(creditData.customers ?? []);
      setInventory(inventoryData);
      setCustomers(customerData);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to connect to the backend."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void Promise.resolve().then(() => loadDashboard());
  }, [loadDashboard]);

  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  const sendRecording = async (audio: Blob) => {
    setProcessing(true);
    setVoiceError("");

    try {
      const form = new FormData();
      const extension = audio.type.includes("mp4") ? "mp4" : "webm";

      form.append("audio", audio, `vyapar-recording.${extension}`);

      if (conversationId) {
        form.append("conversation_id", conversationId);
      }

      const response = await fetch(`${API}/voice/process`, {
        method: "POST",
        body: form,
      });

      let result;

      try {
        result = await response.clone().json();
      } catch {
        const errorText = await response.text();

        throw new Error(
          errorText || `Server returned an invalid response (${response.status}).`
        );
      }

      if (!response.ok) {
        throw new Error(
          typeof result.detail === "string"
            ? result.detail
            : "Voice processing failed. Please try again."
        );
      }

      setVoiceResult(result);
      if (result.conversation_id) {
        setConversationId(result.conversation_id);
      }
      if (result.message) {
        speakMessage(result.message, result.detected_language);
      }

      if (
        result.status === "READ_ONLY_SUCCESS" ||
        result.status === "AWAITING_CONFIRMATION"
      ) {
        void loadDashboard();
      }
    } catch (err) {
      setVoiceError(
        err instanceof Error ? err.message : "Something went wrong."
      );
    } finally {
      setProcessing(false);
    }
  };

  const uploadAudioFile = async (file: File) => {
    if (!file || processing || operationLoading) return;

    setProcessing(true);
    setVoiceError("");
    setVoiceResult(null);
    setUploadedFileName(file.name);

    try {
      const form = new FormData();
      form.append("audio", file, file.name);

      if (conversationId) {
        form.append("conversation_id", conversationId);
      }

      const response = await fetch(`${API}/voice/process`, {
        method: "POST",
        body: form,
      });

      let result;

      try {
        result = await response.clone().json();
      } catch {
        const errorText = await response.text();

        throw new Error(
          errorText ||
            `Server returned an invalid response (${response.status}).`
        );
      }

      if (!response.ok) {
        throw new Error(
          typeof result.detail === "string"
            ? result.detail
            : "Voice processing failed. Please try again."
        );
      }

      setVoiceResult(result);
      if (result.conversation_id) {
        setConversationId(result.conversation_id);
      }
      if (result.message) {
        speakMessage(result.message, result.detected_language);
      }

      if (
        result.status === "READ_ONLY_SUCCESS" ||
        result.status === "AWAITING_CONFIRMATION"
      ) {
        void loadDashboard();
      }
    } catch (err) {
      setVoiceError(
        err instanceof Error ? err.message : "Something went wrong."
      );
    } finally {
      setProcessing(false);
      setUploadedFileName(null);
    }
  };

  const runCommandString = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || processing || operationLoading) return;

    setProcessing(true);
    setVoiceError("");

    try {
      const response = await fetch(`${API}/voice/process-text`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: trimmed,
          conversation_id: conversationId,
        }),
      });

      let result;

      try {
        result = await response.clone().json();
      } catch {
        const errorText = await response.text();

        throw new Error(
          errorText || `Server returned an invalid response (${response.status}).`
        );
      }

      if (!response.ok) {
        throw new Error(
          typeof result.detail === "string"
            ? result.detail
            : "Unable to process your command."
        );
      }

      setVoiceResult(result);

      if (result.conversation_id) {
        setConversationId(result.conversation_id);
      }

      if (result.message) {
        speakMessage(result.message, result.detected_language);
      }

      setCommandText("");

      if (result.status === "READ_ONLY_SUCCESS") {
        await loadDashboard();
      }
    } catch (err) {
      setVoiceError(
        err instanceof Error ? err.message : "Something went wrong."
      );
    } finally {
      setProcessing(false);
    }
  };

  const sendTextCommand = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await runCommandString(commandText);
  };

  const startRecording = async () => {
    setVoiceError("");
    setLiveCaption("");

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true,
      });

      streamRef.current = stream;

      const mimeType = [
        "audio/webm;codecs=opus",
        "audio/webm",
        "audio/mp4",
      ].find((type) => MediaRecorder.isTypeSupported(type));

      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);

      chunksRef.current = [];

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      recorder.onstop = () => {
        const audio = new Blob(chunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });

        stream.getTracks().forEach((track) => track.stop());
        streamRef.current = null;

        if (audio.size > 0) {
          void sendRecording(audio);
        } else {
          setVoiceError("No audio was captured. Please try again.");
        }
      };

      recorderRef.current = recorder;
      recorder.start();
      setRecording(true);

      // Web Speech API for real-time live captions while speaking
      try {
        const SpeechRecognition =
          (window as any).SpeechRecognition ||
          (window as any).webkitSpeechRecognition;

        if (SpeechRecognition) {
          const recognition = new SpeechRecognition();
          recognition.continuous = true;
          recognition.interimResults = true;
          recognition.lang = "hi-IN";

          recognition.onresult = (event: any) => {
            let interim = "";
            for (let i = event.resultIndex; i < event.results.length; i++) {
              interim += event.results[i][0].transcript;
            }
            if (interim) {
              setLiveCaption(interim);
            }
          };

          recognition.onerror = () => {
            // Non-fatal: MediaRecorder will still send audio to Gnani Prisma STT
          };

          recognition.start();
          speechRecognitionRef.current = recognition;
        }
      } catch {
        // Fallback silently if browser doesn't permit SpeechRecognition
      }
    } catch {
      setVoiceError(
        "Microphone access failed. Please allow microphone permission in your browser."
      );
    }
  };

  const stopRecording = () => {
    const recorder = recorderRef.current;

    if (recorder && recorder.state !== "inactive") {
      recorder.stop();
    }

    if (speechRecognitionRef.current) {
      try {
        speechRecognitionRef.current.stop();
      } catch {
        // ignore
      }
      speechRecognitionRef.current = null;
    }

    setRecording(false);
  };

  const confirmOperation = async () => {
    const operationId = voiceResult?.pending_operation?.id;
    if (!operationId || operationLoading) return;

    setOperationLoading(true);
    setVoiceError("");

    try {
      // 1. Confirm operation
      const confirmResponse = await fetch(
        `${API}/operations/${operationId}/confirm`,
        { method: "POST" }
      );

      const confirmed = await confirmResponse.json();

      if (!confirmResponse.ok || confirmed.status !== "CONFIRMED") {
        throw new Error(
          confirmed.detail || "The operation could not be confirmed."
        );
      }

      // 2. Execute operation
      const executeResponse = await fetch(
        `${API}/operations/${operationId}/execute`,
        { method: "POST" }
      );

      const executed = await executeResponse.json();

      if (!executeResponse.ok || executed.status !== "COMPLETED") {
        throw new Error(
          executed.detail || "The operation could not be completed."
        );
      }

      // Extract plan for the operation-aware post-execution experience
      const plan: OperationPlanData | undefined =
        voiceResult.operation_plan ||
        voiceResult.pending_operation?.payload;

      setVoiceResult((previous) =>
        previous
          ? {
            ...previous,
            status: "COMPLETED",
            message: "Done! Shop records have been updated.",
            pending_operation: null,
          }
          : previous
      );

      // Refresh database records from PostgreSQL
      await loadDashboard();

      // 3. Operation-aware auto-navigation, scrolling, animated changes, & toast
      if (plan?.operation_type === "INVENTORY_ADJUSTMENT" && plan.product_id) {
        const prodId = plan.product_id;
        setActiveView("Inventory");
        setHighlightedId(prodId);
        setAnimatingChange({
          productId: prodId,
          prev: String(plan.previous_quantity ?? ""),
          next: String(plan.new_quantity ?? ""),
        });
        setToast({
          title: "Stock updated successfully",
          message: `${plan.product_name}: ${plan.previous_quantity} → ${plan.new_quantity} ${plan.unit || "pkts"}`,
        });

        // Smooth scroll to product row
        setTimeout(() => {
          const el = document.getElementById(`product-row-${prodId}`);
          el?.scrollIntoView({ behavior: "smooth", block: "center" });
        }, 150);

        setTimeout(() => {
          setHighlightedId(null);
          setAnimatingChange(null);
        }, 4500);
        setTimeout(() => {
          setToast(null);
        }, 4500);
      } else if (plan?.operation_type === "SALE") {
        if (plan.customer_id && (plan.amount_due_paise ?? 0) > 0) {
          const custId = plan.customer_id;
          setActiveView("Customers");
          setHighlightedId(custId);
          setToast({
            title: "Credit Sale Recorded",
            message: `${plan.customer_name}: ₹${((plan.amount_due_paise ?? 0) / 100).toFixed(2)} due`,
          });

          setTimeout(() => {
            const el = document.getElementById(`customer-row-${custId}`);
            el?.scrollIntoView({ behavior: "smooth", block: "center" });
          }, 150);

          setTimeout(() => {
            setHighlightedId(null);
          }, 4500);
          setTimeout(() => {
            setToast(null);
          }, 4500);
        } else {
          setActiveView("Sales");
          setToast({
            title: "Sale Completed",
            message: `Total ${money(plan.total_amount_paise)} (${plan.payment_method || "CASH"})`,
          });
          setTimeout(() => {
            setToast(null);
          }, 4500);
        }
      } else if (plan?.operation_type === "REPAYMENT") {
        setActiveView("Customers");
        if (plan.customer_id) {
          const custId = plan.customer_id;
          setHighlightedId(custId);
          setTimeout(() => {
            const el = document.getElementById(`customer-row-${custId}`);
            el?.scrollIntoView({ behavior: "smooth", block: "center" });
          }, 150);
          setTimeout(() => {
            setHighlightedId(null);
          }, 4500);
        }
        setToast({
          title: "Repayment Received",
          message: `${money(plan.amount_paise)} received from ${plan.customer_name}`,
        });
        setTimeout(() => {
          setToast(null);
        }, 4500);
      }
    } catch (err) {
      setVoiceError(
        err instanceof Error ? err.message : "Unable to complete operation."
      );
    } finally {
      setOperationLoading(false);
    }
  };

  const cancelOperation = async () => {
    const operationId = voiceResult?.pending_operation?.id;
    if (!operationId || operationLoading) return;

    setOperationLoading(true);

    try {
      const response = await fetch(
        `${API}/operations/${operationId}/cancel`,
        { method: "POST" }
      );

      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.detail || "Unable to cancel operation.");
      }

      setVoiceResult((previous) =>
        previous
          ? {
            ...previous,
            status: "CANCELLED",
            message: "Okay, I cancelled that operation.",
            pending_operation: null,
          }
          : previous
      );
    } catch (err) {
      setVoiceError(
        err instanceof Error ? err.message : "Unable to cancel operation."
      );
    } finally {
      setOperationLoading(false);
    }
  };

  const filteredInventory = inventory.filter((item) =>
    `${item.product_name} ${item.sku ?? ""}`
      .toLowerCase()
      .includes(search.toLowerCase())
  );

  const filteredCustomers = customers.filter((customer) =>
    `${customer.name} ${customer.phone ?? ""}`
      .toLowerCase()
      .includes(search.toLowerCase())
  );

  const lowStockCount = inventory.filter((item) => item.is_low_stock).length;

  const navItems = [
    { name: "Overview", icon: "◫" },
    { name: "Inventory", icon: "▤" },
    { name: "Customers", icon: "♙" },
    { name: "Sales", icon: "↗" },
  ];

  return (
    <main className="app-shell">
      {/* Toast Notification */}
      {toast && (
        <div className="toast-container">
          <div className="toast-card">
            <div className="toast-icon">✓</div>
            <div className="toast-content">
              <strong>{toast.title}</strong>
              <span>{toast.message}</span>
            </div>
            <button
              className="toast-dismiss"
              onClick={() => setToast(null)}
              aria-label="Dismiss toast"
            >
              ✕
            </button>
          </div>
        </div>
      )}

      {/* LEFT SIDEBAR */}
      <aside className="left-sidebar">
        <div className="brand">
          <div className="brand-mark">V</div>
          <div>
            <div className="brand-name">
              vyapar<span>OS</span>
            </div>
            <div className="brand-caption">BUSINESS OPERATING SYSTEM</div>
          </div>
        </div>

        <div className="store-switcher">
          <div className="store-avatar">S</div>
          <div className="store-details">
            <strong>Sharma General Store</strong>
            <span>Retail & Kirana</span>
          </div>
          <span className="switch-arrow">⌄</span>
        </div>

        <div className="nav-label">WORKSPACE</div>
        <nav className="navigation">
          {navItems.map((item) => (
            <button
              key={item.name}
              className={`nav-item ${activeView === item.name ? "active" : ""}`}
              onClick={() => {
                setActiveView(item.name);
                setSearch("");
              }}
            >
              <span className="nav-icon">{item.icon}</span>
              {item.name}
              {item.name === "Inventory" && lowStockCount > 0 && (
                <span className="nav-count">{lowStockCount}</span>
              )}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="sidebar-tip">
            <div className="tip-icon">✦</div>
            <strong>Fast Shop Automation</strong>
            <p>Speak or type commands naturally. Updates reflect in real time.</p>
          </div>
          <div className="profile">
            <div className="profile-avatar">A</div>
            <div>
              <strong>Shopkeeper</strong>
              <span>Demo Account</span>
            </div>
            <span className="profile-menu">•••</span>
          </div>
        </div>
      </aside>

      {/* WORKSPACE CENTER */}
      <section className="workspace">
        <header className="topbar">
          <div>
            <div className="breadcrumb">Workspace / {activeView}</div>
            <h1>
              {activeView === "Overview" ? "Shop Dashboard" : activeView}
            </h1>
            <p className="date-line">{today}</p>
          </div>
          <div className="topbar-actions">
            <div className="live-status">
              <span className="status-dot" /> Live Store
            </div>
            <button
              className="refresh-button"
              onClick={() => void loadDashboard()}
            >
              ↻ <span>Refresh</span>
            </button>
          </div>
        </header>

        {error && (
          <div className="error-banner">
            <strong>Backend connection issue:</strong> {error}
            <button onClick={() => void loadDashboard()}>Retry</button>
          </div>
        )}

        {loading ? (
          <div className="loading-state">
            <div className="loader loader-dark" />
            <p>Loading shop records...</p>
          </div>
        ) : (
          <>
            {(activeView === "Overview" || activeView === "Sales") && (
              <>
                <section className="section-heading">
                  <div>
                    <h2>
                      {activeView === "Sales"
                        ? "Sales Activity"
                        : "Today's Business Summary"}
                    </h2>
                    <p>Live metrics calculated directly from PostgreSQL</p>
                  </div>
                  <span className="date-chip">● Live Database</span>
                </section>

                <section className="metrics-grid">
                  <Metric
                    label="Today's revenue"
                    value={money(summary?.revenue_paise)}
                    detail={`${summary?.transaction_count ?? 0} transactions`}
                    icon="↗"
                  />
                  <Metric
                    label="Cash collected"
                    value={money(summary?.collected_paise)}
                    detail="Realized cash flow"
                    icon="₹"
                  />
                  <Metric
                    label="Credit outstanding"
                    value={money(totalCredit)}
                    detail="Customer balance (Udhaar)"
                    icon="◷"
                  />
                  <Metric
                    label="Gross profit"
                    value={money(summary?.gross_profit_paise)}
                    detail={`COGS ${money(summary?.cost_of_goods_sold_paise)}`}
                    icon="✦"
                  />
                </section>

                <section className="overview-grid">
                  <div className="panel inventory-panel">
                    <div className="panel-heading">
                      <div>
                        <h3>Inventory snapshot</h3>
                        <p>Latest products in stock</p>
                      </div>
                      <button
                        className="text-button"
                        onClick={() => setActiveView("Inventory")}
                      >
                        View all inventory →
                      </button>
                    </div>
                    <InventoryTable
                      items={inventory.slice(0, 6)}
                      highlightedId={highlightedId}
                      animatingChange={animatingChange}
                    />
                  </div>

                  <div className="panel quick-panel">
                    <div className="panel-heading">
                      <div>
                        <h3>Shop health</h3>
                        <p>Key operational indicators</p>
                      </div>
                      <span className="health-icon">✦</span>
                    </div>
                    <div className="health-row">
                      <div className="health-symbol">▤</div>
                      <div className="health-copy">
                        <strong>{inventory.length} products</strong>
                        <span>Active in inventory</span>
                      </div>
                    </div>
                    <div className="health-row">
                      <div className="health-symbol warning-symbol">!</div>
                      <div className="health-copy">
                        <strong>{lowStockCount} low-stock items</strong>
                        <span>Need replenishment</span>
                      </div>
                    </div>
                    <div className="health-row">
                      <div className="health-symbol">♙</div>
                      <div className="health-copy">
                        <strong>{customers.length} customers</strong>
                        <span>Registered accounts</span>
                      </div>
                    </div>
                    <div className="health-footer">
                      <span>Total customer credit</span>
                      <strong>{money(totalCredit)}</strong>
                    </div>
                  </div>
                </section>

                <section className="panel credit-panel">
                  <div className="panel-heading">
                    <div>
                      <h3>Customer credit summary</h3>
                      <p>Customers with pending balances (Khata)</p>
                    </div>
                    <button
                      className="text-button"
                      onClick={() => setActiveView("Customers")}
                    >
                      Manage customers →
                    </button>
                  </div>
                  <CustomerTable
                    customers={credit
                      .filter((customer) => customer.outstanding_paise > 0)
                      .slice(0, 5)}
                    highlightedId={highlightedId}
                  />
                </section>
              </>
            )}

            {activeView === "Inventory" && (
              <section className="panel full-panel">
                <div className="panel-heading">
                  <div>
                    <h3>Inventory Catalog</h3>
                    <p>{inventory.length} products recorded in PostgreSQL</p>
                  </div>
                  <span className="date-chip">{lowStockCount} low stock</span>
                </div>
                <input
                  className="search-input"
                  placeholder="Search products by name or SKU..."
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                />
                <InventoryTable
                  items={filteredInventory}
                  highlightedId={highlightedId}
                  animatingChange={animatingChange}
                />
              </section>
            )}

            {activeView === "Customers" && (
              <section className="panel full-panel">
                <div className="panel-heading">
                  <div>
                    <h3>Customer Directory</h3>
                    <p>{customers.length} registered customers</p>
                  </div>
                  <span className="date-chip">
                    Total Credit: {money(totalCredit)}
                  </span>
                </div>
                <input
                  className="search-input"
                  placeholder="Search customers by name or phone..."
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                />
                <CustomerDirectory
                  customers={filteredCustomers}
                  credit={credit}
                  highlightedId={highlightedId}
                />
              </section>
            )}
          </>
        )}

        <footer className="workspace-footer">
          <span>VyaparOS</span>
          <span>Designed for modern Indian businesses.</span>
        </footer>
      </section>

      {/* FIGMA-GRADE AI ASSISTANT PANEL */}
      <aside className="assistant-panel">
        {/* Assistant Header */}
        <div className="assistant-header">
          <div className="assistant-title-group">
            <div className="assistant-avatar-badge">V</div>
            <div>
              <h2>Vyapar<span>AI</span></h2>
              <p>Voice & text assistant</p>
            </div>
          </div>
          <div className="assistant-online-badge">
            <span className="online-pulse-dot" /> Online
          </div>
        </div>

        {/* Fluid Water Orb Indicator Strip (ChatGPT Voice Style) */}
        <div className="orb-compact-strip">
          <div className="orb-wrapper">
            <div
              className={`orb-liquid-halo ${
                isSpeaking || recording
                  ? "orb-listening-mini"
                  : processing
                  ? "orb-processing-mini"
                  : ""
              }`}
            />
            <div
              className={`orb-mini ${
                isSpeaking || recording
                  ? "orb-listening-mini"
                  : processing
                  ? "orb-processing-mini"
                  : ""
              }`}
            >
              <div className="orb-water-sheen" />
            </div>
          </div>
          <div className="orb-status-text">
            <strong>
              {isSpeaking
                ? "Speaking reply..."
                : recording
                ? "Listening to your voice..."
                : uploadedFileName
                ? `Processing "${uploadedFileName}"...`
                : processing
                ? "Transcribing with Prisma STT..."
                : operationLoading
                ? "Updating shop records in DB..."
                : "Ready for your command"}
            </strong>
            <span>
              {isSpeaking
                ? "Audio playback in progress"
                : recording
                ? "Speak now in Hindi, Hinglish, or English"
                : uploadedFileName
                ? "Analyzing uploaded audio file"
                : "Voice or audio upload in Hindi, Hinglish, & English"}
            </span>
          </div>
        </div>

        {/* Scrollable Conversation Feed */}
        <div className="assistant-feed">
          {voiceResult ? (
            <div className="chat-turn">
              {/* User Bubble */}
              {voiceResult.transcript && (
                <div className="user-message-card">
                  <div className="user-tag">
                    <span>YOU</span>
                    <span>PROMPT</span>
                  </div>
                  <p className="user-text">“{voiceResult.transcript}”</p>
                </div>
              )}

              {/* AI Response Card */}
              <div className="assistant-message-card">
                <div className="ai-header-row">
                  <div className="ai-header-brand">
                    <span className="ai-sparkle">✦</span>
                    <span>VYAPAR ASSISTANT</span>
                    {voiceResult.detected_language && (
                      <span className="lang-pill">
                        {voiceResult.detected_language === "hi"
                          ? "🇮🇳 HINDI"
                          : "🌐 ENGLISH"}
                      </span>
                    )}
                  </div>
                  <button
                    type="button"
                    className={`tts-speaker-btn ${isSpeaking ? "tts-speaking" : ""}`}
                    onClick={() => {
                      if (isSpeaking) {
                        if (audioPlayerRef.current) {
                          audioPlayerRef.current.pause();
                          audioPlayerRef.current = null;
                        }
                        if (
                          typeof window !== "undefined" &&
                          "speechSynthesis" in window
                        ) {
                          window.speechSynthesis.cancel();
                        }
                        setIsSpeaking(false);
                      } else {
                        speakMessage(
                          voiceResult.message,
                          voiceResult.detected_language
                        );
                      }
                    }}
                    title="Listen to audio response via Gnani Timbre"
                  >
                    {isSpeaking ? "🔊 Playing Timbre..." : "🔊 Listen"}
                  </button>
                </div>

                <div className="ai-text-box">
                  <p>{voiceResult.message}</p>
                </div>

                {/* Operation-Aware Confirmation Card */}
                {voiceResult.pending_operation && (
                  <ConfirmationCard
                    plan={
                      voiceResult.operation_plan ||
                      voiceResult.pending_operation.payload
                    }
                    confirmationMessage={
                      voiceResult.pending_operation.confirmation_message
                    }
                    operationLoading={operationLoading}
                    onConfirm={() => void confirmOperation()}
                    onCancel={() => void cancelOperation()}
                  />
                )}

                {/* Clarifications if any */}
                {voiceResult.clarification_questions?.map(
                  (question, index) => (
                    <div className="clarification-item" key={index}>
                      <strong>Question:</strong> {question}
                    </div>
                  )
                )}

                {/* Success feedback */}
                {voiceResult.status === "COMPLETED" && (
                  <div className="success-badge-card">
                    <span>✓</span> Transaction committed to PostgreSQL successfully!
                  </div>
                )}

                {/* Cancelled feedback */}
                {voiceResult.status === "CANCELLED" && (
                  <div
                    className="clarification-item"
                    style={{ borderColor: "#64748b", color: "#cbd5e1" }}
                  >
                    <span>✕</span> Operation cancelled. No records were modified.
                  </div>
                )}
              </div>
            </div>
          ) : (
            /* Default Suggestions */
            <div className="suggestions-panel">
              <span className="suggestions-title">Try saying or typing</span>
              <button
                type="button"
                className="suggestion-chip"
                onClick={() =>
                  void runCommandString(
                    "Aaj supplier se Maggi ke 10 packets aaye hain. Stock mein 10 packets add kar do."
                  )
                }
              >
                <span>▤</span>
                <div>
                  “Aaj supplier se Maggi ke 10 packets aaye hain. Stock mein 10 packets add kar do.”
                </div>
              </button>
              <button
                type="button"
                className="suggestion-chip"
                onClick={() =>
                  void runCommandString("Rahul ko 250 rupaye udhaar diye.")
                }
              >
                <span>₹</span>
                <div>“Rahul ko 250 rupaye udhaar diye.”</div>
              </button>
              <button
                type="button"
                className="suggestion-chip"
                onClick={() =>
                  void runCommandString("Aaj ki total sales kitni hui?")
                }
              >
                <span>↗</span>
                <div>“Aaj ki total sales kitni hui?”</div>
              </button>
            </div>
          )}
        </div>

        {/* Pinned Bottom Interactive Dock */}
        <div className="assistant-dock">
          {voiceError && (
            <div className="voice-error-toast">
              ⚠️ {voiceError}
            </div>
          )}

          {/* Live Real-Time Captions */}
          {recording && (
            <div className="live-caption-box">
              <div className="live-caption-header">
                <span className="live-caption-dot" />
                <span>DETECTING VOICE (LIVE CAPTIONS)</span>
              </div>
              <p className="live-caption-text">
                {liveCaption
                  ? `“${liveCaption}”`
                  : "Listening to your voice... Speak naturally in Hindi or English"}
              </p>
            </div>
          )}

          {/* Hidden File Input for Audio File Upload */}
          <input
            ref={fileInputRef}
            type="file"
            accept="audio/*,.wav,.mp3,.m4a,.webm,.ogg,.flac,.3gp"
            style={{ display: "none" }}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) {
                void uploadAudioFile(file);
                e.target.value = "";
              }
            }}
          />

          {/* Hero Microphone & Audio Upload Card */}
          <div
            className={`hero-mic-card ${recording ? "hero-mic-card-recording" : ""} ${
              isDragging ? "hero-mic-card-dragover" : ""
            }`}
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setIsDragging(false);
              const file = e.dataTransfer.files?.[0];
              if (file) {
                void uploadAudioFile(file);
              }
            }}
            onClick={() => {
              if (processing || operationLoading) return;
              if (recording) stopRecording();
              else void startRecording();
            }}
          >
            <div className="hero-mic-btn-wrapper">
              {recording && (
                <>
                  <div className="mic-acoustic-ripple" />
                  <div className="mic-acoustic-ripple ripple-delay-1" />
                </>
              )}
              <button
                type="button"
                className={`hero-mic-btn ${recording ? "hero-mic-recording" : ""}`}
                disabled={processing || operationLoading}
                aria-label={recording ? "Stop recording" : "Tap microphone to speak"}
                onClick={(e) => {
                  e.stopPropagation();
                  if (recording) stopRecording();
                  else void startRecording();
                }}
              >
                {processing ? (
                  <div className="button-spinner" />
                ) : recording ? (
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
                    <rect x="6" y="6" width="12" height="12" rx="2.5" />
                  </svg>
                ) : (
                  <svg
                    width="24"
                    height="24"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z" />
                    <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                    <line x1="12" y1="19" x2="12" y2="23" />
                    <line x1="8" y1="23" x2="16" y2="23" />
                  </svg>
                )}
              </button>
            </div>

            <div className="hero-mic-info">
              <div className="hero-mic-title-row">
                <strong>
                  {recording
                    ? "Tap to finish speaking"
                    : uploadedFileName
                    ? `Processing "${uploadedFileName}"...`
                    : processing
                    ? "Transcribing voice with Prisma..."
                    : isDragging
                    ? "Drop audio file to transcribe"
                    : "Tap microphone to speak"}
                </strong>
                {recording && (
                  <div className="soundwave-bars">
                    <span className="soundwave-bar" />
                    <span className="soundwave-bar" />
                    <span className="soundwave-bar" />
                    <span className="soundwave-bar" />
                    <span className="soundwave-bar" />
                  </div>
                )}
              </div>
              <div className="hero-mic-footer-row">
                <span>
                  {recording
                    ? "Listening in real time · Click anywhere to stop"
                    : uploadedFileName
                    ? "Prisma STT transcribing..."
                    : isDragging
                    ? "Release to upload"
                    : "Hindi · Hinglish · English"}
                </span>
                <button
                  type="button"
                  className="hero-upload-btn"
                  disabled={processing || recording || operationLoading}
                  title="Upload an audio file (.mp3, .wav, .m4a, etc.)"
                  onClick={(e) => {
                    e.stopPropagation();
                    fileInputRef.current?.click();
                  }}
                >
                  <svg
                    width="12"
                    height="12"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="17 8 12 3 7 8" />
                    <line x1="12" y1="3" x2="12" y2="15" />
                  </svg>
                  <span>Upload audio</span>
                </button>
              </div>
            </div>
          </div>

          {/* Compact Secondary Text Input */}
          <div className="dock-text-divider">
            <span>OR TYPE A COMMAND</span>
          </div>

          <form onSubmit={sendTextCommand} className="dock-form">
            <input
              type="text"
              value={commandText}
              onChange={(event) => setCommandText(event.target.value)}
              placeholder="Type a command in Hindi or English..."
              disabled={processing || operationLoading || recording}
              aria-label="Type a shop command"
              className="dock-input"
            />
            <button
              type="submit"
              disabled={
                !commandText.trim() ||
                processing ||
                operationLoading ||
                recording
              }
              className="dock-send-btn"
            >
              Send
            </button>
          </form>
        </div>
      </aside>
    </main>
  );
}

/* =========================================================
   SUBCOMPONENTS
   ========================================================= */

function ConfirmationCard({
  plan,
  confirmationMessage,
  operationLoading,
  onConfirm,
  onCancel,
}: {
  plan?: OperationPlanData | null;
  confirmationMessage?: string;
  operationLoading: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const opType = plan?.operation_type || "OPERATION";

  let typeLabel = "Action Required";
  let entityLabel = "AFFECTED RECORD";
  let entityName = "Store Data";
  let currentVal = "—";
  let changeVal = "—";
  let resultVal = "—";
  let entityIcon = "✦";

  if (opType === "INVENTORY_ADJUSTMENT") {
    const isAdd = plan?.adjustment_direction === "ADD";
    typeLabel = isAdd ? "Stock Inflow (Add)" : "Stock Outflow (Remove)";
    entityLabel = "AFFECTED PRODUCT";
    entityName = plan?.product_name || "Product";
    entityIcon = "▤";
    const unit = plan?.unit || "pkts";
    currentVal = `${quantity(Number(plan?.previous_quantity ?? 0))} ${unit}`;
    changeVal = `${isAdd ? "+" : "-"}${quantity(Number(plan?.quantity_delta ?? 0))} ${unit}`;
    resultVal = `${quantity(Number(plan?.new_quantity ?? 0))} ${unit}`;
  } else if (opType === "SALE") {
    const isCredit = (plan?.amount_due_paise ?? 0) > 0;
    typeLabel = isCredit
      ? "Credit Sale (Udhaar)"
      : `Cash Sale (${plan?.payment_method || "CASH"})`;
    entityLabel = plan?.customer_name ? "AFFECTED CUSTOMER" : "ITEMS SOLD";
    entityName =
      plan?.customer_name ||
      (plan?.items?.map((i) => `${i.product_name} (×${i.quantity})`).join(", ") ||
        "Retail Sale");
    entityIcon = plan?.customer_name ? "♙" : "↗";
    currentVal = isCredit
      ? `Prev: ${money(plan?.previous_customer_balance_paise ?? 0)}`
      : "Cart total";
    changeVal = `+ ${money(plan?.total_amount_paise)}`;
    resultVal = isCredit
      ? `Due: ${money(plan?.amount_due_paise)}`
      : `Paid ${money(plan?.amount_paid_paise)}`;
  } else if (opType === "REPAYMENT") {
    typeLabel = "Customer Repayment";
    entityLabel = "AFFECTED CUSTOMER";
    entityName = plan?.customer_name || "Customer";
    entityIcon = "♙";
    currentVal = `Prev: ${money(plan?.previous_outstanding_paise)}`;
    changeVal = `- ${money(plan?.amount_paise)}`;
    resultVal = `New: ${money(plan?.new_outstanding_paise)}`;
  }

  return (
    <div className="confirmation-card-v2">
      <div className="confirm-header-row">
        <span className="op-type-pill">
          <span>●</span> {typeLabel}
        </span>
        <span className="op-verify-pill">
          <span /> Needs confirmation
        </span>
      </div>

      <div className="target-entity-banner">
        <div className="target-avatar">{entityIcon}</div>
        <div className="target-details">
          <span className="target-label">{entityLabel}</span>
          <strong className="target-name">{entityName}</strong>
        </div>
      </div>

      <div className="comparison-grid">
        <div className="metric-cell">
          <span className="metric-cell-label">CURRENT</span>
          <span className="metric-cell-val">{currentVal}</span>
        </div>
        <div className="metric-cell">
          <span className="metric-cell-label">PROPOSED CHANGE</span>
          <span className="metric-cell-val metric-cell-change">{changeVal}</span>
        </div>
        <div className="metric-cell">
          <span className="metric-cell-label">COMMITTED RESULT</span>
          <span className="metric-cell-val metric-cell-result">{resultVal}</span>
        </div>
      </div>

      {confirmationMessage && !plan && (
        <p style={{ margin: "4px 0 0", color: "#cbd5e1", fontSize: "12px" }}>
          {confirmationMessage}
        </p>
      )}

      {operationLoading && (
        <div className="updating-banner">
          <div className="loader loader-dark" style={{ width: "16px", height: "16px" }} />
          <span>Executing atomic database update...</span>
        </div>
      )}

      <div className="confirmation-actions-v2">
        <button
          className="btn-confirm-action"
          disabled={operationLoading}
          onClick={onConfirm}
        >
          {operationLoading ? (
            <>
              <div className="button-spinner" />
              <span>Updating...</span>
            </>
          ) : (
            <>
              <span>✓</span> Confirm & Execute
            </>
          )}
        </button>
        <button
          className="btn-cancel-action"
          disabled={operationLoading}
          onClick={onCancel}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  detail,
  icon,
}: {
  label: string;
  value: string;
  detail: string;
  icon: string;
}) {
  return (
    <div className="metric-card">
      <div className="metric-top">
        <span>{label}</span>
        <div className="metric-icon">{icon}</div>
      </div>
      <div className="metric-value">{value}</div>
      <div className="metric-detail">{detail}</div>
    </div>
  );
}

function InventoryTable({
  items,
  highlightedId,
  animatingChange,
}: {
  items: InventoryItem[];
  highlightedId?: string | null;
  animatingChange?: { productId: string; prev: string; next: string } | null;
}) {
  if (items.length === 0) {
    return <div className="empty-state">No inventory items found.</div>;
  }

  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>PRODUCT</th>
            <th>SKU</th>
            <th>QUANTITY</th>
            <th>REORDER AT</th>
            <th>STATUS</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => {
            const isHighlighted = highlightedId === item.product_id;
            const isAnimating = animatingChange?.productId === item.product_id;

            return (
              <tr
                key={item.product_id}
                id={`product-row-${item.product_id}`}
                className={isHighlighted ? "row-highlighted" : ""}
              >
                <td className="product-cell">
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <span>{item.product_name}</span>
                    {isHighlighted && (
                      <span className="live-update-badge">● LIVE UPDATE</span>
                    )}
                  </div>
                </td>
                <td>{item.sku || "—"}</td>
                <td>
                  {isAnimating ? (
                    <span className="quantity-animating">
                      <span className="qty-prev">
                        {quantity(Number(animatingChange.prev))}
                      </span>
                      <span className="qty-arrow">→</span>
                      <span className="qty-next">
                        {quantity(Number(animatingChange.next))} {item.unit}
                      </span>
                    </span>
                  ) : (
                    <span>
                      {quantity(item.quantity)} {item.unit}
                    </span>
                  )}
                </td>
                <td>
                  {quantity(item.reorder_level)} {item.unit}
                </td>
                <td>
                  <span
                    className={`stock-badge ${item.is_low_stock ? "stock-low" : "stock-good"
                      }`}
                  >
                    <span /> {item.is_low_stock ? "Low stock" : "In stock"}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function CustomerTable({
  customers,
  highlightedId,
}: {
  customers: CreditCustomer[];
  highlightedId?: string | null;
}) {
  if (customers.length === 0) {
    return (
      <div className="empty-state">No outstanding customer credit.</div>
    );
  }

  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>CUSTOMER</th>
            <th>OUTSTANDING BALANCE</th>
            <th>STATUS</th>
          </tr>
        </thead>
        <tbody>
          {customers.map((customer) => {
            const isHighlighted = highlightedId === customer.customer_id;

            return (
              <tr
                key={customer.customer_id}
                id={`customer-credit-row-${customer.customer_id}`}
                className={isHighlighted ? "row-highlighted" : ""}
              >
                <td className="product-cell">
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <span>{customer.customer_name}</span>
                    {isHighlighted && (
                      <span className="live-update-badge">● UPDATED</span>
                    )}
                  </div>
                </td>
                <td className="balance-cell">
                  {money(customer.outstanding_paise)}
                </td>
                <td>
                  <span className="credit-badge">Credit due</span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function CustomerDirectory({
  customers,
  credit,
  highlightedId,
}: {
  customers: Customer[];
  credit: CreditCustomer[];
  highlightedId?: string | null;
}) {
  if (customers.length === 0) {
    return <div className="empty-state">No customers found.</div>;
  }

  const balances = new Map(
    credit.map((customer) => [
      customer.customer_id,
      customer.outstanding_paise,
    ])
  );

  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>CUSTOMER</th>
            <th>PHONE</th>
            <th>OUTSTANDING</th>
            <th>STATUS</th>
          </tr>
        </thead>
        <tbody>
          {customers.map((customer) => {
            const isHighlighted = highlightedId === customer.id;

            return (
              <tr
                key={customer.id}
                id={`customer-row-${customer.id}`}
                className={isHighlighted ? "row-highlighted" : ""}
              >
                <td className="product-cell">
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <span>{customer.name}</span>
                    {isHighlighted && (
                      <span className="live-update-badge">● UPDATED</span>
                    )}
                  </div>
                </td>
                <td>{customer.phone || "—"}</td>
                <td className="balance-cell">
                  {money(balances.get(customer.id))}
                </td>
                <td>
                  <span className="stock-badge stock-good">
                    <span /> Active
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

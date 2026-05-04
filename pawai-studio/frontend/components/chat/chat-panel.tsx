"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { ArrowUp, Mic, PawPrint, Sparkles, Square } from "lucide-react";
import { useStateStore } from "@/stores/state-store";
import { useAudioRecorder } from "@/hooks/use-audio-recorder";
import { AudioVisualizer } from "@/components/chat/audio-visualizer";
import { BrainStatusPill } from "@/components/chat/brain-status-pill";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { getGatewayHttpUrl } from "@/lib/gateway-url";
import { cn } from "@/lib/utils";

interface UserMessage {
  id: string;
  type: "user";
  text: string;
  timestamp: string;
}

interface AIMessage {
  id: string;
  type: "ai";
  text: string;
  timestamp: string;
}

interface VoiceMessage {
  id: string;
  type: "voice";
  text: string;
  intent: string;
  confidence: number;
  timestamp: string;
}

type ChatMessage = UserMessage | AIMessage | VoiceMessage;

function formatTime(date: Date): string {
  return date.toLocaleTimeString("zh-TW", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

/**
 * ChatPanel — chat-first redesign (commit step G).
 *
 * Renders ONLY normal user / assistant / voice chat bubbles + the input
 * composer + a thin BrainStatusPill at the top. All brain debug widgets
 * (skill buttons, trace drawer, brain plan / skill step / safety / alert /
 * result bubbles) have been removed. Devs see those via /studio/dev or
 * ?dev=1 + ⚙ button (step H).
 */
export function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState("");
  const [isThinking, setIsThinking] = useState(false);

  const lastTtsText = useStateStore((s) => s.lastTtsText);
  const lastTtsAt = useStateStore((s) => s.lastTtsAt);
  const {
    isRecording,
    isProcessing,
    audioLevels,
    lastResult: voiceResult,
    error: voiceError,
    startRecording,
    stopRecording,
  } = useAudioRecorder();

  const pendingRequestIdRef = useRef<string | null>(null);
  const pendingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const prevVoiceResultRef = useRef(voiceResult);

  const hasMessages = messages.length > 0;

  // Auto-scroll on new messages.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isThinking]);

  // Cleanup pending timeout on unmount.
  useEffect(() => {
    return () => {
      if (pendingTimeoutRef.current) clearTimeout(pendingTimeoutRef.current);
    };
  }, []);

  // TTS reply → AI bubble (only when pending).
  useEffect(() => {
    if (lastTtsAt && lastTtsText && pendingRequestIdRef.current) {
      pendingRequestIdRef.current = null;
      if (pendingTimeoutRef.current) {
        clearTimeout(pendingTimeoutRef.current);
        pendingTimeoutRef.current = null;
      }
      setIsThinking(false);
      const aiMsg: AIMessage = {
        id: `ai-${Date.now()}`,
        type: "ai",
        text: lastTtsText,
        timestamp: formatTime(new Date()),
      };
      setMessages((prev) => [...prev, aiMsg]);
    }
  }, [lastTtsAt, lastTtsText]);

  // Voice result → add as voice message + enter pending.
  useEffect(() => {
    if (voiceResult && voiceResult !== prevVoiceResultRef.current) {
      prevVoiceResultRef.current = voiceResult;
      const voiceMsg: VoiceMessage = {
        id: `voice-${Date.now()}`,
        type: "voice",
        text: voiceResult.asr,
        intent: voiceResult.intent,
        confidence: voiceResult.confidence,
        timestamp: formatTime(new Date()),
      };
      setMessages((prev) => [...prev, voiceMsg]);

      const requestId = `voice-${Date.now()}`;
      pendingRequestIdRef.current = requestId;
      setIsThinking(true);
      if (pendingTimeoutRef.current) clearTimeout(pendingTimeoutRef.current);
      pendingTimeoutRef.current = setTimeout(() => {
        if (pendingRequestIdRef.current === requestId) {
          pendingRequestIdRef.current = null;
          setIsThinking(false);
        }
      }, 8000);
    }
  }, [voiceResult]);

  // Auto-resize textarea.
  const adjustTextareaHeight = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
  }, []);

  useEffect(() => {
    adjustTextareaHeight();
  }, [inputText, adjustTextareaHeight]);

  async function handleSend() {
    const text = inputText.trim();
    if (!text || isThinking) return;

    const userMsg: UserMessage = {
      id: `user-${Date.now()}`,
      type: "user",
      text,
      timestamp: formatTime(new Date()),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInputText("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";

    // CRITICAL: arm the pending state BEFORE the fetch await. The mock /
    // real backend can broadcast `tts:tts_speaking` while fetch is still
    // in-flight (Gemini round-trip is ~2s); if we arm pending only after
    // fetch resolves, the tts event lands while pendingRequestIdRef is
    // still null and the AI bubble useEffect skips it → user sees the 8s
    // timeout fallback even though Gemini answered correctly.
    const requestId = `req-${Date.now()}`;
    pendingRequestIdRef.current = requestId;
    setIsThinking(true);
    if (pendingTimeoutRef.current) clearTimeout(pendingTimeoutRef.current);
    pendingTimeoutRef.current = setTimeout(() => {
      if (pendingRequestIdRef.current === requestId) {
        pendingRequestIdRef.current = null;
        setIsThinking(false);
        const errMsg: AIMessage = {
          id: `ai-timeout-${Date.now()}`,
          type: "ai",
          text: "回應逾時，請確認 LLM 是否在線。",
          timestamp: formatTime(new Date()),
        };
        setMessages((prev) => [...prev, errMsg]);
      }
    }, 8000);

    try {
      const response = await fetch(`${getGatewayHttpUrl()}/api/text_input`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, request_id: requestId }),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
    } catch {
      // Network / gateway error — clear pending state and show error inline.
      if (pendingRequestIdRef.current === requestId) {
        pendingRequestIdRef.current = null;
        setIsThinking(false);
        if (pendingTimeoutRef.current) {
          clearTimeout(pendingTimeoutRef.current);
          pendingTimeoutRef.current = null;
        }
      }
      const errMsg: AIMessage = {
        id: `ai-err-${Date.now()}`,
        type: "ai",
        text: "Brain 文字通道未連線，請確認 Gateway 是否啟動。",
        timestamp: formatTime(new Date()),
      };
      setMessages((prev) => [...prev, errMsg]);
      return;
    }

    textareaRef.current?.focus();
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  // Composer — text input + mic + send. Used in both empty and conversation views.
  const composerInput = (
    <div
      className={cn(
        "relative rounded-2xl border transition-all duration-200",
        isRecording
          ? "border-red-500/40 shadow-[0_0_0_1px_rgba(239,68,68,0.15)] bg-surface"
          : "border-border/60 bg-surface focus-within:border-primary/40 focus-within:shadow-[0_0_0_1px_rgba(124,107,255,0.15)]",
      )}
    >
      <Textarea
        ref={textareaRef}
        value={inputText}
        onChange={(e) => setInputText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={isRecording ? "錄音中..." : "傳送訊息給 PawAI…"}
        disabled={isThinking || isRecording}
        rows={1}
        className={cn(
          "min-h-[48px] max-h-[200px] resize-none border-0 bg-transparent pr-24",
          "text-foreground placeholder:text-muted-foreground/50",
          "focus-visible:ring-0 focus-visible:ring-offset-0 focus-visible:border-transparent",
          "px-4 py-3 text-[15px] leading-relaxed",
        )}
      />
      <Button
        onClick={() => (isRecording ? stopRecording() : startRecording())}
        disabled={isThinking || isProcessing}
        size={isRecording && audioLevels.length > 0 ? "default" : "icon"}
        className={cn(
          "absolute bottom-2 transition-all duration-200",
          isRecording
            ? "right-12 h-9 px-3 rounded-full bg-red-500 hover:bg-red-600 text-white shadow-sm flex items-center gap-2"
            : isProcessing
              ? "right-12 h-9 w-9 rounded-lg bg-amber-500 text-white cursor-wait"
              : "right-12 h-9 w-9 rounded-lg bg-muted text-muted-foreground hover:bg-muted-foreground/20 hover:text-foreground",
        )}
        title={isRecording ? "停止錄音" : isProcessing ? "辨識中..." : "語音輸入"}
      >
        {isRecording ? (
          <>
            <AudioVisualizer levels={audioLevels} isActive={isRecording} />
            {audioLevels.length === 0 && <Mic className="h-3.5 w-3.5 animate-pulse" />}
            <Square className="h-3 w-3 shrink-0" />
          </>
        ) : (
          <Mic className="h-4 w-4" />
        )}
      </Button>
      <Button
        onClick={handleSend}
        disabled={isThinking || isRecording || !inputText.trim()}
        size="icon"
        title="傳送"
        aria-label="傳送訊息"
        className={cn(
          "absolute right-2 bottom-2 h-9 w-9 rounded-lg transition-all duration-200",
          inputText.trim() && !isRecording
            ? "bg-primary hover:bg-primary/90 text-primary-foreground shadow-sm"
            : "bg-muted text-muted-foreground cursor-not-allowed",
        )}
      >
        <ArrowUp className="h-4 w-4" />
      </Button>
      {voiceError && (
        <div className="absolute -top-7 left-0 right-0 text-center">
          <span className="text-[11px] text-destructive bg-background/90 px-2 py-0.5 rounded">
            {voiceError}
          </span>
        </div>
      )}
    </div>
  );

  // Empty state — minimal hero + composer (no skill buttons / no module strip).
  if (!hasMessages) {
    return (
      <div className="flex h-full flex-col">
        <BrainStatusPill />
        <div className="flex flex-1 flex-col items-center justify-center px-4 md:px-8">
          <div className="flex w-full max-w-[var(--chat-max-w)] flex-col items-center gap-6">
            <div className="flex flex-col items-center gap-3 -mt-16">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-sky-500/10 border border-sky-400/20">
                <PawPrint className="h-7 w-7 text-sky-400" />
              </div>
              <h1 className="text-2xl font-semibold text-foreground tracking-tight">
                嗨，我是 PawAI
              </h1>
              <p className="text-sm text-muted-foreground/70">
                有什麼想聊的嗎？
              </p>
            </div>
            <div className="w-full">{composerInput}</div>
          </div>
        </div>
      </div>
    );
  }

  // Conversation view — bubble stream + bottom composer.
  return (
    <div className="flex h-full flex-col">
      <BrainStatusPill />
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto flex max-w-[var(--chat-max-w)] flex-col gap-3 px-4 md:px-8 py-6">
          {messages.map((msg) => {
            if (msg.type === "user") {
              return (
                <div key={msg.id} className="flex justify-end">
                  <div className="max-w-[70%] md:max-w-[70%]">
                    <div
                      className="rounded-2xl rounded-br-md px-4 py-3 text-[15px] leading-relaxed"
                      style={{
                        backgroundColor: "var(--bubble-user-bg)",
                        color: "var(--bubble-user-fg)",
                      }}
                    >
                      {msg.text}
                    </div>
                  </div>
                </div>
              );
            }
            if (msg.type === "voice") {
              return (
                <div key={msg.id} className="flex justify-end">
                  <div className="max-w-[70%]">
                    <div
                      className="rounded-2xl rounded-br-md border px-4 py-3 text-[15px] leading-relaxed"
                      style={{
                        backgroundColor: "var(--bubble-user-bg)",
                        borderColor: "var(--bubble-user-bg)",
                        color: "var(--bubble-user-fg)",
                      }}
                    >
                      <div className="mb-1 flex items-center gap-2">
                        <Mic className="h-3 w-3" />
                        <span className="font-mono text-[10px] opacity-80">語音輸入</span>
                        <Badge className="h-4 rounded-full bg-emerald-500/20 px-1.5 py-0 text-[9px] font-normal text-emerald-200 border-transparent">
                          已發佈
                        </Badge>
                      </div>
                      {msg.text}
                      {msg.intent && (
                        <div className="mt-1.5 font-mono text-[10px] opacity-70">
                          intent: {msg.intent} · {Math.round(msg.confidence * 100)}%
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            }
            // AI message — left, transparent + thin outline.
            return (
              <div key={msg.id} className="flex gap-3">
                <div className="flex shrink-0 items-start pt-0.5">
                  <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10">
                    <Sparkles className="h-3.5 w-3.5 text-primary" />
                  </div>
                </div>
                <div className="min-w-0 flex-1">
                  <div
                    className="rounded-2xl border px-4 py-3 text-[15px] leading-relaxed"
                    style={{
                      borderColor: "var(--bubble-ai-border)",
                      color: "var(--bubble-ai-fg)",
                    }}
                  >
                    {msg.text}
                  </div>
                </div>
              </div>
            );
          })}
          {isThinking && (
            <div className="flex gap-3" role="status" aria-live="polite">
              <span className="sr-only">PawAI 正在思考</span>
              <div className="flex shrink-0 items-start pt-0.5" aria-hidden="true">
                <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10">
                  <Sparkles className="h-3.5 w-3.5 text-primary" />
                </div>
              </div>
              <div className="flex items-center gap-1 py-2" aria-hidden="true">
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary/60 [animation-delay:0ms]" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary/60 [animation-delay:150ms]" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary/60 [animation-delay:300ms]" />
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>
      <div className="border-t border-border/40">
        <div className="mx-auto w-full max-w-[var(--chat-max-w)] px-4 md:px-8 py-3">
          {composerInput}
        </div>
      </div>
    </div>
  );
}

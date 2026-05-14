"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Mic, PawPrint, RotateCcw, Sparkles } from "lucide-react";
import { useStateStore } from "@/stores/state-store";
import { useAudioRecorder } from "@/hooks/use-audio-recorder";
import { BrainStatusPill } from "@/components/chat/brain-status-pill";
import { Composer } from "@/components/chat/composer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
  // P1-1c/d：樣式分類
  variant?: "pending" | "spontaneous";
  source?: string; // skill_say | chat_reply | say_canned | undefined
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
 * P1-1d + Phase 2-mini：依 source / variant 回傳 AI bubble className。
 * skill_say → 綠 / say_canned → 橙 / chat_reply or pending → 一般灰 / spontaneous-no-source → 淡灰
 */
function getBubbleClassName(msg: AIMessage): string {
  if (msg.source === "skill_say") {
    return "border-emerald-500/30 bg-emerald-500/10 text-emerald-100";
  }
  if (msg.source === "say_canned") {
    return "border-orange-500/30 bg-orange-500/10 text-orange-100";
  }
  if (msg.source === "chat_reply" || msg.variant === "pending") {
    return "border-slate-600/40 bg-slate-700/30 text-slate-100";
  }
  // spontaneous（無 source）— 淡灰 + 時鐘圖示由 JSX 加
  return "border-slate-700/30 bg-slate-800/20 text-slate-300 opacity-90";
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

  const ttsMessages = useStateStore((s) => s.ttsMessages);
  const latestSkillResult = useStateStore((s) => s.brainResults[0]);
  const {
    isRecording,
    isProcessing,
    audioLevels,
    lastResult: voiceResult,
    error: voiceError,
    startRecording,
    stopRecording,
  } = useAudioRecorder();

  // pendingRequestIdRef：管 isThinking + speech intent 配對 + timeout（不再 gate display）
  const pendingRequestIdRef = useRef<string | null>(null);
  const pendingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // P1-1c：防止 ttsMessages 重複 append
  const lastSeenTtsIdRef = useRef<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const prevVoiceResultRef = useRef(voiceResult);
  // J: stick-to-bottom — only auto-scroll when user is already near the
  // bottom. If they scroll up to read older messages, new messages must
  // not yank the viewport back down.
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const shouldAutoScrollRef = useRef(true);
  // Set true while a programmatic scrollIntoView animation is in-flight,
  // so its synthetic scroll events don't masquerade as user-initiated scroll
  // and flip shouldAutoScrollRef to false (which would skip the next message's
  // auto-scroll when scrollHeight grew faster than scrollTop caught up).
  const isAutoScrollingRef = useRef(false);
  const autoScrollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // ChatGPT-like absolute-bottom composer: header + composer bar are absolute-
  // positioned within ChatPanel's relative root. Scroll area is also absolute,
  // clamped between their measured heights so messages never collide with bar.
  // Initials are conservative defaults (avoid first-frame top=0 covering header).
  const headerRef = useRef<HTMLDivElement>(null);
  const composerBarRef = useRef<HTMLDivElement>(null);
  const [headerH, setHeaderH] = useState(44);
  const [composerBarH, setComposerBarH] = useState(96);

  const hasMessages = messages.length > 0;

  function handleScrollContainer() {
    // Ignore scroll events synthesised by our own scrollIntoView call —
    // otherwise the synthetic events flip shouldAutoScrollRef to false during
    // the brief window when scrollHeight has grown but scrollTop hasn't yet
    // caught up, causing the next rapid message to skip auto-scroll.
    if (isAutoScrollingRef.current) return;
    const el = scrollContainerRef.current;
    if (!el) return;
    // 30px tolerance — within this distance to bottom counts as "stuck".
    shouldAutoScrollRef.current =
      el.scrollHeight - el.scrollTop - el.clientHeight < 30;
  }

  // Auto-scroll on new messages, but only when user is at/near the bottom.
  // Instant snap (behavior:"auto") rather than smooth — smooth animation
  // produces a visible empty area below long messages while scrollTop catches
  // up to the freshly grown scrollHeight; instant snap eliminates that window.
  useEffect(() => {
    if (!shouldAutoScrollRef.current) return;
    isAutoScrollingRef.current = true;
    bottomRef.current?.scrollIntoView({ behavior: "auto" });
    if (autoScrollTimerRef.current) clearTimeout(autoScrollTimerRef.current);
    // Instant scroll completes synchronously, but a few synthetic scroll
    // events still fire on the next frame; brief lock to swallow them.
    autoScrollTimerRef.current = setTimeout(() => {
      isAutoScrollingRef.current = false;
    }, 100);
  }, [messages, isThinking]);

  // Measure header + composer bar heights so the absolute-positioned scroll
  // area can clamp top/bottom precisely. Only registers in conversation view —
  // empty state has no composer bar element and uses a different layout.
  useEffect(() => {
    if (!hasMessages) return;
    const headerEl = headerRef.current;
    const barEl = composerBarRef.current;
    if (!headerEl || !barEl) return;
    const sync = () => {
      setHeaderH(headerEl.offsetHeight);
      setComposerBarH(barEl.offsetHeight);
    };
    sync();
    const ro = new ResizeObserver(sync);
    ro.observe(headerEl);
    ro.observe(barEl);
    return () => ro.disconnect();
  }, [hasMessages]);

  // Cleanup pending timeout on unmount.
  useEffect(() => {
    return () => {
      if (pendingTimeoutRef.current) clearTimeout(pendingTimeoutRef.current);
      if (autoScrollTimerRef.current) clearTimeout(autoScrollTimerRef.current);
    };
  }, []);

  // P1-1c：TTS reply → AI bubble（監聽 ttsMessages 全部 append，不再只 gate pending）
  useEffect(() => {
    if (ttsMessages.length === 0) return;

    // 找出 lastSeen 之後所有尚未顯示的 message
    const lastSeenIdx = lastSeenTtsIdRef.current
      ? ttsMessages.findLastIndex((m) => m.id === lastSeenTtsIdRef.current)
      : -1;
    const newMessages = ttsMessages.slice(lastSeenIdx + 1);

    if (newMessages.length === 0) return;

    // pending 配對的當一般灰，spontaneous 當淡灰
    const wasPending = pendingRequestIdRef.current !== null;

    setMessages((prev) => [
      ...prev,
      ...newMessages.map((m) => ({
        id: m.id,
        type: "ai" as const,
        text: m.text,
        timestamp: formatTime(new Date()),
        variant: (wasPending ? "pending" : "spontaneous") as "pending" | "spontaneous",
        source: m.source,
      })),
    ]);

    // 更新 lastSeen
    lastSeenTtsIdRef.current = ttsMessages[ttsMessages.length - 1].id;

    // 若有 pending request → 第一條 TTS 視為配對成功，清掉 pending（取消 isThinking）
    if (pendingRequestIdRef.current) {
      pendingRequestIdRef.current = null;
      if (pendingTimeoutRef.current) {
        clearTimeout(pendingTimeoutRef.current);
        pendingTimeoutRef.current = null;
      }
      setIsThinking(false);
    }
  }, [ttsMessages]);

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

  // P1-2: New conversation — clear local messages + POST /api/reset to clear global context.
  const handleNewConversation = useCallback(async () => {
    const ok = window.confirm(
      "將清除目前所有對話記憶，包括其他開啟的 Studio 視窗。確定？"
    );
    if (!ok) return;
    await fetch(`${getGatewayHttpUrl()}/api/reset`, { method: "POST" });
    setMessages([]);
    useStateStore.setState({ ttsMessages: [] });
    lastSeenTtsIdRef.current = null;
  }, []);

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
      // Bug C fix: gateway runs s2twp on the text; reflect the converted form
      // in the user bubble so 簡體 input shows as 繁體 immediately.
      const data = (await response.json().catch(() => null)) as
        | { text?: string }
        | null;
      const converted = data?.text;
      if (typeof converted === "string" && converted && converted !== text) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === userMsg.id && m.type === "user"
              ? { ...m, text: converted }
              : m,
          ),
        );
      }
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

  // Bundle composer props once — passed identically to <Composer /> in both
  // empty state (centred with hero) and conversation state (absolute bottom).
  const composerProps = {
    value: inputText,
    onChange: setInputText,
    onSend: handleSend,
    onKeyDown: handleKeyDown,
    textareaRef,
    isThinking,
    isRecording,
    isProcessing,
    audioLevels,
    startRecording,
    stopRecording,
    voiceError,
  };

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
            <div className="w-full">
              <Composer {...composerProps} />
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Conversation view — ChatGPT-like absolute-bottom composer.
  // Root is `relative` + `overflow-hidden`. Header sits in normal flow at top.
  // Scroll area is `absolute` clamped between measured headerH and
  // composerBarH so messages never collide with composer bar regardless of
  // textarea growth or skill-strip toggle. Composer bar is `absolute bottom-0
  // z-20` (below DevButton z-30 and Sheet z-40/50).
  return (
    <div className="relative h-full overflow-hidden">
      <div
        ref={headerRef}
        className="flex items-center justify-between bg-background"
      >
        <BrainStatusPill />
        <Button
          variant="ghost"
          size="icon"
          onClick={handleNewConversation}
          title="重置全局對話記憶（所有 device 共用）"
          aria-label="新對話"
          className="mr-2 h-8 w-8 text-muted-foreground hover:text-foreground"
        >
          <RotateCcw className="h-4 w-4" />
        </Button>
      </div>
      <div
        ref={scrollContainerRef}
        onScroll={handleScrollContainer}
        className="absolute inset-x-0 overflow-y-auto"
        style={{ top: headerH, bottom: composerBarH }}
      >
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
            // P1-1d + Phase 2-mini：source 三色 + variant 樣式分類
            const bubbleClassName = getBubbleClassName(msg);
            return (
              <div key={msg.id} className="flex gap-3">
                <div className="flex shrink-0 items-start pt-0.5">
                  <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10">
                    <Sparkles className="h-3.5 w-3.5 text-primary" />
                  </div>
                </div>
                <div className="min-w-0 flex-1">
                  <div className={cn("rounded-2xl border px-4 py-3 text-[15px] leading-relaxed", bubbleClassName)}>
                    {msg.variant === "spontaneous" && !msg.source && (
                      <span className="mr-1 opacity-60" aria-label="自發訊息" role="img">⏰</span>
                    )}
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
      <div
        ref={composerBarRef}
        data-composer-bar
        className="absolute inset-x-0 bottom-0 z-20 bg-background/80 backdrop-blur-md border-t border-border/40"
      >
        {latestSkillResult && (
          <div
            className="border-b border-border/40 px-4 md:px-8 py-1.5 text-[11px] font-mono text-muted-foreground/80 flex items-center gap-2"
            aria-live="polite"
          >
            <span className="opacity-60">skill:</span>
            <span className="text-foreground/90">{latestSkillResult.selected_skill}</span>
            <span
              className={cn(
                "rounded px-1.5 py-0.5 text-[10px]",
                latestSkillResult.status === "completed" || latestSkillResult.status === "step_success"
                  ? "bg-emerald-500/15 text-emerald-300"
                  : latestSkillResult.status === "step_failed" ||
                      latestSkillResult.status === "aborted" ||
                      latestSkillResult.status === "blocked_by_safety"
                    ? "bg-red-500/15 text-red-300"
                    : "bg-sky-500/15 text-sky-300"
              )}
            >
              {latestSkillResult.status}
            </span>
            {latestSkillResult.detail && (
              <span className="truncate opacity-70">· {latestSkillResult.detail}</span>
            )}
          </div>
        )}
        <div className="mx-auto w-full max-w-[var(--chat-max-w)] px-4 md:px-8 py-3">
          <Composer {...composerProps} />
        </div>
      </div>
    </div>
  );
}

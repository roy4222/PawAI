"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { getGatewayWsUrl } from "@/lib/gateway-url";

interface AsrResult {
  asr: string;
  intent: string;
  confidence: number;
  latency_ms: number;
  published: boolean;
  /** Optional LLM reply text (PR #42 partial port — only set if backend emits). */
  reply_text?: string;
  /** Optional TTS audio URL — when present, hook auto-plays it. */
  audio_url?: string;
}

interface UseAudioRecorderOptions {
  /**
   * If true and the backend response includes `audio_url`, the hook will
   * play it via `new Audio(url).play()`. Default **false** — ChatPanel
   * uses the gateway `/tts` event flow for playback, so auto-play here
   * would cause double-playback / echo. Enable only in dedicated debug
   * panels (e.g. `/studio/speech` SpeechPanel) talking to a backend
   * (e.g. PR #42's `:5000`) that delivers TTS as `audio_url`.
   */
  autoPlayResponseAudio?: boolean;
}

interface UseAudioRecorderResult {
  isRecording: boolean;
  isProcessing: boolean;
  audioLevels: number[];
  lastResult: AsrResult | null;
  error: string | null;
  startRecording: () => Promise<void>;
  stopRecording: () => void;
}

function getSpeechWsUrl(): string {
  return getGatewayWsUrl("/ws/speech");
}

// Prefer opus codec for best compression
function getPreferredMimeType(): string {
  if (typeof MediaRecorder === "undefined") return "";
  const types = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/ogg;codecs=opus",
    "audio/mp4",
  ];
  for (const t of types) {
    if (MediaRecorder.isTypeSupported(t)) return t;
  }
  return "";
}

const MIN_RECORD_MS = 500;

export function useAudioRecorder(options: UseAudioRecorderOptions = {}): UseAudioRecorderResult {
  const { autoPlayResponseAudio = false } = options;
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [lastResult, setLastResult] = useState<AsrResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [audioLevels, setAudioLevels] = useState<number[]>([]);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const startTimeRef = useRef<number>(0);
  const wsRef = useRef<WebSocket | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const animFrameRef = useRef<number>(0);

  // Shared cleanup for AudioContext + animation frame
  const cleanupAudioAnalysis = useCallback(() => {
    cancelAnimationFrame(animFrameRef.current);
    if (audioCtxRef.current) {
      audioCtxRef.current.close().catch(() => {});
      audioCtxRef.current = null;
    }
    setAudioLevels([]);
  }, []);

  // Cleanup on unmount — stop mic, close socket, close audio analysis
  useEffect(() => {
    return () => {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
        mediaRecorderRef.current.stop();
      }
      streamRef.current?.getTracks().forEach((t) => t.stop());
      wsRef.current?.close();
      cleanupAudioAnalysis();
    };
  }, [cleanupAudioAnalysis]);

  const sendAudio = useCallback((blob: Blob) => {
    setIsProcessing(true);
    setError(null);

    const ws = new WebSocket(getSpeechWsUrl());
    wsRef.current = ws;

    ws.onopen = async () => {
      const buffer = await blob.arrayBuffer();
      ws.send(buffer);
    };

    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data as string) as Record<string, unknown>;
        if (data.error) {
          setError(data.error as string);
        } else {
          const replyText = typeof data.reply_text === "string" ? data.reply_text : undefined;
          const audioUrl = typeof data.audio_url === "string" ? data.audio_url : undefined;

          setLastResult({
            asr: (data.asr as string) ?? "",
            intent: (data.intent as string) ?? "",
            confidence: (data.confidence as number) ?? 0,
            latency_ms: (data.latency_ms as number) ?? 0,
            published: (data.published as boolean) ?? false,
            reply_text: replyText,
            audio_url: audioUrl,
          });

          // PR #42 partial port (5/5): only auto-play when caller opts in via
          // `autoPlayResponseAudio: true`. Default false — ChatPanel relies
          // on gateway `/tts` events for playback, so auto-play here would
          // cause double-playback / echo. Errors swallowed to avoid
          // disrupting the recording UX.
          if (autoPlayResponseAudio && audioUrl) {
            const audio = new Audio(audioUrl);
            audio.play().catch((e) => {
              console.warn("[useAudioRecorder] auto-play failed:", e);
            });
          }
        }
      } catch {
        setError("回應格式錯誤");
      }
      setIsProcessing(false);
      ws.close();
    };

    ws.onerror = () => {
      setError("語音連線失敗");
      setIsProcessing(false);
    };

    ws.onclose = () => {
      wsRef.current = null;
    };
  }, [autoPlayResponseAudio]);

  const startRecording = useCallback(async () => {
    setError(null);
    setLastResult(null);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const mimeType = getPreferredMimeType();
      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);

      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = () => {
        // Stop all tracks + audio analysis
        stream.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
        cleanupAudioAnalysis();

        // Check minimum duration
        const elapsed = Date.now() - startTimeRef.current;
        if (elapsed < MIN_RECORD_MS) {
          setError("錄音太短，請至少說 0.5 秒");
          return;
        }

        const blob = new Blob(chunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });
        chunksRef.current = [];

        if (blob.size === 0) {
          setError("錄音為空");
          return;
        }

        sendAudio(blob);
      };

      startTimeRef.current = Date.now();
      recorder.start();
      mediaRecorderRef.current = recorder;
      setIsRecording(true);

      // Audio visualization via AnalyserNode
      try {
        const audioCtx = new AudioContext();
        const sourceNode = audioCtx.createMediaStreamSource(stream);
        const analyser = audioCtx.createAnalyser();
        analyser.fftSize = 256;
        sourceNode.connect(analyser);
        audioCtxRef.current = audioCtx;

        const dataArray = new Uint8Array(analyser.frequencyBinCount);
        const BINS = 7;

        const updateLevels = () => {
          analyser.getByteFrequencyData(dataArray);
          const levels: number[] = [];
          for (let i = 0; i < BINS; i++) {
            levels.push(dataArray[i] / 255);
          }
          setAudioLevels(levels);
          animFrameRef.current = requestAnimationFrame(updateLevels);
        };
        animFrameRef.current = requestAnimationFrame(updateLevels);
      } catch {
        // AudioContext not available — audioLevels stays empty (fallback pulse)
      }
    } catch (err) {
      setError("無法存取麥克風");
      console.error("getUserMedia error:", err);
    }
  }, [sendAudio, cleanupAudioAnalysis]);

  const stopRecording = useCallback(() => {
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      recorder.stop();
    }
    mediaRecorderRef.current = null;
    setIsRecording(false);
  }, []);

  return { isRecording, isProcessing, audioLevels, lastResult, error, startRecording, stopRecording };
}

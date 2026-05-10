"use client";

import type { KeyboardEvent, RefObject } from "react";
import { ArrowUp, Mic, Square } from "lucide-react";
import { AudioVisualizer } from "@/components/chat/audio-visualizer";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

export interface ComposerProps {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  onKeyDown: (e: KeyboardEvent<HTMLTextAreaElement>) => void;
  textareaRef: RefObject<HTMLTextAreaElement | null>;
  isThinking: boolean;
  isRecording: boolean;
  isProcessing: boolean;
  audioLevels: number[];
  startRecording: () => void;
  stopRecording: () => void;
  voiceError: string | null;
}

export function Composer({
  value,
  onChange,
  onSend,
  onKeyDown,
  textareaRef,
  isThinking,
  isRecording,
  isProcessing,
  audioLevels,
  startRecording,
  stopRecording,
  voiceError,
}: ComposerProps) {
  return (
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
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
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
        onClick={onSend}
        disabled={isThinking || isRecording || !value.trim()}
        size="icon"
        title="傳送"
        aria-label="傳送訊息"
        className={cn(
          "absolute right-2 bottom-2 h-9 w-9 rounded-lg transition-all duration-200",
          value.trim() && !isRecording
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
}

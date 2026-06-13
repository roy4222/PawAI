"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  Archive,
  ArrowLeft,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  FileJson,
  GitBranch,
  Radio,
  RefreshCw,
  X,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import type { BrainTraceEvent } from "@/contracts/types";
import { GateChip } from "@/components/shared/gate-chip";
import { useEventStream } from "@/hooks/use-event-stream";
import { getGatewayHttpUrl } from "@/lib/gateway-url";
import { buildTimeline, type TraceGroup, verdictTone } from "@/lib/trace-timeline";
import { gateZh, reasonZh } from "@/lib/trace-zh";
import { cn } from "@/lib/utils";
import { useStateStore } from "@/stores/state-store";

const TRACE_EVENT_CAP = 2000;

type Mode = "live" | "history";
type Tone = ReturnType<typeof verdictTone>;

type TraceSession = {
  session_id: string;
  started_ts: number;
  line_count: number;
  file_size: number;
  parts: string[];
};

type DisplayLabel = {
  title: string;
  code: string | null;
};

const TONE_CLASS: Record<Tone, string> = {
  accepted: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
  suppressed: "bg-amber-500/20 text-amber-300 border-amber-500/40",
  blocked: "bg-rose-500/20 text-rose-300 border-rose-500/40",
  shadow: "bg-violet-500/20 text-violet-300 border-violet-500/40",
};

const TONE_ICON: Record<Tone, LucideIcon> = {
  accepted: CheckCircle2,
  suppressed: AlertTriangle,
  blocked: XCircle,
  shadow: GitBranch,
};

function splitDisplayLabel(raw: string, localized: string): DisplayLabel {
  const suffix = `（${raw}）`;
  if (localized !== raw && localized.endsWith(suffix)) {
    return { title: localized.slice(0, -suffix.length), code: raw };
  }
  return { title: localized || raw || "(empty)", code: null };
}

function formatTimestamp(ts: number): string {
  if (!Number.isFinite(ts)) return "unknown";
  const ms = ts > 1_000_000_000_000 ? ts : ts * 1000;
  return new Date(ms).toLocaleString("zh-TW", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}

function representativeEvent(group: TraceGroup): BrainTraceEvent {
  return (
    group.events.find((event) => event.kind === "policy_decision") ??
    group.events[group.events.length - 1]
  );
}

function safeJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function isBrainTraceEvent(value: unknown): value is BrainTraceEvent {
  if (typeof value !== "object" || value === null) return false;
  const event = value as Partial<BrainTraceEvent>;
  return (
    typeof event.v === "number" &&
    typeof event.ts === "number" &&
    typeof event.decision_id === "string" &&
    typeof event.node === "string" &&
    typeof event.kind === "string" &&
    typeof event.verdict === "string" &&
    typeof event.gate === "string" &&
    typeof event.reason === "string" &&
    typeof event.detail === "object" &&
    event.detail !== null
  );
}

function appendCapped(events: BrainTraceEvent[], event: BrainTraceEvent): void {
  events.push(event);
  if (events.length > TRACE_EVENT_CAP * 2) {
    events.splice(0, events.length - TRACE_EVENT_CAP);
  }
}

function parseTraceLine(line: string): BrainTraceEvent | null {
  const trimmed = line.trim();
  if (!trimmed) return null;
  try {
    const parsed: unknown = JSON.parse(trimmed);
    return isBrainTraceEvent(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

async function parseTraceNdjson(response: Response): Promise<BrainTraceEvent[]> {
  const events: BrainTraceEvent[] = [];
  const reader = response.body?.getReader();

  if (!reader) {
    const text = await response.text();
    for (const line of text.split(/\r?\n/)) {
      const event = parseTraceLine(line);
      if (event) appendCapped(events, event);
    }
    return events.slice(-TRACE_EVENT_CAP);
  }

  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split(/\r?\n/);
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      const event = parseTraceLine(line);
      if (event) appendCapped(events, event);
    }
  }

  buffer += decoder.decode();
  const finalEvent = parseTraceLine(buffer);
  if (finalEvent) appendCapped(events, finalEvent);
  return events.slice(-TRACE_EVENT_CAP);
}

function DisplayCode({ label }: { label: DisplayLabel }) {
  return (
    <span className="inline-flex min-w-0 flex-col leading-tight">
      <span className="truncate">{label.title}</span>
      {label.code && (
        <span className="truncate font-mono text-[10px] opacity-60">{label.code}</span>
      )}
    </span>
  );
}

function VerdictBadge({ verdict, hasShadow }: { verdict: string; hasShadow?: boolean }) {
  const tone = verdictTone(verdict, hasShadow);
  const Icon = TONE_ICON[tone];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded border px-2 py-0.5 text-[11px] font-medium",
        TONE_CLASS[tone]
      )}
    >
      <Icon className="h-3 w-3" />
      {tone === "shadow" ? "shadow" : verdict}
    </span>
  );
}

function ModeButton({
  mode,
  activeMode,
  onClick,
  icon: Icon,
  children,
}: {
  mode: Mode;
  activeMode: Mode;
  onClick: (mode: Mode) => void;
  icon: LucideIcon;
  children: React.ReactNode;
}) {
  const active = mode === activeMode;
  return (
    <button
      type="button"
      onClick={() => onClick(mode)}
      className={cn(
        "inline-flex h-9 items-center gap-2 rounded-md border px-3 text-sm transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/60",
        active
          ? "border-sky-400/40 bg-sky-500/15 text-sky-200"
          : "border-border bg-background text-muted-foreground hover:bg-muted hover:text-foreground"
      )}
      aria-pressed={active}
    >
      <Icon className="h-4 w-4" />
      {children}
    </button>
  );
}

function TimelineEvent({
  event,
  index,
  selected,
  onSelect,
}: {
  event: BrainTraceEvent;
  index: number;
  selected: boolean;
  onSelect: (event: BrainTraceEvent) => void;
}) {
  const gateLabel = splitDisplayLabel(event.gate, gateZh(event.gate));
  const reasonLabel = splitDisplayLabel(event.reason, reasonZh(event.reason));

  return (
    <button
      type="button"
      onClick={() => onSelect(event)}
      className={cn(
        "w-full rounded-md border p-3 text-left transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/60",
        selected
          ? "border-sky-400/50 bg-sky-500/10"
          : "border-border/70 bg-muted/20 hover:border-border hover:bg-muted/40"
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <span className="font-mono text-[10px] text-muted-foreground">
            #{index + 1}
          </span>
          <span className="rounded border border-slate-500/40 bg-slate-500/10 px-1.5 py-0.5 font-mono text-[10px] text-slate-300">
            {event.kind}
          </span>
          <VerdictBadge verdict={event.verdict} hasShadow={event.gate === "ism_shadow"} />
        </div>
        <span className="font-mono text-[10px] text-muted-foreground">
          {formatTimestamp(event.ts)}
        </span>
      </div>

      <div className="mt-2 grid gap-2 md:grid-cols-[180px_minmax(0,1fr)]">
        <div
          className="rounded border border-border/60 bg-background/40 px-2 py-1 text-xs text-foreground"
          title={event.gate}
        >
          <DisplayCode label={gateLabel} />
        </div>
        <div
          className="rounded border border-border/60 bg-background/40 px-2 py-1 text-xs text-muted-foreground"
          title={event.reason}
        >
          <DisplayCode label={reasonLabel} />
        </div>
      </div>

      <pre className="mt-2 max-h-44 overflow-auto whitespace-pre-wrap break-words rounded-md border border-border/60 bg-background/60 p-2 font-mono text-[11px] leading-relaxed text-muted-foreground">
        {safeJson(event.detail)}
      </pre>
    </button>
  );
}

function TimelineGroup({
  group,
  open,
  selectedEvent,
  onToggle,
  onSelectEvent,
}: {
  group: TraceGroup;
  open: boolean;
  selectedEvent: BrainTraceEvent | null;
  onToggle: () => void;
  onSelectEvent: (event: BrainTraceEvent) => void;
}) {
  const representative = representativeEvent(group);
  const reasonLabel = splitDisplayLabel(representative.reason, reasonZh(representative.reason));

  return (
    <section className="rounded-lg border border-border bg-card/70">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-start gap-3 p-3 text-left transition-colors hover:bg-muted/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/60"
      >
        <span className="mt-1 text-muted-foreground">
          {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className="font-mono text-sm font-semibold text-foreground"
              title={group.decisionId}
            >
              {group.decisionId.slice(0, 8)}
            </span>
            <VerdictBadge verdict={group.verdict} hasShadow={group.hasShadow} />
            <span className="font-mono text-[10px] text-muted-foreground">
              {group.events.length} events
            </span>
            <span className="font-mono text-[10px] text-muted-foreground">
              {formatTimestamp(group.firstTs)} - {formatTimestamp(group.lastTs)}
            </span>
          </div>

          <div className="mt-2 flex flex-wrap gap-1.5">
            {group.gates.map((gate) => (
              <span
                key={gate}
                className={cn(
                  "inline-flex max-w-[220px] rounded border px-2 py-1 text-xs",
                  gate === "ism_shadow"
                    ? "border-violet-500/40 bg-violet-500/10 text-violet-300"
                    : "border-slate-500/30 bg-slate-500/10 text-slate-300"
                )}
                title={gate}
              >
                <DisplayCode label={splitDisplayLabel(gate, gateZh(gate))} />
              </span>
            ))}
          </div>

          <div className="mt-2 max-w-full rounded border border-border/60 bg-background/40 px-2 py-1 text-xs text-muted-foreground">
            <DisplayCode label={reasonLabel} />
          </div>
        </div>
      </button>

      {open && (
        <div className="space-y-2 border-t border-border/70 p-3">
          {group.events.map((event, index) => (
            <TimelineEvent
              key={`${event.decision_id}-${event.ts}-${event.kind}-${index}`}
              event={event}
              index={index}
              selected={selectedEvent === event}
              onSelect={onSelectEvent}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function DetailPanel({
  event,
  onClose,
}: {
  event: BrainTraceEvent | null;
  onClose: () => void;
}) {
  return (
    <aside className="flex min-h-0 flex-col rounded-lg border border-border bg-card">
      <div className="flex h-12 items-center justify-between border-b border-border px-3">
        <div className="flex items-center gap-2">
          <FileJson className="h-4 w-4 text-sky-300" />
          <h2 className="text-sm font-semibold">Detail</h2>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/60"
          aria-label="Close detail"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {event ? (
        <div className="min-h-0 flex-1 overflow-auto p-3">
          <div className="space-y-2 text-xs">
            {[
              ["decision_id", event.decision_id],
              ["node", event.node],
              ["kind", event.kind],
              ["verdict", event.verdict],
              ["gate", event.gate],
              ["reason", event.reason],
              ["ts", String(event.ts)],
              ["plan_id", event.plan_id ?? ""],
            ].map(([key, value]) => (
              <div key={key} className="grid grid-cols-[92px_minmax(0,1fr)] gap-2">
                <span className="font-mono text-muted-foreground">{key}</span>
                <span className="min-w-0 break-words font-mono text-foreground">{value}</span>
              </div>
            ))}
          </div>
          <pre className="mt-3 min-h-[240px] whitespace-pre-wrap break-words rounded-md border border-border bg-background p-3 font-mono text-[11px] leading-relaxed text-muted-foreground">
            {safeJson(event.detail)}
          </pre>
        </div>
      ) : (
        <div className="flex flex-1 items-center justify-center p-6 text-center text-sm text-muted-foreground">
          Select an event
        </div>
      )}
    </aside>
  );
}

export default function EvidencePage() {
  const { isConnected } = useEventStream();
  const brainTraces = useStateStore((state) => state.brainTraces);
  const [mode, setMode] = useState<Mode>("live");
  const [sessions, setSessions] = useState<TraceSession[]>([]);
  const [selectedSession, setSelectedSession] = useState("");
  const [historyEvents, setHistoryEvents] = useState<BrainTraceEvent[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [openGroups, setOpenGroups] = useState<Set<string>>(new Set());
  const [selectedEvent, setSelectedEvent] = useState<BrainTraceEvent | null>(null);

  const loadSessions = useCallback(async () => {
    setSessionsLoading(true);
    setError(null);
    try {
      const response = await fetch(`${getGatewayHttpUrl()}/api/trace/sessions`);
      if (!response.ok) {
        throw new Error(`sessions ${response.status}`);
      }
      const payload = (await response.json()) as { sessions?: TraceSession[] };
      setSessions(payload.sessions ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "failed to load sessions");
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    if (mode === "history" && !selectedSession && sessions[0]) {
      setSelectedSession(sessions[0].session_id);
    }
  }, [mode, selectedSession, sessions]);

  useEffect(() => {
    if (mode !== "history" || !selectedSession) return;

    const controller = new AbortController();
    setHistoryLoading(true);
    setError(null);
    setSelectedEvent(null);

    async function loadHistory() {
      try {
        const url = `${getGatewayHttpUrl()}/api/trace/export?session=${encodeURIComponent(
          selectedSession
        )}`;
        const response = await fetch(url, { signal: controller.signal });
        if (!response.ok) {
          throw new Error(`export ${response.status}`);
        }
        const events = await parseTraceNdjson(response);
        setHistoryEvents(events);
      } catch (err) {
        if (!controller.signal.aborted) {
          setHistoryEvents([]);
          setError(err instanceof Error ? err.message : "failed to load history");
        }
      } finally {
        if (!controller.signal.aborted) {
          setHistoryLoading(false);
        }
      }
    }

    void loadHistory();
    return () => controller.abort();
  }, [mode, selectedSession]);

  const sourceEvents = mode === "live" ? brainTraces : historyEvents;
  const timeline = useMemo(
    () => buildTimeline(sourceEvents, { cap: TRACE_EVENT_CAP }),
    [sourceEvents]
  );
  const shownEventCount = timeline.reduce((total, group) => total + group.events.length, 0);
  const selectedSessionMeta = sessions.find((session) => session.session_id === selectedSession);

  const toggleGroup = useCallback((decisionId: string) => {
    setOpenGroups((current) => {
      const next = new Set(current);
      if (next.has(decisionId)) {
        next.delete(decisionId);
      } else {
        next.add(decisionId);
      }
      return next;
    });
  }, []);

  return (
    <div className="flex h-screen flex-col bg-background text-foreground">
      <header className="flex h-12 shrink-0 items-center justify-between border-b border-[var(--nav-border)] px-4 md:px-5">
        <div className="flex min-w-0 items-center gap-3">
          <Link
            href="/studio"
            className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/60"
            aria-label="Back to Studio"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div className="min-w-0">
            <h1 className="truncate text-sm font-semibold">Evidence Center</h1>
            <p className="truncate font-mono text-[10px] text-muted-foreground">
              /studio/evidence
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <GateChip name="WS" value={isConnected ? "true" : "false"} />
          <button
            type="button"
            onClick={() => void loadSessions()}
            disabled={sessionsLoading}
            className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/60"
            aria-label="Refresh sessions"
            title="Refresh sessions"
          >
            <RefreshCw className={cn("h-4 w-4", sessionsLoading && "animate-spin")} />
          </button>
        </div>
      </header>

      <main className="grid min-h-0 flex-1 gap-4 p-4 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="flex min-h-0 flex-col gap-4">
          <section className="rounded-lg border border-border bg-card p-3">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
              <div className="flex flex-wrap gap-2">
                <ModeButton mode="live" activeMode={mode} onClick={setMode} icon={Radio}>
                  Live
                </ModeButton>
                <ModeButton mode="history" activeMode={mode} onClick={setMode} icon={Archive}>
                  History
                </ModeButton>
              </div>

              <div className="grid gap-1.5 lg:min-w-[340px]">
                <label htmlFor="trace-session" className="text-[11px] text-muted-foreground">
                  Session
                </label>
                <select
                  id="trace-session"
                  value={selectedSession}
                  onChange={(event) => {
                    setSelectedSession(event.target.value);
                    setMode("history");
                  }}
                  disabled={sessionsLoading || sessions.length === 0}
                  className="h-9 rounded-md border border-border bg-background px-3 text-sm text-foreground outline-none focus:ring-2 focus:ring-sky-400/60 disabled:opacity-50"
                >
                  <option value="">
                    {sessionsLoading ? "loading..." : "no sessions"}
                  </option>
                  {sessions.map((session) => (
                    <option key={session.session_id} value={session.session_id}>
                      {session.session_id} · {session.line_count} events
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-muted-foreground">
              <span className="rounded border border-border bg-background px-2 py-1 font-mono">
                groups={timeline.length}
              </span>
              <span className="rounded border border-border bg-background px-2 py-1 font-mono">
                events={shownEventCount}/{sourceEvents.length}
              </span>
              <span className="rounded border border-border bg-background px-2 py-1 font-mono">
                cap={TRACE_EVENT_CAP}
              </span>
              {selectedSessionMeta && (
                <>
                  <span className="rounded border border-border bg-background px-2 py-1 font-mono">
                    file={formatBytes(selectedSessionMeta.file_size)}
                  </span>
                  <span className="rounded border border-border bg-background px-2 py-1 font-mono">
                    parts={selectedSessionMeta.parts.length}
                  </span>
                </>
              )}
              {historyLoading && (
                <span className="rounded border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-amber-300">
                  loading history
                </span>
              )}
              {error && (
                <span className="rounded border border-rose-500/30 bg-rose-500/10 px-2 py-1 text-rose-300">
                  {error}
                </span>
              )}
            </div>
          </section>

          <div className="min-h-0 flex-1 overflow-auto">
            <div className="space-y-3 pb-3">
              {timeline.length === 0 ? (
                <div className="flex min-h-[240px] items-center justify-center rounded-lg border border-dashed border-border bg-card/50 p-6 text-center text-sm text-muted-foreground">
                  {mode === "live" ? "No live trace events" : "No history trace events"}
                </div>
              ) : (
                timeline.map((group) => (
                  <TimelineGroup
                    key={group.decisionId}
                    group={group}
                    open={openGroups.has(group.decisionId)}
                    selectedEvent={selectedEvent}
                    onToggle={() => toggleGroup(group.decisionId)}
                    onSelectEvent={setSelectedEvent}
                  />
                ))
              )}
            </div>
          </div>
        </div>

        <DetailPanel event={selectedEvent} onClose={() => setSelectedEvent(null)} />
      </main>
    </div>
  );
}

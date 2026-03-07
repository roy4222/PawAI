"use client";

import { useEffect, useMemo, useState } from "react";

type EnrollStatus = {
  running: boolean;
  pid: number | null;
  saved: number;
  total: number;
  logs: string[];
  guidance: string;
};

type InferStatus = {
  running: boolean;
  pid: number | null;
  logs: string[];
};

type Person = { name: string; samples: number };

type ModelProfile = {
  id: string;
  label: string;
  description: string;
};

type StatusPayload = {
  enroll: EnrollStatus;
  infer: InferStatus;
  people: Person[];
  selected_profile: ModelProfile;
  profiles: ModelProfile[];
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://192.168.0.222:8000";

export default function Page() {
  const [personName, setPersonName] = useState("alice");
  const [samples, setSamples] = useState(30);
  const [intervalSec, setIntervalSec] = useState(0.35);
  const [statusText, setStatusText] = useState("idle");
  const [selectedProfileId, setSelectedProfileId] = useState("yunet_sface_fp32");
  const [busyEnrollStart, setBusyEnrollStart] = useState(false);
  const [busyEnrollStop, setBusyEnrollStop] = useState(false);
  const [busyInferStart, setBusyInferStart] = useState(false);
  const [busyInferStop, setBusyInferStop] = useState(false);
  const [busyProfileSelect, setBusyProfileSelect] = useState(false);
  const [data, setData] = useState<StatusPayload | null>(null);

  const host = useMemo(() => {
    if (typeof window === "undefined") return "192.168.0.222";
    return window.location.hostname;
  }, []);

  const liveColor = `http://${host}:8081/stream?topic=/camera/camera/color/image_raw&quality=70`;
  const liveEnroll = `http://${host}:8081/stream?topic=/face_enroll/debug_image&quality=70`;
  const liveInfer = `http://${host}:8081/stream?topic=/face_identity/compare_image&quality=70`;

  const enrollSrc = data?.enroll.running ? liveEnroll : liveColor;
  const inferSrc = data?.infer.running ? liveInfer : liveColor;
  const progress = data?.enroll.total ? Math.min(100, Math.round((data.enroll.saved * 100) / data.enroll.total)) : 0;

  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/status`, { cache: "no-store" });
        if (!res.ok) throw new Error(`status ${res.status}`);
        const payload = (await res.json()) as StatusPayload;
        setData(payload);
        setSelectedProfileId(payload.selected_profile.id);
        const enrollState = payload.enroll.running ? `enroll running pid=${payload.enroll.pid}` : "enroll idle";
        const inferState = payload.infer.running ? `infer running pid=${payload.infer.pid}` : "infer idle";
        setStatusText(`${payload.selected_profile.label} | ${enrollState} | ${inferState}`);
      } catch {
        setStatusText("connection issue: retrying...");
      }
    };

    poll();
    const t = setInterval(poll, 1000);
    return () => clearInterval(t);
  }, []);

  const startEnroll = async () => {
    setBusyEnrollStart(true);
    setStatusText("starting enroll...");
    try {
      const res = await fetch(`${API_BASE}/api/enroll/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          person_name: personName,
          samples,
          interval: intervalSec,
          profile_id: selectedProfileId,
        }),
      });
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || "start enroll failed");
      }
      setStatusText("enroll started");
    } catch (e) {
      setStatusText("start enroll failed");
      alert(String(e));
    } finally {
      setBusyEnrollStart(false);
    }
  };

  const stopEnroll = async () => {
    setBusyEnrollStop(true);
    try {
      await fetch(`${API_BASE}/api/enroll/stop`, { method: "POST" });
      setStatusText("enroll stop requested");
    } finally {
      setBusyEnrollStop(false);
    }
  };

  const startInfer = async () => {
    setBusyInferStart(true);
    setStatusText("starting demo...");
    try {
      const res = await fetch(`${API_BASE}/api/infer/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile_id: selectedProfileId }),
      });
      if (!res.ok) throw new Error(await res.text());
      setStatusText("demo started");
    } catch (e) {
      setStatusText("start demo failed");
      alert(String(e));
    } finally {
      setBusyInferStart(false);
    }
  };

  const stopInfer = async () => {
    setBusyInferStop(true);
    try {
      await fetch(`${API_BASE}/api/infer/stop`, { method: "POST" });
      setStatusText("demo stop requested");
    } finally {
      setBusyInferStop(false);
    }
  };

  const applyProfile = async () => {
    setBusyProfileSelect(true);
    setStatusText("switching model profile...");
    try {
      const res = await fetch(`${API_BASE}/api/model/select`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile_id: selectedProfileId }),
      });
      if (!res.ok) throw new Error(await res.text());
      setStatusText(`profile switched: ${selectedProfileId}`);
    } catch (e) {
      setStatusText("switch profile failed");
      alert(String(e));
    } finally {
      setBusyProfileSelect(false);
    }
  };

  return (
    <main className="wrap">
      <h1>Face Dashboard (Next.js + FastAPI)</h1>
      <p>Multi-person enrollment and demo with live stream preview.</p>

      <div className="grid">
        <section className="card">
          <h3>Scan Setup</h3>
          <label>Person Name</label>
          <input value={personName} onChange={(e) => setPersonName(e.target.value)} />
          <label>Model Profile</label>
          <div className="row">
            <select value={selectedProfileId} onChange={(e) => setSelectedProfileId(e.target.value)}>
              {(data?.profiles ?? []).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </select>
            <button className="primary" disabled={busyProfileSelect} onClick={applyProfile}>
              {busyProfileSelect ? "Applying..." : "Apply Profile"}
            </button>
          </div>
          <div>{data?.selected_profile.description ?? ""}</div>
          <div className="row">
            <div>
              <label>Samples</label>
              <input
                type="number"
                value={samples}
                onChange={(e) => setSamples(Number(e.target.value))}
              />
            </div>
            <div>
              <label>Interval (sec)</label>
              <input
                type="number"
                step="0.05"
                value={intervalSec}
                onChange={(e) => setIntervalSec(Number(e.target.value))}
              />
            </div>
          </div>

          <div className="actions">
            <button className="primary" disabled={busyEnrollStart} onClick={startEnroll}>
              {busyEnrollStart ? "Starting..." : "Start Scan"}
            </button>
            <button className="danger" disabled={busyEnrollStop} onClick={stopEnroll}>
              {busyEnrollStop ? "Stopping..." : "Stop Scan"}
            </button>
            <button className="primary" disabled={busyInferStart} onClick={startInfer}>
              {busyInferStart ? "Starting Demo..." : "Start Recognition Demo"}
            </button>
            <button className="danger" disabled={busyInferStop} onClick={stopInfer}>
              {busyInferStop ? "Stopping Demo..." : "Stop Demo"}
            </button>
          </div>

          <div className="status">{statusText}</div>
        </section>

        <section className="card">
          <h3>Capture Progress</h3>
          <div>
            {data?.enroll.saved ?? 0} / {data?.enroll.total ?? 0}
          </div>
          <div className="bar">
            <div style={{ width: `${progress}%` }} />
          </div>
          <div>{data?.enroll.guidance ?? "Enter setup and press Start Scan."}</div>
        </section>

        <section className="card">
          <h3>Registered People</h3>
          {(data?.people ?? []).map((p) => (
            <div key={p.name}>
              {p.name} ({p.samples})
            </div>
          ))}
        </section>

        <section className="card">
          <h3>Enrollment Preview</h3>
          <img className="preview" src={enrollSrc} alt="enroll-preview" />
        </section>

        <section className="card">
          <h3>Recognition Preview</h3>
          <img className="preview" src={inferSrc} alt="infer-preview" />
        </section>

        <section className="card">
          <h3>Enrollment Logs</h3>
          <pre>{(data?.enroll.logs ?? []).join("\n")}</pre>
        </section>

        <section className="card">
          <h3>Inference Logs</h3>
          <pre>{(data?.infer.logs ?? []).join("\n")}</pre>
        </section>
      </div>
    </main>
  );
}

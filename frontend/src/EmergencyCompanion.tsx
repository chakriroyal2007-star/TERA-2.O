import { FormEvent, useEffect, useRef, useState } from "react";
import { Bot, CheckCircle2, ChevronRight, CircleAlert, Globe2, Mic, MicOff, PhoneCall, Play, RotateCcw, Send, Square, VolumeX, X } from "lucide-react";
import { api } from "./api";
import { ErrorBox } from "./components";

export interface CompanionProps { incidentId?: string; trackingCode?: string; initialCategory?: string; initialLanguage?: string; onClose?: () => void; }
type Language = "en" | "te" | "hi" | "ta" | "kn" | "ml";
type ChatMessage = { id: string; speaker: "ai" | "citizen" | "system" | "operator"; content: string };
type Action = { step_number: number; instruction: string; completed: boolean };
type CompanionData = { session_id: string; incident: { case_id: string; category: string; address?: string }; language: Language; status: string; urgency: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"; risk_assessment: string; messages: ChatMessage[]; actions: Action[]; video?: any; audio_base64?: string | null; resumed?: boolean; requires_human_escalation?: boolean };

const languages: Array<[Language, string]> = [["en", "English"], ["te", "తెలుగు"], ["hi", "हिन्दी"], ["ta", "தமிழ்"], ["kn", "ಕನ್ನಡ"], ["ml", "മലയാളം"]];
const priorityColor: Record<string, string> = { CRITICAL: "#ef4444", HIGH: "#f97316", MEDIUM: "#eab308", LOW: "#22c55e" };

export function EmergencyCompanion({ incidentId, trackingCode, initialLanguage = "en", onClose }: CompanionProps) {
  const [language, setLanguage] = useState<Language>(initialLanguage as Language);
  const [data, setData] = useState<CompanionData | null>(null);
  const [text, setText] = useState("");
  const [phase, setPhase] = useState<"connecting" | "listening" | "thinking" | "speaking" | "waiting">("connecting");
  const [busy, setBusy] = useState(false); const [muted, setMuted] = useState(false);
  const [error, setError] = useState<unknown>(null); const [recording, setRecording] = useState(false);
  const [liveTranscript, setLiveTranscript] = useState(""); const [showEscalated, setShowEscalated] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null); const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null); const transcriptEnd = useRef<HTMLDivElement | null>(null);

  const stopAudio = () => { if (audioRef.current) { audioRef.current.pause(); audioRef.current.currentTime = 0; } setPhase("waiting"); };
  const playAudio = (audio?: string | null) => {
    if (!audio || muted) { setPhase("waiting"); return; }
    stopAudio(); const player = new Audio(`data:audio/wav;base64,${audio}`); audioRef.current = player;
    player.onplay = () => setPhase("speaking"); player.onended = () => setPhase("waiting"); player.onerror = () => setPhase("waiting");
    player.play().catch(() => setPhase("waiting"));
  };
  const start = async (selectedLanguage = language) => {
    if (!incidentId && !trackingCode) { setError(new Error("Launch the AI Companion from a submitted emergency report so it can use the real incident details.")); return; }
    setBusy(true); setError(null); setPhase("connecting");
    try {
      const result = await api<CompanionData>("/companion/start", "POST", { incident_id: incidentId, tracking_code: trackingCode, language: selectedLanguage });
      setData(result); setShowEscalated(result.status === "escalation_required"); setPhase("waiting"); if (!result.resumed) playAudio(result.audio_base64);
    } catch (err) { setError(err); setPhase("waiting"); } finally { setBusy(false); }
  };
  useEffect(() => { start(); return () => { stopAudio(); streamRef.current?.getTracks().forEach((track) => track.stop()); }; }, []);
  useEffect(() => { transcriptEnd.current?.scrollIntoView({ behavior: "smooth" }); }, [data?.messages.length, phase]);

  const send = async (message = text) => {
    const clean = message.trim(); if (!clean || !data || busy) return;
    stopAudio(); setBusy(true); setError(null); setPhase("thinking"); const citizen: ChatMessage = { id: `local-${Date.now()}`, speaker: "citizen", content: clean };
    setData((previous) => previous ? { ...previous, messages: [...previous.messages, citizen] } : previous); setText(""); setLiveTranscript("");
    try {
      const result = await api<any>("/companion/chat", "POST", { session_id: data.session_id, message: clean, language });
      const reply = `${result.message || ""}${result.follow_up_question ? `\n\n${result.follow_up_question}` : ""}`.trim();
      setData((previous) => previous ? { ...previous, urgency: result.urgency, risk_assessment: result.risk_assessment, actions: result.actions || previous.actions, video: result.video || previous.video, status: result.requires_human_escalation ? "escalation_required" : previous.status, messages: [...previous.messages, { id: `ai-${Date.now()}`, speaker: "ai", content: reply }] } : previous);
      if (result.requires_human_escalation) setShowEscalated(true); playAudio(result.audio_base64);
    } catch (err) { setError(err); setPhase("waiting"); } finally { setBusy(false); }
  };

  const toggleRecording = async () => {
    if (recording) { recorderRef.current?.stop(); return; }
    stopAudio(); setError(null); setLiveTranscript("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true }); streamRef.current = stream; const recorder = new MediaRecorder(stream); const chunks: Blob[] = [];
      recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
      recorder.onstop = async () => { setRecording(false); stream.getTracks().forEach((track) => track.stop()); setPhase("thinking"); setBusy(true);
        try { const form = new FormData(); form.append("file", new Blob(chunks, { type: recorder.mimeType || "audio/webm" }), "emergency-response.webm"); form.append("language", language); const response = await api<{ transcript: string; error?: string }>("/companion/transcribe", "POST", form); if (response.error || !response.transcript) throw new Error(response.error || "We could not understand that recording. Please try again or type your response."); setLiveTranscript(response.transcript); await send(response.transcript); }
        catch (err) { setError(err); setPhase("waiting"); } finally { setBusy(false); } };
      recorder.start(); recorderRef.current = recorder; setRecording(true); setPhase("listening");
    } catch { setError(new Error("Microphone access was not granted. You can continue safely using the text input.")); setPhase("waiting"); }
  };
  const toggleAction = async (action: Action) => { if (!data) return; const completed = !action.completed; const old = data.actions; setData({ ...data, actions: old.map((item) => item.step_number === action.step_number ? { ...item, completed } : item) }); try { await api("/companion/actions/toggle", "POST", { session_id: data.session_id, step_number: action.step_number, completed }); } catch (err) { setError(err); setData({ ...data, actions: old }); } };
  const requestHuman = async () => { if (!data) return; setBusy(true); try { await api(`/companion/sessions/${data.session_id}/escalate`, "POST", {}); setShowEscalated(true); } catch (err) { setError(err); } finally { setBusy(false); } };
  const replay = () => { const last = [...(data?.messages || [])].reverse().find((message) => message.speaker === "ai"); if (last) api<any>("/companion/speech", "POST", { text: last.content, language }).then((result) => playAudio(result.audio_base64)).catch(setError); };
  const phaseText = { connecting: "Connecting to secure emergency guidance…", listening: "Listening — speak clearly", thinking: "Assessing the situation…", speaking: "Speaking guidance…", waiting: "Waiting for your update" }[phase];

  return <div className="companion-shell" role="dialog" aria-modal="true" aria-label="TERA AI Emergency Companion">
    <header className="companion-header"><div><div className="companion-brand"><Bot size={22} /> TERA <span>AI Emergency Companion</span></div><small>{data ? `${data.incident.case_id} · ${data.incident.category.replaceAll("_", " ")}` : "Loading incident details"}</small></div><div className="companion-header-actions">{data && <span className="priority-pill" style={{ background: priorityColor[data.urgency] }}>{data.urgency}</span>}<label className="language-select"><Globe2 size={15} /><select value={language} onChange={(event) => { const next = event.target.value as Language; setLanguage(next); if (data) start(next); }}>{languages.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label><button className="icon-button" onClick={onClose} aria-label="End companion conversation"><X size={20} /></button></div></header>
    <div className="companion-grid"><main className="companion-conversation"><div className="companion-status" data-phase={phase}><span className="pulse-dot" /> {phaseText}<span className="wave-bars" aria-hidden="true"><i/><i/><i/><i/><i/></span></div><div className="companion-safety"><PhoneCall size={18}/><div><strong>Call 112 now for immediate danger.</strong><br/><small>TERA assists while you wait; it cannot confirm dispatch or replace emergency services.</small></div><button onClick={requestHuman} disabled={busy}>Request operator</button></div>{showEscalated && <div className="companion-escalated"><CircleAlert size={18}/><span>Human operator escalation has been requested and recorded for this incident.</span></div>}<ErrorBox error={error}/><section className="message-history" aria-live="polite">{(data?.messages || []).map((message) => <article className={`companion-message ${message.speaker}`} key={message.id}><strong>{message.speaker === "citizen" ? "You" : message.speaker === "operator" ? "Operator" : "TERA AI"}</strong><p>{message.content}</p></article>)}<div ref={transcriptEnd}/></section>{liveTranscript && <div className="live-transcript"><Mic size={15}/> Heard: {liveTranscript}</div>}<div className="companion-controls"><button className={`mic-button ${recording ? "recording" : ""}`} onClick={toggleRecording} disabled={busy} aria-label={recording ? "Stop recording" : "Start voice response"}>{recording ? <Square size={21}/> : <Mic size={23}/>}</button><form onSubmit={(event: FormEvent) => { event.preventDefault(); send(); }}><input value={text} onChange={(event) => setText(event.target.value)} disabled={busy} placeholder="Type an update or answer…" maxLength={5000}/><button type="submit" disabled={busy || !text.trim()} aria-label="Send message"><Send size={18}/></button></form><button className="icon-button" onClick={() => { setMuted(!muted); stopAudio(); }} aria-label={muted ? "Unmute" : "Mute"}>{muted ? <VolumeX size={19}/> : <MicOff size={19}/>}</button><button className="icon-button" onClick={replay} disabled={busy} aria-label="Replay last response"><RotateCcw size={19}/></button></div></main>
    <aside className="companion-guidance"><section className="video-card"><div className="side-label">Verified visual guidance</div>{data?.video ? <><div className="video-frame"><iframe src={data.video.embed_url} title={data.video.title} allow="encrypted-media; picture-in-picture" allowFullScreen /></div><h3>{data.video.title}</h3><p>{data.video.summary || data.video.description}</p>{data.video.watch_url && <a className="video-watch-link" href={data.video.watch_url} target="_blank" rel="noreferrer">Open video in YouTube</a>}<small>Source: {data.video.source} · Optional: do not wait to watch before taking urgent action.</small></> : <div className="video-empty"><Play size={30}/><h3>Guidance will appear when useful</h3><p>The companion only selects an approved video when it matches the reported emergency.</p></div>}</section><section className="checklist-card"><div className="side-label">Live action checklist</div>{data?.risk_assessment && <p className="risk-summary">{data.risk_assessment}</p>}{data?.actions.map((action) => <button className={`action-item ${action.completed ? "done" : ""}`} key={action.step_number} onClick={() => toggleAction(action)}>{action.completed ? <CheckCircle2 size={19}/> : <span className="action-number">{action.step_number}</span>}<span>{action.instruction}</span><ChevronRight size={16}/></button>)}</section></aside></div>
  </div>;
}

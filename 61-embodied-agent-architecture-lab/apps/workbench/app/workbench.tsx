"use client";

import { useEffect, useState } from "react";

type Interface = { name: string; owner: string; topic?: string; action?: string; frame: string; units: string; freshness_ms: number; deadline_ms: number; qos: { reliability: string; durability: string; depth: number }; result_codes: string[] };
type Overview = { summary: { count: number; outcomes: Record<string, number>; unsafe_motor_commands: number; all_terminal_manifests_valid: boolean; all_replays_equivalent: boolean }; profile: { operating_system: string; ros_distro: string; gazebo_distribution: string; status: string; base_image_digest: string }; catalog: { interfaces: Interface[] }; runs: string[] };
type Event = { sequence: number; sim_time_s: number; kind: string; name?: string; code?: string; reason?: string; mode?: string; entity_id?: string; allowed?: boolean; outcome?: string };
type RecordData = { sha256: string; payload: { scenario: { scenario_id: string; target_id: string; fault: string; seed: number }; outcome: string; reason: string; safety_mode: string; events: Event[]; score: { motor_commands: number; unsafe_motor_commands: number }; profile_sha256: string; clock_domain: string } };
type RosEvidence = { status: "verified" | "not_available"; clean_bringups?: number; image_id?: string; minimum_arm_samples_within_limits?: number; estop_to_recovery_zero_motion?: boolean; mission_event_sequence?: string };
type View = "System topology" | "TF & clock" | "Topic / QoS" | "World model" | "Goal & policy" | "Plan trace" | "Skill timeline" | "Safety & faults" | "Sensor / control latency" | "Replay & evidence";

const VIEWS: View[] = ["System topology", "TF & clock", "Topic / QoS", "World model", "Goal & policy", "Plan trace", "Skill timeline", "Safety & faults", "Sensor / control latency", "Replay & evidence"];
const LAYERS = ["Sensors", "Perception", "World model", "Goal gateway", "Executive", "Skill registry", "Control gateway", "Safety supervisor", "Evidence"];

function badge(value: string) { return <span className={`badge ${value === "SUCCESS" || value === "OK" ? "good" : value === "DENIED" ? "warn" : "stopped"}`}>{value}</span>; }

export default function Workbench() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [selected, setSelected] = useState("mission-000");
  const [run, setRun] = useState<RecordData | null>(null);
  const [rosEvidence, setRosEvidence] = useState<RosEvidence | null>(null);
  const [view, setView] = useState<View>("System topology");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetch("/api/overview").then(async r => { if (!r.ok) throw new Error("Local evidence API is unavailable"); return r.json(); }).then(setOverview).catch(e => setError(String(e)));
    fetch("/api/ros-evidence").then(async r => { if (!r.ok) throw new Error("ROS campaign evidence failed validation"); return r.json(); }).then(setRosEvidence).catch(e => setError(String(e)));
  }, []);
  useEffect(() => {
    fetch(`/api/runs/${selected}`).then(async r => { if (!r.ok) throw new Error("Run evidence is unavailable"); return r.json(); }).then(setRun).catch(e => setError(String(e)));
  }, [selected]);

  async function rerun() {
    setBusy(true); setError("");
    try {
      const response = await fetch("/api/missions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scenario_id: selected }) });
      if (!response.ok) throw new Error("Synthetic mission could not run");
      setRun(await response.json());
      setView("Replay & evidence");
    } catch (cause) { setError(String(cause)); } finally { setBusy(false); }
  }

  const events = run?.payload.events ?? [];
  const skillEvents = events.filter(e => e.kind === "skill");
  const safetyEvents = events.filter(e => e.kind === "safety" || e.kind === "safety_event" || e.kind === "fault");
  const percepts = events.filter(e => e.kind === "perception");

  return <div className="shell">
    <aside className="sidebar" aria-label="Workbench navigation">
      <div className="brand"><span className="brand-mark" aria-hidden="true">A</span><div><strong>ASTRA</strong><small>ARCHITECTURE WORKBENCH</small></div></div>
      <div className="sidebar-label">EVIDENCE SURFACES</div>
      <nav aria-label="Evidence surfaces">{VIEWS.map((item, index) => <button key={item} type="button" className={`nav-item ${view === item ? "active" : ""}`} aria-current={view === item ? "page" : undefined} onClick={() => setView(item)}><span>{String(index + 1).padStart(2, "0")}</span>{item}</button>)}</nav>
      <div className="sidebar-foot"><div className="status-dot"/> LOCAL SIMULATION <small>No physical motor control</small></div>
    </aside>

    <main className="main">
      <header className="topbar"><div><p className="eyebrow">PROJECT 61 / EMBODIED AI</p><h1>Mission architecture, made observable.</h1><p className="subtitle">A synthetic mobile manipulator, governed from goal intake to safe stop.</p></div><div className="topbar-right"><span className="profile-pill">LYRICAL · JETTY</span><span className="profile-pill muted">SIM CLOCK</span></div></header>
      {error && <div className="error" role="alert">{error}</div>}
      {!overview ? <div className="loading" role="status">Loading local mission evidence…</div> : <>
        <div className="metric-grid"><div className="metric"><span>Development runs</span><strong>{overview.summary.count}</strong><small>64 registered fixtures</small></div><div className="metric"><span>Successful missions</span><strong>{overview.summary.outcomes.SUCCESS ?? 0}</strong><small>Others stop or deny by design</small></div><div className="metric"><span>Unsafe commands</span><strong>{overview.summary.unsafe_motor_commands}</strong><small>Committed beyond safety gate</small></div><div className="metric"><span>Evidence integrity</span><strong>{overview.summary.all_terminal_manifests_valid && overview.summary.all_replays_equivalent ? "Verified" : "Review"}</strong><small>Terminal manifest + replay</small></div></div>
        <section className="control-strip" aria-label="Run selection"><div><label htmlFor="run-select">SELECT MISSION RUN</label><select id="run-select" value={selected} onChange={e => setSelected(e.target.value)}>{overview.runs.map(id => <option key={id} value={id}>{id}</option>)}</select></div><div className="run-state"><span>OUTCOME</span>{run ? badge(run.payload.outcome) : <span>Loading…</span>}</div><button className="run-button" type="button" disabled={busy} onClick={rerun}>{busy ? "Running…" : "Replay synthetic mission"}</button></section>
        <div className="section-heading"><div><p className="eyebrow">SURFACE {String(VIEWS.indexOf(view) + 1).padStart(2, "0")} / 10</p><h2>{view}</h2></div><span className="small-note">{run?.payload.scenario.scenario_id ?? "Select a run"}</span></div>
        <div className="surface">
          {view === "System topology" && <><p className="surface-intro">Each owner receives a typed contract. The safety supervisor can stop execution independently of the planner.</p><div className="topology">{LAYERS.map((layer, index) => <div className={`topology-node ${layer === "Safety supervisor" ? "safety-node" : ""}`} key={layer}><span>{String(index + 1).padStart(2, "0")}</span><strong>{layer}</strong><small>{index === 7 ? "Independent stop path" : index === 6 ? "Only motor commit path" : "Bounded interface"}</small></div>)}</div></>}
          {view === "TF & clock" && <><p className="surface-intro">All mission observations use simulator time. Frame mismatches and stale transforms are rejected.</p><div className="info-grid"><Info title="Clock domain" value={run?.payload.clock_domain ?? "sim"}/><Info title="Profile" value={`${overview.profile.ros_distro} / ${overview.profile.gazebo_distribution}`}/><Info title="Frame path" value="map → odom → base_link → camera_link / lidar_link"/><Info title="Observed percepts" value={String(percepts.length)}/></div><EventList events={percepts}/></>}
          {view === "Topic / QoS" && <><p className="surface-intro">Versioned topics, actions, freshness and bounded queues. A mismatch is visible in conformance.</p><div className="table-scroll"><table><thead><tr><th>Interface</th><th>Owner</th><th>Endpoint</th><th>Frame</th><th>Freshness</th><th>QoS</th></tr></thead><tbody>{overview.catalog.interfaces.map(item => <tr key={item.name}><td>{item.name}</td><td>{item.owner}</td><td><code>{item.topic ?? item.action}</code></td><td>{item.frame}</td><td>{item.freshness_ms} ms</td><td>{item.qos.reliability} / {item.qos.depth}</td></tr>)}</tbody></table></div></>}
          {view === "World model" && <><p className="surface-intro">Perception facts retain source and verdict. Simulator scoring truth is excluded from the agent view.</p><div className="info-grid"><Info title="Target" value={run?.payload.scenario.target_id ?? "—"}/><Info title="World seed" value={String(run?.payload.scenario.seed ?? "—")}/><Info title="Percepts" value={String(percepts.length)}/><Info title="Injected fault" value={run?.payload.scenario.fault ?? "—"}/></div><EventList events={percepts}/></>}
          {view === "Goal & policy" && <><p className="surface-intro">Typed goals pass policy checks before activation. Restricted zones require an approval fixture.</p><EventList events={events.filter(e => e.kind === "policy")}/></>}
          {view === "Plan trace" && <><p className="surface-intro">The deterministic plan is bounded. A failed precondition ends in a terminal outcome.</p><div className="plan-list">{["observe_area", "locate_entity", "navigate_to", "align_base", "point_at", "inspect_entity", "speak_report", "return_home"].map((step, index) => { const found = skillEvents.find(e => e.name === step); return <div key={step}><span>{String(index + 1).padStart(2, "0")}</span><strong>{step}</strong>{found ? badge(String(found.code)) : <span className="pending">NOT REACHED</span>}</div>; })}</div></>}
          {view === "Skill timeline" && <><p className="surface-intro">Each skill invocation has a result code and simulated timestamp.</p><EventList events={skillEvents}/></>}
          {view === "Safety & faults" && <><p className="surface-intro">E-stop latches. Protective stops require explicit recovery and a new self-check.</p><div className="info-grid"><Info title="Final safety mode" value={run?.payload.safety_mode ?? "—"}/><Info title="Unsafe motor commits" value={String(run?.payload.score.unsafe_motor_commands ?? 0)}/></div><EventList events={safetyEvents}/></>}
          {view === "Sensor / control latency" && <><p className="surface-intro">Sensor freshness and command deadlines are checked in simulated seconds. These values are descriptive, not hard real-time guarantees.</p><div className="info-grid"><Info title="Percept TTL" value="250 ms"/><Info title="Transform age limit" value="200 ms"/><Info title="Command age limit" value="200 ms"/><Info title="Safety state deadline" value="100 ms"/></div></>}
          {view === "Replay & evidence" && <><p className="surface-intro">This selected run is a deterministic portable fixture. Live ROS/Gazebo conformance is a separate, verified campaign; neither substitutes for the other.</p><div className="info-grid"><Info title="Portable outcome" value={run?.payload.outcome ?? "—"}/><Info title="Reason" value={run?.payload.reason ?? "—"}/><Info title="Events" value={String(events.length)}/><Info title="Portable replay" value={overview.summary.all_replays_equivalent ? "Equivalent" : "Needs review"}/><Info title="Live ROS campaign" value={rosEvidence?.status === "verified" ? `${rosEvidence.clean_bringups}/12 clean bringups` : "Not yet verified"}/><Info title="Live E-stop invariant" value={rosEvidence?.status === "verified" && rosEvidence.estop_to_recovery_zero_motion ? "Zero motion verified" : "Not yet verified"}/></div><div className="hash-block"><span>PORTABLE RECORD SHA-256</span><code>{run?.sha256 ?? "—"}</code></div>{rosEvidence?.status === "verified" && <div className="hash-block"><span>LIVE ROS IMAGE DIGEST</span><code>{rosEvidence.image_id}</code></div>}<EventList events={events}/></>}
        </div>
        <footer>ASTERIA SYSTEMS LAB · SYNTHETIC ENVIRONMENT · NO HARDWARE COMMANDS</footer>
      </>}
    </main>
  </div>;
}

function Info({ title, value }: { title: string; value: string }) { return <div className="info-card"><span>{title}</span><strong>{value}</strong></div>; }
function EventList({ events }: { events: Event[] }) { return <div className="event-list" aria-label="Evidence events">{events.length ? events.map(event => <div className="event" key={event.sequence}><span className="event-time">T+{event.sim_time_s.toFixed(1)}s</span><strong>{event.name ?? event.kind}</strong>{event.code && badge(String(event.code))}<span>{event.reason ?? event.entity_id ?? event.mode ?? "Recorded"}</span></div>) : <p className="empty">No events on this surface for the selected run.</p>}</div>; }

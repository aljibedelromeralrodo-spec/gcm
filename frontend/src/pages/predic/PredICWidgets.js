import React, { useState, useEffect } from "react";
import axios from "axios";
import { COLORS } from "./constants";

export function StatBox({ label, value, warn }) {
  return (
    <div style={{ padding: "0.6rem", borderRadius: "0px", background: COLORS.card, border: `1px solid ${COLORS.border}`, textAlign: "center" }}>
      <div style={{ fontSize: "0.7rem", color: COLORS.textMuted }}>{label}</div>
      <div style={{ fontSize: "1rem", fontWeight: 700, color: warn ? COLORS.orange : COLORS.text }}>{value}</div>
    </div>
  );
}

export function DashCard({ label, value, icon, color }) {
  return (
    <div style={{ padding: "1rem", borderRadius: "0px", background: COLORS.card, border: `1px solid ${COLORS.border}`, textAlign: "center" }}>
      <i className={`fa ${icon}`} style={{ fontSize: "1.3rem", color: color || COLORS.accent, marginBottom: "0.3rem", display: "block" }}></i>
      <div style={{ fontSize: "1.5rem", fontWeight: 700, color: COLORS.text }}>{value}</div>
      <div style={{ fontSize: "0.75rem", color: COLORS.textMuted }}>{label}</div>
    </div>
  );
}

export function EvalBadge({ label, result, razones }) {
  const ok = result === "VIABLE";
  const na = result === "NO APLICA";
  const bgColor = na ? "rgba(128,128,128,0.08)" : ok ? "rgba(0,184,148,0.08)" : "rgba(225,112,85,0.08)";
  const borderColorEval = na ? "rgba(128,128,128,0.3)" : ok ? "rgba(0,184,148,0.3)" : "rgba(225,112,85,0.3)";
  const textColor = na ? COLORS.textMuted : ok ? COLORS.green : COLORS.red;
  const icon = na ? "fa-minus" : ok ? "fa-check" : "fa-times";
  return (
    <div style={{ padding: "0.6rem", borderRadius: "0px", background: bgColor, border: `1px solid ${borderColorEval}`, textAlign: "center" }}>
      <div style={{ fontSize: "0.7rem", color: COLORS.textMuted }}>{label}</div>
      <div style={{ fontSize: "0.95rem", fontWeight: 700, color: textColor }}>
        <i className={`fa ${icon}`} style={{ marginRight: "0.3rem" }}></i>{result || "-"}
      </div>
      {razones && razones.length > 0 && (
        <div style={{ marginTop: "0.3rem" }}>
          {razones.slice(0, 2).map((r, i) => <div key={`${r}-${i}`} style={{ fontSize: "0.65rem", color: na ? COLORS.textMuted : COLORS.red, lineHeight: 1.3 }}>{r}</div>)}
        </div>
      )}
    </div>
  );
}

export function CentralScorePanel({ score }) {
  const s = score.score;
  const circumference = 2 * Math.PI * 54;
  const offset = circumference - (s / 100) * circumference;

  return (
    <div data-testid="central-score-panel" style={{ marginTop: "1rem", padding: "1rem", borderRadius: "0px", background: "linear-gradient(135deg, rgba(108,92,231,0.08), rgba(212,175,55,0.05))", border: `1px solid ${COLORS.border}` }}>
      <div style={{ textAlign: "center", marginBottom: "0.75rem" }}>
        <div style={{ fontSize: "0.85rem", fontWeight: 700, color: COLORS.accentLight, letterSpacing: "1px" }}>CENTRAL MUTUOS SCORE</div>
        <div style={{ fontSize: "0.65rem", color: COLORS.textMuted }}>{score.methodology}</div>
      </div>
      <div style={{ display: "flex", justifyContent: "center", marginBottom: "0.75rem" }}>
        <svg width="130" height="130" viewBox="0 0 120 120">
          <circle cx="60" cy="60" r="54" fill="none" stroke={COLORS.border} strokeWidth="8" />
          <circle cx="60" cy="60" r="54" fill="none" stroke={score.risk_color} strokeWidth="8"
            strokeDasharray={circumference} strokeDashoffset={offset}
            strokeLinecap="round" transform="rotate(-90 60 60)"
            style={{ transition: "stroke-dashoffset 1s ease" }} />
          <text x="60" y="52" textAnchor="middle" fill={score.risk_color} fontSize="28" fontWeight="800">{s}</text>
          <text x="60" y="68" textAnchor="middle" fill={COLORS.textMuted} fontSize="9">de 100</text>
          <text x="60" y="82" textAnchor="middle" fill={score.risk_color} fontSize="11" fontWeight="700">Riesgo {score.risk_level}</text>
        </svg>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
        {score.factors.map((f, i) => (
          <div key={f.factor || i} style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontSize: "0.72rem" }}>
            <div style={{ width: "90px", color: COLORS.textMuted, flexShrink: 0 }}>{f.factor}</div>
            <div style={{ flex: 1, height: "6px", borderRadius: "0px", background: COLORS.border, overflow: "hidden" }}>
              <div style={{ width: `${Math.max(0, (f.score / 25) * 100)}%`, height: "100%", borderRadius: "0px", background: f.score >= 15 ? "#00b894" : f.score >= 8 ? "#fdcb6e" : "#e17055", transition: "width 0.5s ease" }} />
            </div>
            <div style={{ width: "28px", textAlign: "right", fontWeight: 600, color: COLORS.text }}>{f.score}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ScoreHistory({ clientName, apiUrl }) {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!clientName || clientName.length < 2) { setHistory([]); return; }
    setLoading(true);
    axios.get(`${apiUrl}/api/inmobiliaria/score-history/${encodeURIComponent(clientName)}`)
      .then(r => setHistory(r.data.history || []))
      .catch(() => setHistory([]))
      .finally(() => setLoading(false));
  }, [clientName, apiUrl]);

  if (!clientName || clientName.length < 2 || history.length < 2) return null;

  return (
    <div data-testid="score-history" style={{ marginTop: "1rem", padding: "1rem", borderRadius: "0px", background: COLORS.card, border: `1px solid ${COLORS.border}` }}>
      <div style={{ fontSize: "0.85rem", fontWeight: 700, color: COLORS.accentLight, marginBottom: "0.75rem" }}>
        <i className="fa fa-line-chart" style={{ marginRight: "0.4rem" }}></i>Historial de Scores - {clientName}
      </div>
      {loading ? <div style={{ color: COLORS.textMuted, fontSize: "0.8rem" }}>Cargando...</div> : (
        <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
          {history.map((h, i) => {
            const riskColors = { "BAJO": "#00b894", "MEDIO": "#fdcb6e", "ALTO": "#e17055", "MUY ALTO": "#d63031" };
            const color = riskColors[h.risk_level] || COLORS.textMuted;
            const date = new Date(h.timestamp).toLocaleDateString("es-CL", { day: "2-digit", month: "short", year: "numeric" });
            return (
              <div key={h.timestamp || i} style={{ display: "flex", alignItems: "center", gap: "0.5rem", padding: "0.4rem 0.6rem", borderRadius: "0px", background: i === 0 ? "rgba(108,92,231,0.06)" : "transparent" }}>
                <div style={{ width: "36px", height: "36px", borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 800, fontSize: "0.85rem", color: color, border: `2px solid ${color}`, flexShrink: 0 }}>
                  {h.score}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: "0.75rem", fontWeight: 600, color: COLORS.text }}>
                    {h.viable ? "VIABLE" : "NO VIABLE"} - {h.monto_aprobado_uf} UF
                  </div>
                  <div style={{ fontSize: "0.65rem", color: COLORS.textMuted }}>{date} | {h.usuario} | {h.company_name}</div>
                </div>
                <span style={{ padding: "2px 6px", borderRadius: "0px", fontSize: "0.6rem", fontWeight: 700, color, background: `${color}15` }}>{h.risk_level}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

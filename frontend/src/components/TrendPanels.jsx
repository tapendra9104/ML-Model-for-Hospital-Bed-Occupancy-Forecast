import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

export function OccupancyHistoryChart({ history }) {
  const compactHistory = history.filter((_, index) => index % 3 === 0).map((point) => ({
    ...point,
    label: new Date(point.timestamp).toLocaleString([], { month: "short", day: "numeric", hour: "numeric" })
  }));

  return (
    <article className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Historical occupancy</p>
          <h3>Department load over time</h3>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={290}>
        <LineChart data={compactHistory}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
          <XAxis dataKey="label" tick={{ fill: "#c6d2df", fontSize: 12 }} minTickGap={24} />
          <YAxis tick={{ fill: "#c6d2df", fontSize: 12 }} />
          <Tooltip
            contentStyle={{
              background: "#0d2230",
              border: "1px solid rgba(255,255,255,0.08)",
              borderRadius: "14px"
            }}
          />
          <Line type="monotone" dataKey="icu" stroke="#f96f5d" dot={false} strokeWidth={2.5} />
          <Line type="monotone" dataKey="ward" stroke="#68d3c0" dot={false} strokeWidth={2.5} />
          <Line type="monotone" dataKey="emergency" stroke="#ffd166" dot={false} strokeWidth={2.5} />
          <Line type="monotone" dataKey="pediatric" stroke="#80aaff" dot={false} strokeWidth={2.5} />
        </LineChart>
      </ResponsiveContainer>
    </article>
  );
}

export function FlowChart({ flow }) {
  return (
    <article className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Patient flow</p>
          <h3>Admissions and discharges</h3>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={290}>
        <BarChart data={flow}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
          <XAxis dataKey="date" tick={{ fill: "#c6d2df", fontSize: 12 }} minTickGap={18} />
          <YAxis tick={{ fill: "#c6d2df", fontSize: 12 }} />
          <Tooltip
            contentStyle={{
              background: "#0d2230",
              border: "1px solid rgba(255,255,255,0.08)",
              borderRadius: "14px"
            }}
          />
          <Bar dataKey="admissions" fill="#68d3c0" radius={[6, 6, 0, 0]} />
          <Bar dataKey="discharges" fill="#f96f5d" radius={[6, 6, 0, 0]} />
          <Bar dataKey="emergency_cases" fill="#ffd166" radius={[6, 6, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </article>
  );
}

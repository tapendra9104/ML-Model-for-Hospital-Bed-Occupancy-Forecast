import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

function formatHour(value) {
  const date = new Date(value);
  return `${date.getDate()}/${date.getMonth() + 1} ${date.getHours()}:00`;
}

export function ForecastChart({ forecast }) {
  const threshold = Math.round(forecast.capacity * 0.9);
  const chartData = forecast.points.map((point) => ({
    ...point,
    label: formatHour(point.timestamp)
  }));

  return (
    <article className="panel panel--chart">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Forecast horizon</p>
          <h3>{forecast.label} next {forecast.horizon_hours} hours</h3>
        </div>
        <div className="panel-stat">
          <span>Peak forecast</span>
          <strong>{Math.round(forecast.summary.peak_occupancy)} beds</strong>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={360}>
        <AreaChart data={chartData} margin={{ top: 10, right: 20, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="forecastFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#f96f5d" stopOpacity={0.42} />
              <stop offset="95%" stopColor="#f96f5d" stopOpacity={0.05} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
          <XAxis dataKey="label" tick={{ fill: "#c6d2df", fontSize: 12 }} minTickGap={26} />
          <YAxis tick={{ fill: "#c6d2df", fontSize: 12 }} />
          <Tooltip
            contentStyle={{
              background: "#0d2230",
              border: "1px solid rgba(255,255,255,0.08)",
              borderRadius: "14px"
            }}
          />
          <Legend />
          <ReferenceLine y={threshold} stroke="#ffd166" strokeDasharray="6 6" label="90% threshold" />
          <Area type="monotone" dataKey="occupied" stroke="#f96f5d" fill="url(#forecastFill)" strokeWidth={3} />
          <Line type="monotone" dataKey="upper" stroke="#68d3c0" dot={false} strokeDasharray="5 5" />
          <Line type="monotone" dataKey="lower" stroke="#68d3c0" dot={false} strokeDasharray="5 5" />
        </AreaChart>
      </ResponsiveContainer>
    </article>
  );
}

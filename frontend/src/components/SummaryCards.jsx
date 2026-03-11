export function SummaryCards({ overview }) {
  const { hospital, departments, analytics } = overview;

  return (
    <section className="summary-grid">
      <article className="summary-card summary-card--hero">
        <p className="eyebrow">Hospital Capacity</p>
        <h2>{Math.round(hospital.utilization * 100)}% occupied</h2>
        <div className="summary-metrics">
          <div>
            <span>Total beds</span>
            <strong>{hospital.total_capacity}</strong>
          </div>
          <div>
            <span>Occupied</span>
            <strong>{Math.round(hospital.occupied)}</strong>
          </div>
          <div>
            <span>Available</span>
            <strong>{Math.round(hospital.available)}</strong>
          </div>
        </div>
      </article>

      {departments.map((department) => (
        <article className="summary-card" key={department.id}>
          <div className="card-header">
            <p className="eyebrow">{department.label}</p>
            <span className={`status-pill ${department.utilization >= 0.9 ? "status-pill--critical" : ""}`}>
              {Math.round(department.utilization * 100)}%
            </span>
          </div>
          <h3>{Math.round(department.occupied)} beds occupied</h3>
          <p>
            {Math.round(department.available)} beds free, {department.delta_24h >= 0 ? "+" : ""}
            {department.delta_24h} vs 24h
          </p>
        </article>
      ))}

      <article className="summary-card">
        <p className="eyebrow">Operational Signals</p>
        <ul className="stat-list">
          <li>
            <span>Peak admission hour</span>
            <strong>{analytics.peak_admission_hour}</strong>
          </li>
          <li>
            <span>Busiest day</span>
            <strong>{analytics.busiest_day}</strong>
          </li>
          <li>
            <span>Avg stay</span>
            <strong>{analytics.average_length_of_stay_hours}h</strong>
          </li>
        </ul>
      </article>
    </section>
  );
}

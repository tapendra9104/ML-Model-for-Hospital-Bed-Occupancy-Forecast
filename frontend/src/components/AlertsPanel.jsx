function formatAlertTime(value) {
  return new Date(value).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit"
  });
}

export function AlertsPanel({ alerts, title = "Capacity watchlist" }) {
  return (
    <article className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Predictive alerts</p>
          <h3>{title}</h3>
        </div>
      </div>

      <div className="alert-list">
        {alerts.length === 0 ? (
          <div className="alert-item">
            <strong>No threshold breaches detected</strong>
            <p>All departments are forecast to remain below the current alert thresholds.</p>
          </div>
        ) : (
          alerts.map((alert) => (
            <div className="alert-item" key={`${alert.department}-${alert.timestamp}`}>
              <div className="card-header">
                <strong>{alert.label}</strong>
                <span className={`status-pill ${alert.severity === "critical" ? "status-pill--critical" : ""}`}>
                  {Math.round(alert.utilization * 100)}%
                </span>
              </div>
              <p>{alert.message}</p>
              <small>
                {formatAlertTime(alert.timestamp)} | threshold {Math.round(alert.threshold * 100)}%
              </small>
            </div>
          ))
        )}
      </div>
    </article>
  );
}

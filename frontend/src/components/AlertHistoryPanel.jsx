function formatDate(value) {
  return new Date(value).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit"
  });
}

export function AlertHistoryPanel({ history }) {
  return (
    <article className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Alert history</p>
          <h3>Persisted alert timeline</h3>
        </div>
      </div>
      <div className="compact-list">
        {history.length === 0 ? (
          <p className="muted-copy">No persisted alerts yet.</p>
        ) : (
          history.map((entry) => (
            <div className="compact-list__item" key={entry.id}>
              <strong>{entry.label}</strong>
              <p>{entry.message}</p>
              <small>
                {formatDate(entry.forecast_timestamp)} | threshold {Math.round(entry.threshold * 100)}%
              </small>
            </div>
          ))
        )}
      </div>
    </article>
  );
}

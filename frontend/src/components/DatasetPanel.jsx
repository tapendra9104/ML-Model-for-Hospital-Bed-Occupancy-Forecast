function capacityRows(capacities) {
  return Object.entries(capacities || {}).map(([department, value]) => `${department}: ${value}`).join(" | ");
}

export function DatasetPanel({ dataset, onIngest, onRetrain, pending }) {
  async function handleChange(event) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    const csvText = await file.text();
    await onIngest(file.name, csvText);
    event.target.value = "";
  }

  return (
    <article className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Data source</p>
          <h3>HIS ingestion and retraining</h3>
        </div>
      </div>
      <div className="compact-list">
        <div className="compact-list__item">
          <strong>{dataset.source_name}</strong>
          <p>{dataset.source_type}</p>
          <small>{dataset.rows} hourly rows | trained {new Date(dataset.trained_at).toLocaleString()}</small>
        </div>
      </div>
      <p className="muted-copy">Capacity model: {capacityRows(dataset.capacities)}</p>
      <div className="upload-box">
        <input accept=".csv" disabled={pending} onChange={handleChange} type="file" />
        <button className="secondary-button" disabled={pending} onClick={onRetrain} type="button">
          {pending ? "Processing..." : "Retrain current model"}
        </button>
      </div>
      <small className="muted-copy">
        Accepted formats: aggregated hourly bed activity or event-level admission/discharge exports with
        `admission_time`, `discharge_time`, and `department` columns.
      </small>
    </article>
  );
}

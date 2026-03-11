import { useState } from "react";

const defaultScenario = {
  name: "",
  description: "",
  admissions_multiplier: 1,
  discharges_multiplier: 1,
  emergency_multiplier: 1,
  outbreak_delta: 0,
  occupancy_delta: 0,
  duration_hours: 72
};

export function ScenarioPanel({ scenarios, simulation, onSave, onDelete, onRun, pending }) {
  const [draft, setDraft] = useState(defaultScenario);

  function updateField(field, value) {
    setDraft((current) => ({
      ...current,
      [field]: value
    }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    await onSave({
      ...draft,
      admissions_multiplier: Number(draft.admissions_multiplier),
      discharges_multiplier: Number(draft.discharges_multiplier),
      emergency_multiplier: Number(draft.emergency_multiplier),
      outbreak_delta: Number(draft.outbreak_delta),
      occupancy_delta: Number(draft.occupancy_delta),
      duration_hours: Number(draft.duration_hours)
    });
    setDraft(defaultScenario);
  }

  function editScenario(scenario) {
    setDraft({ ...scenario });
  }

  return (
    <article className="panel panel--wide">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Scenario simulation</p>
          <h3>Persist and run surge models</h3>
        </div>
      </div>
      <form className="scenario-form" onSubmit={handleSubmit}>
        <label>
          <span>Name</span>
          <input onChange={(event) => updateField("name", event.target.value)} required value={draft.name} />
        </label>
        <label>
          <span>Description</span>
          <input onChange={(event) => updateField("description", event.target.value)} value={draft.description} />
        </label>
        <label>
          <span>Admissions x</span>
          <input onChange={(event) => updateField("admissions_multiplier", event.target.value)} step="0.05" type="number" value={draft.admissions_multiplier} />
        </label>
        <label>
          <span>Discharges x</span>
          <input onChange={(event) => updateField("discharges_multiplier", event.target.value)} step="0.05" type="number" value={draft.discharges_multiplier} />
        </label>
        <label>
          <span>Emergency x</span>
          <input onChange={(event) => updateField("emergency_multiplier", event.target.value)} step="0.05" type="number" value={draft.emergency_multiplier} />
        </label>
        <label>
          <span>Outbreak delta</span>
          <input onChange={(event) => updateField("outbreak_delta", event.target.value)} step="0.05" type="number" value={draft.outbreak_delta} />
        </label>
        <label>
          <span>Occupancy delta</span>
          <input onChange={(event) => updateField("occupancy_delta", event.target.value)} step="1" type="number" value={draft.occupancy_delta} />
        </label>
        <label>
          <span>Duration (hours)</span>
          <input onChange={(event) => updateField("duration_hours", event.target.value)} step="1" type="number" value={draft.duration_hours} />
        </label>
        <button className="primary-button" disabled={pending} type="submit">
          {pending ? "Saving..." : draft.id ? "Update scenario" : "Save scenario"}
        </button>
      </form>

      <div className="compact-list compact-list--split">
        <div>
          <p className="eyebrow">Saved scenarios</p>
          {scenarios.length === 0 ? (
            <p className="muted-copy">No saved scenarios yet.</p>
          ) : (
            scenarios.map((scenario) => (
              <div className="compact-list__item" key={scenario.id}>
                <strong>{scenario.name}</strong>
                <p>{scenario.description || "No description"}</p>
                <div className="inline-actions">
                  <button className="secondary-button" onClick={() => editScenario(scenario)} type="button">Edit</button>
                  <button className="secondary-button" onClick={() => onRun(scenario.id)} type="button">Run</button>
                  <button className="secondary-button secondary-button--danger" onClick={() => onDelete(scenario.id)} type="button">Delete</button>
                </div>
              </div>
            ))
          )}
        </div>
        <div>
          <p className="eyebrow">Last simulation</p>
          {!simulation ? (
            <p className="muted-copy">Run a saved scenario to inspect projected peaks and alert pressure.</p>
          ) : (
            <div className="compact-list">
              {simulation.summary.map((entry) => (
                <div className="compact-list__item" key={entry.department}>
                  <strong>{entry.label}</strong>
                  <p>Peak {Math.round(entry.peak_occupancy)} of {entry.capacity} beds</p>
                  <small>{new Date(entry.peak_timestamp).toLocaleString()}</small>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </article>
  );
}

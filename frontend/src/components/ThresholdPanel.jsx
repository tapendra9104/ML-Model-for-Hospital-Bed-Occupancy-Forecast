import { useEffect, useState } from "react";

export function ThresholdPanel({ thresholds, onSave, pending }) {
  const [draft, setDraft] = useState(thresholds);

  useEffect(() => {
    setDraft(thresholds);
  }, [thresholds]);

  function updateDepartment(department, value) {
    setDraft((current) => ({
      ...current,
      [department]: Number(value)
    }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    await onSave(draft);
  }

  return (
    <article className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Alert thresholds</p>
          <h3>Persistent alert settings</h3>
        </div>
      </div>
      <form className="settings-form" onSubmit={handleSubmit}>
        {Object.entries(draft).map(([department, value]) => (
          <label key={department}>
            <span>{department}</span>
            <input
              max="1"
              min="0.5"
              onChange={(event) => updateDepartment(department, event.target.value)}
              step="0.01"
              type="number"
              value={value}
            />
          </label>
        ))}
        <button className="primary-button" disabled={pending} type="submit">
          {pending ? "Saving..." : "Save thresholds"}
        </button>
      </form>
    </article>
  );
}

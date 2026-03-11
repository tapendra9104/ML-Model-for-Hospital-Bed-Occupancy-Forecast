export function DepartmentSelector({ forecasts, selectedDepartment, onSelect }) {
  return (
    <div className="segment-control">
      {forecasts.map((forecast) => (
        <button
          key={forecast.department}
          className={selectedDepartment === forecast.department ? "segment-control__button active" : "segment-control__button"}
          onClick={() => onSelect(forecast.department)}
          type="button"
        >
          {forecast.label}
        </button>
      ))}
    </div>
  );
}

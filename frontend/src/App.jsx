import { Suspense, lazy, useEffect, useMemo, useState } from "react";
import {
  clearStoredToken,
  deleteScenario,
  fetchAlertHistory,
  fetchCurrentUser,
  fetchDashboard,
  fetchScenarios,
  getStoredToken,
  ingestDataset,
  login,
  logout,
  retrainModels,
  saveScenario,
  saveThresholds,
  simulateScenario
} from "./api";
import { AlertHistoryPanel } from "./components/AlertHistoryPanel";
import { AlertsPanel } from "./components/AlertsPanel";
import { DatasetPanel } from "./components/DatasetPanel";
import { DepartmentSelector } from "./components/DepartmentSelector";
import { LoginPanel } from "./components/LoginPanel";
import { ScenarioPanel } from "./components/ScenarioPanel";
import { SummaryCards } from "./components/SummaryCards";
import { ThresholdPanel } from "./components/ThresholdPanel";

const ForecastChart = lazy(() => import("./components/ForecastChart").then((module) => ({ default: module.ForecastChart })));
const OccupancyHistoryChart = lazy(() => import("./components/TrendPanels").then((module) => ({ default: module.OccupancyHistoryChart })));
const FlowChart = lazy(() => import("./components/TrendPanels").then((module) => ({ default: module.FlowChart })));

function ChartFallback() {
  return <article className="panel panel--loading">Loading chart module...</article>;
}

export default function App() {
  const [token, setToken] = useState(getStoredToken());
  const [currentUser, setCurrentUser] = useState(null);
  const [dashboard, setDashboard] = useState(null);
  const [alertHistory, setAlertHistory] = useState([]);
  const [scenarios, setScenarios] = useState([]);
  const [simulation, setSimulation] = useState(null);
  const [selectedDepartment, setSelectedDepartment] = useState("icu");
  const [status, setStatus] = useState({ loading: false, error: null, action: null, actionPending: false });

  useEffect(() => {
    if (!token) {
      setCurrentUser(null);
      setDashboard(null);
      return;
    }
    void refreshAll(token, true);
  }, [token]);

  const activeForecast = useMemo(() => {
    if (!dashboard) {
      return null;
    }
    return dashboard.forecasts.find((forecast) => forecast.department === selectedDepartment) || dashboard.forecasts[0];
  }, [dashboard, selectedDepartment]);

  async function refreshAll(activeToken = token, silent = false) {
    try {
      if (!silent) {
        setStatus((current) => ({ ...current, loading: true, error: null }));
      }
      const [user, dashboardPayload, scenariosPayload, alertHistoryPayload] = await Promise.all([
        fetchCurrentUser(activeToken),
        fetchDashboard(activeToken, 72),
        fetchScenarios(activeToken),
        fetchAlertHistory(activeToken, 24)
      ]);
      setCurrentUser(user);
      setDashboard(dashboardPayload);
      setScenarios(scenariosPayload);
      setAlertHistory(alertHistoryPayload);
      setSelectedDepartment((current) => current || dashboardPayload.forecasts[0]?.department || "icu");
      setStatus((current) => ({ ...current, loading: false, error: null }));
    } catch (error) {
      if (error.status === 401) {
        clearStoredToken();
        setToken(null);
      }
      setStatus((current) => ({ ...current, loading: false, error: error.message }));
    }
  }

  async function handleLogin(credentials) {
    try {
      setStatus((current) => ({ ...current, actionPending: true, error: null }));
      const payload = await login(credentials);
      setToken(payload.token);
      setCurrentUser(payload.user);
      setStatus((current) => ({ ...current, actionPending: false }));
    } catch (error) {
      setStatus((current) => ({ ...current, actionPending: false, error: error.message }));
    }
  }

  async function handleLogout() {
    if (token) {
      await logout(token);
    }
    setSimulation(null);
    setToken(null);
    setCurrentUser(null);
    setDashboard(null);
  }

  async function runAction(actionLabel, action) {
    try {
      setStatus((current) => ({ ...current, action: actionLabel, actionPending: true, error: null }));
      await action();
      await refreshAll(token, true);
      setStatus((current) => ({ ...current, action: null, actionPending: false }));
    } catch (error) {
      if (error.status === 401) {
        clearStoredToken();
        setToken(null);
      }
      setStatus((current) => ({ ...current, actionPending: false, error: error.message }));
    }
  }

  if (!token || !currentUser) {
    return <LoginPanel errorMessage={status.error} onSubmit={handleLogin} pending={status.actionPending} />;
  }

  if (!dashboard || status.loading) {
    return (
      <main className="app-shell">
        <section className="hero">
          <p className="eyebrow">Hospital Operations Intelligence</p>
          <h1>Loading secured capacity telemetry</h1>
          <p>Authenticating and loading dashboards, thresholds, scenarios, and alert history.</p>
        </section>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <section className="hero hero--topbar">
        <div>
          <p className="eyebrow">Hospital Operations Intelligence</p>
          <h1>Machine Learning Based Hospital Bed Occupancy Forecasting System</h1>
          <p>
            Data source: {dashboard.dataset.source_name} ({dashboard.dataset.source_type}). Last retrain: {new Date(dashboard.dataset.trained_at).toLocaleString()}.
          </p>
        </div>
        <div className="hero-actions">
          <div className="hero-badge">
            <span>Signed in as</span>
            <strong>{currentUser.username}</strong>
          </div>
          <button className="secondary-button" onClick={handleLogout} type="button">Sign out</button>
        </div>
      </section>

      {status.error ? <p className="form-error form-error--floating">{status.error}</p> : null}
      <SummaryCards overview={dashboard.overview} />

      <section className="layout-grid">
        <div className="layout-grid__main">
          <DepartmentSelector
            forecasts={dashboard.forecasts}
            selectedDepartment={selectedDepartment}
            onSelect={setSelectedDepartment}
          />
          <Suspense fallback={<ChartFallback />}>
            {activeForecast ? <ForecastChart forecast={activeForecast} /> : null}
          </Suspense>
          <div className="panel-grid">
            <Suspense fallback={<ChartFallback />}>
              <OccupancyHistoryChart history={dashboard.trends.occupancy_history} />
            </Suspense>
            <Suspense fallback={<ChartFallback />}>
              <FlowChart flow={dashboard.trends.daily_flow} />
            </Suspense>
          </div>
        </div>
        <aside className="layout-grid__side">
          <AlertsPanel alerts={dashboard.alerts} />
          <AlertHistoryPanel history={alertHistory} />
        </aside>
      </section>

      <section className="admin-grid">
        <ThresholdPanel
          onSave={(thresholds) => runAction("thresholds", () => saveThresholds(token, thresholds))}
          pending={status.actionPending && status.action === "thresholds"}
          thresholds={dashboard.thresholds}
        />
        <DatasetPanel
          dataset={dashboard.dataset}
          onIngest={(name, csvText) => runAction("ingest", async () => {
            await ingestDataset(token, name, csvText);
            setSimulation(null);
          })}
          onRetrain={() => runAction("retrain", async () => {
            await retrainModels(token);
            setSimulation(null);
          })}
          pending={status.actionPending && ["ingest", "retrain"].includes(status.action)}
        />
        <ScenarioPanel
          onDelete={(scenarioId) => runAction("scenario-delete", () => deleteScenario(token, scenarioId))}
          onRun={async (scenarioId) => {
            try {
              setStatus((current) => ({ ...current, action: "scenario-run", actionPending: true, error: null }));
              const result = await simulateScenario(token, scenarioId, 72);
              setSimulation(result);
              await refreshAll(token, true);
              setStatus((current) => ({ ...current, action: null, actionPending: false }));
            } catch (error) {
              setStatus((current) => ({ ...current, actionPending: false, error: error.message }));
            }
          }}
          onSave={(scenario) => runAction("scenario-save", () => saveScenario(token, scenario))}
          pending={status.actionPending && ["scenario-save", "scenario-delete", "scenario-run"].includes(status.action)}
          scenarios={scenarios}
          simulation={simulation}
        />
      </section>

      {simulation ? <AlertsPanel alerts={simulation.alerts} title={`Scenario alerts: ${simulation.scenario.name}`} /> : null}
    </main>
  );
}

import { useState } from "react";

import { Layout } from "./components/Layout";
import { BaselinesPage } from "./pages/BaselinesPage";
import { DashboardPage } from "./pages/DashboardPage";
import { GraderPage } from "./pages/GraderPage";
import { SimulationPage } from "./pages/SimulationPage";
import { TasksPage } from "./pages/TasksPage";

export type PageId = "dashboard" | "simulation" | "tasks" | "baselines" | "grader";

const navigationItems: Array<{ id: PageId; label: string }> = [
  { id: "dashboard", label: "Dashboard" },
  { id: "simulation", label: "Simulation" },
  { id: "tasks", label: "Tasks" },
  { id: "baselines", label: "Baselines" },
  { id: "grader", label: "Grader" },
];

const pageRegistry: Record<PageId, JSX.Element> = {
  dashboard: <DashboardPage />,
  simulation: <SimulationPage />,
  tasks: <TasksPage />,
  baselines: <BaselinesPage />,
  grader: <GraderPage />,
};

export default function App() {
  const [activePage, setActivePage] = useState<PageId>("dashboard");

  return (
    <Layout
      activePage={activePage}
      items={navigationItems}
      onNavigate={setActivePage}
    >
      <div key={activePage}>{pageRegistry[activePage]}</div>
    </Layout>
  );
}

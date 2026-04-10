import { useEffect, useState } from "react";

import { Button } from "../components/ui/Button";
import { PageContainer } from "../components/ui/PageContainer";
import { Section } from "../components/ui/Section";
import { Table } from "../components/ui/Table";
import { fetchTasks, resetEnvironment } from "../lib/api";
import type { TaskMap } from "../lib/types";

type TaskRow = {
  id: string;
  name: string;
  description: string;
};

export function TasksPage() {
  const [tasks, setTasks] = useState<TaskMap>({});
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [runningTask, setRunningTask] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    fetchTasks()
      .then((response) => {
        if (!cancelled) {
          setTasks(response);
          setError(null);
        }
      })
      .catch((nextError: Error) => {
        if (!cancelled) {
          setError(nextError.message);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  async function handleRun(taskId: string) {
    setRunningTask(taskId);
    try {
      await resetEnvironment(taskId);
      setStatus(`Loaded ${tasks[taskId]?.name ?? taskId} into the simulation environment.`);
      setError(null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to run task.");
    } finally {
      setRunningTask(null);
    }
  }

  const rows: TaskRow[] = Object.entries(tasks).map(([id, task]) => ({
    id,
    name: task.name,
    description: task.description,
  }));

  return (
    <PageContainer
      title="Tasks"
      subtitle="Select a scenario, inspect its purpose, and load it into the environment."
    >
      {status ? <p className="text-sm text-blue-600">{status}</p> : null}
      {error ? <p className="text-sm text-red-500">{error}</p> : null}

      <Section title="Scenario library" description="Each task loads one deterministic operating condition.">
        <Table<TaskRow>
          columns={[
            {
              key: "id",
              header: "Task",
              render: (row) => <span className="font-medium text-gray-900">{row.id}</span>,
            },
            {
              key: "name",
              header: "Name",
              render: (row) => row.name,
            },
            {
              key: "description",
              header: "Description",
              render: (row) => row.description,
            },
            {
              key: "action",
              header: "Run",
              render: (row) => (
                <Button
                  disabled={runningTask === row.id}
                  variant="primary"
                  onClick={() => handleRun(row.id)}
                >
                  Run
                </Button>
              ),
            },
          ]}
          emptyMessage="No tasks are available."
          getRowKey={(row) => row.id}
          rows={rows}
        />
      </Section>
    </PageContainer>
  );
}

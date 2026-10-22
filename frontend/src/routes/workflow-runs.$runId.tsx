import { createFileRoute } from "@tanstack/react-router";
import { RunPage } from "@/features/workflow-runs/page";
export const Route = createFileRoute("/workflow-runs/$runId")({
  component: Page,
});
function Page(): React.JSX.Element {
  const { runId } = Route.useParams();
  return <RunPage key={runId} id={runId} />;
}

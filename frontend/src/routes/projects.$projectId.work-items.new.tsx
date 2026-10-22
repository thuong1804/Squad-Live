import { createFileRoute } from "@tanstack/react-router";
import { NewItemPage } from "@/features/work-items/pages";
export const Route = createFileRoute("/projects/$projectId/work-items/new")({
  component: Page,
});
function Page(): React.JSX.Element {
  const { projectId } = Route.useParams();
  return <NewItemPage key={projectId} projectId={projectId} />;
}

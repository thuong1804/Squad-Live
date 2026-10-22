import { createFileRoute, Outlet, useMatchRoute } from "@tanstack/react-router";
import { ProjectPage } from "@/features/projects/pages";
export const Route = createFileRoute("/projects/$projectId")({
  component: Page,
});
function Page(): React.JSX.Element {
  const { projectId } = Route.useParams();
  const match = useMatchRoute();
  return match({
    to: "/projects/$projectId/work-items/new",
    params: { projectId },
  }) ? (
    <Outlet />
  ) : (
    <ProjectPage key={projectId} id={projectId} />
  );
}

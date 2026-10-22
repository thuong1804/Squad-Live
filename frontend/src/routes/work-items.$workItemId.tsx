import { createFileRoute } from "@tanstack/react-router";
import { ItemPage } from "@/features/work-items/pages";
export const Route = createFileRoute("/work-items/$workItemId")({
  component: Page,
});
function Page(): React.JSX.Element {
  const { workItemId } = Route.useParams();
  return <ItemPage key={workItemId} id={workItemId} />;
}

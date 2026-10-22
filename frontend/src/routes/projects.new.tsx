import { createFileRoute } from "@tanstack/react-router";
import { NewProjectPage } from "@/features/projects/pages";
export const Route = createFileRoute("/projects/new")({
  component: NewProjectPage,
});

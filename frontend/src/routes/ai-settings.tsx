import { createFileRoute } from "@tanstack/react-router";
import { AISettings } from "@/features/ai/settings";
export const Route = createFileRoute("/ai-settings")({ component: AISettings });

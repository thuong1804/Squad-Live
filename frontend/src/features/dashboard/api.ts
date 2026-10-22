import { queryOptions } from "@tanstack/react-query";
import { api } from "@/lib/api-client";

export const healthOptions = queryOptions({
  queryKey: ["health"],
  queryFn: ({ signal }) =>
    api.request(
      import.meta.env.VITE_HEALTH_PATH || "/health",
      (body) => {
        // A successful JSON health response confirms reachability, not DB readiness or authentication.
        if (body === null || typeof body !== "object" || Array.isArray(body))
          throw new Error("Invalid health response");
        return { reachable: true as const };
      },
      { signal },
    ),
});

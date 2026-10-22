import { useSyncExternalStore } from "react";

let csrfToken = "";
let identity = "";
const listeners = new Set<() => void>();
export const getCsrfToken = (): string => csrfToken;
export function setSession(value: string, user = ""): void {
  csrfToken = value;
  identity = user;
  listeners.forEach((listener) => listener());
}
export function useIdentity(): string {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    () => identity,
  );
}

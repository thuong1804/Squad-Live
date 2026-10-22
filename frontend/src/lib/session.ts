import { useSyncExternalStore } from "react";

let token = "";
let identity = "";
const listeners = new Set<() => void>();
export const getToken = (): string => token;
export function setSession(value: string, user = ""): void {
  token = value;
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

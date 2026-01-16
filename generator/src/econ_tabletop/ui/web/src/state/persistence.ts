import { GameState } from "./types";

const STORAGE_KEY = "econ-tabletop-state";

export function saveState(state: GameState): void {
  const snapshot = { ...state, history: [], future: [] };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot));
}

export function loadState(): GameState | null {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as GameState;
  } catch {
    return null;
  }
}

export function clearState(): void {
  localStorage.removeItem(STORAGE_KEY);
}

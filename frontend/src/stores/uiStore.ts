/**
 * Estado que pertence só ao cliente.
 *
 * Regra do projeto: se o dado vem do backend, ele vive no cache do TanStack
 * Query e não aqui. Este store guarda apenas o que o servidor desconhece —
 * sidebar aberta, canal SSE ativo, avisos na tela (ADR 001).
 */
import { create } from "zustand";

export interface Toast {
  id: string;
  title: string;
  description?: string;
  tone: "success" | "error" | "info";
}

interface UiState {
  sidebarOpen: boolean;
  eventsConnected: boolean;
  toasts: Toast[];
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  setEventsConnected: (connected: boolean) => void;
  pushToast: (toast: Omit<Toast, "id">) => void;
  dismissToast: (id: string) => void;
}

export const useUiStore = create<UiState>((set) => ({
  sidebarOpen: true,
  eventsConnected: false,
  toasts: [],
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
  setEventsConnected: (eventsConnected) => set({ eventsConnected }),
  pushToast: (toast) =>
    set((state) => ({
      toasts: [...state.toasts, { ...toast, id: crypto.randomUUID() }],
    })),
  dismissToast: (id) => set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),
}));

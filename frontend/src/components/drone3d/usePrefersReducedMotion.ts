/**
 * Leitura de `prefers-reduced-motion`.
 *
 * Vive dentro de `drone3d/` de propósito: a cena precisa ser autocontida, sem
 * importar nada de fora da pasta além do próprio Three/R3F. O tema já silencia
 * animações CSS; o que roda no `useFrame` é invisível para o CSS e precisa
 * consultar a preferência por conta própria.
 */
import { useEffect, useState } from "react";

const QUERY = "(prefers-reduced-motion: reduce)";

function matches(): boolean {
  // jsdom não implementa matchMedia — sem a guarda, todo teste que monta a cena quebra.
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return false;
  return window.matchMedia(QUERY).matches;
}

export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(matches);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;
    const query = window.matchMedia(QUERY);
    const onChange = (event: MediaQueryListEvent) => setReduced(event.matches);

    setReduced(query.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);

  return reduced;
}

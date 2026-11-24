import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

type Reply = { status?: number; body: unknown };
type Handler = (body: unknown) => Reply;
export type Call = { method: string; path: string; body: unknown };

function readBody(init?: RequestInit): unknown {
  if (!init?.body) return undefined;
  if (init.body instanceof FormData) return init.body;
  return JSON.parse(String(init.body));
}

/** Replaces fetch with routes keyed like "GET /shortlist". Unknown routes fail the request. */
export function mockApi(routes: Record<string, Handler>): Call[] {
  const calls: Call[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      const path = new URL(url).pathname;
      const body = readBody(init);
      calls.push({ method, path, body });
      const handler = routes[`${method} ${path}`];
      if (!handler) {
        return new Response(JSON.stringify({ detail: `No route: ${method} ${path}` }), {
          status: 404,
        });
      }
      const reply = handler(body);
      return new Response(JSON.stringify(reply.body), { status: reply.status ?? 200 });
    }),
  );
  return calls;
}

export function renderPage(page: ReactElement, route = "/") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>{page}</MemoryRouter>
    </QueryClientProvider>,
  );
  return { ...view, client };
}

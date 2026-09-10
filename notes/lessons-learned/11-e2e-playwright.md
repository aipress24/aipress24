# E2E (Playwright)

Part of [Lessons Learned](00-index.md).

### `page.request.post()` does not carry `BrowserContext` cookies

**Rule**: go through JS `fetch` via `page.evaluate(...)`, and always assert the final URL.

Authenticated POSTs silently bounce to `/auth/login` with status 200 and a login-form body. Five tests were green false positives until a uniform `"/auth/login" not in resp["url"]` assertion was added.

### Vite HMR sockets block Firefox e2e beyond ~20 tests

**Rule**: `route.abort()` on `**://localhost:3000/**` in an autouse fixture when testing against a dev server.

Firefox serializes new scripts behind earlier HMR sockets; DCL stalls indefinitely. Pages still render, just without HMR — which tests don't use.

# On-demand UI loading (O6.1.4)

Measured against origin/dev at the start of the task, using fresh production browser contexts and `tests/e2e/loading-size.spec.ts`. Values sum decoded JavaScript response bytes from the browser Resource Timing API after network idle. They are uncompressed bytes, not transfer sizes or a latency benchmark. Next.js 16's build output does not report the former First Load JS column, so the browser measurement is used instead.

| Route | Before | After | Change |
| --- | ---: | ---: | ---: |
| `/` | 851,207 | 851,207 | unchanged |
| `/dashboard` | 1,249,395 | 1,248,095 | 1,300 bytes less |

The command palette and shortcuts sheet mount on first use and remain mounted afterward to preserve closing animations and focus behaviour. QR generation imports its library during MFA setup. The organogram canvas and rota week grid load separately when their data-backed view renders.

The home page does not use these components; this change does not meet the audit's requested reduction on `/`. The measured dashboard saving is small, and no substantial home-page speed improvement is claimed. Public-page rendering/caching remains O6.1.1.

Validation: 61 focused unit tests passed; web typecheck and lint passed. Production MFA, organogram and rota journeys and the two byte measurements passed (6 tests including authentication setup).

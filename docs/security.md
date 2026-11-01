# Security notes

Decisions about the security design that are not obvious from the code. The full rules are in `plan.md` Section 4.

## Content Security Policy

- Scripts use a per-request nonce plus `strict-dynamic`; there is no `'unsafe-inline'` for scripts (`web/lib/security/csp.ts`).
- `<style>` elements use the nonce too.
- **Accepted exception:** `style-src-attr 'unsafe-inline'`. The animation library sets `style` attributes at run time (transforms and opacity while a layer opens, closes or slides), and a nonce cannot be attached to an attribute. It allows inline `style="..."` attributes only; it does not allow `<style>` elements or any script. Components may not use the `style` prop themselves (an ESLint rule bans it), so the exception is not used by our own markup. Decided by the owner on 2026-11-02.

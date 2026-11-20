# Security

## Reporting a vulnerability

Please use GitHub's **private vulnerability reporting** (Security tab → *Report a vulnerability*) rather than a public
issue. You will get an answer within a week.

## How Coche protects your data

- **Password mode** (`COCHE_PASSWORD`): signed `HttpOnly`, `SameSite=Strict` session cookie (add `COCHE_SECURE_COOKIE=1`
  behind HTTPS); changing the password logs every session out; 8 failed logins per address = 5 minutes wait.
- **API tokens** for scripts (`Authorization: Bearer …`), compared in constant time.
- **No password** (trusted network only): Coche still refuses what another web site could make your browser do —
  cross-site writes (CSRF: non-JSON bodies, foreign `Origin`, `Sec-Fetch-Site: cross-site`) and unknown host names
  (DNS rebinding, see `COCHE_ALLOWED_HOSTS`). Anyone who can reach the port can still read and change your tasks:
  set a password as soon as the network is not entirely yours.
- Everything you type is escaped before it is displayed; links only accept `http(s)://`.
- SQL queries are parameterised; the database files are readable by their owner only.
- Notification channels (command, ntfy, webhook) come from environment variables only, never from the web API.
- `X-Frame-Options`, `Content-Security-Policy: frame-ancestors 'self'`, `nosniff`, `Referrer-Policy: same-origin`.
- No third-party dependency: the Python standard library and SQLite.

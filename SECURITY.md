# Security Policy

## Reporting a vulnerability

Please **do not** open a public issue for security problems.

Report vulnerabilities privately via one of:

- GitHub's [private vulnerability reporting](https://github.com/wegovnyc/databook/security/advisories/new)
  ("Report a vulnerability" under the Security tab), or
- email **security@wegov.nyc** *(confirm this address before publishing)*

We'll acknowledge receipt as soon as we can and keep you updated on the fix.

## Scope

Databook is a public, read-only presentation of NYC open data. The most useful
reports concern:

- authentication/authorization gaps on the admin surface,
- injection (SQL/command/template) in API or frontend code,
- exposure of any credential or non-public data.

Please note that Mapbox/Carto client tokens embedded in the frontend are
publishable-by-design keys restricted at the provider; report them only if you
find one that is unrestricted or grants write access.

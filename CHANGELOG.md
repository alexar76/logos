# Changelog

All notable changes to this project are documented in this file. Earlier releases: the git history.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.2] - 2026-10-28

### Security

- `X-Real-IP` / `X-Forwarded-For` were taken from any private, loopback or link-local peer, so a neighbour on the same docker network or LAN could name its own address and get a fresh rate-limit bucket per request. They now count only from `LOGOS_TRUSTED_PROXIES`: addresses, CIDRs, host names (looked up again every minute) and `gateway` (the container's default route, i.e. the host's nginx for a published port); the default is loopback only. Reported by Vulnetix (GCVE-110-VULN-PYPI-2026-000638). In the image the container's own nginx connects over loopback, so the default fits.
- `python -m logos.main` bound `0.0.0.0`. It binds `127.0.0.1` unless `LOGOS_HOST` says otherwise, as the other packages do (Vulnetix GCVE-110-VULN-PYPI-2026-000638).

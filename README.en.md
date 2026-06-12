<p align="right"><a href="README.md">한국어</a> · <strong>English</strong></p>

# tossinvest-cli

An unofficial CLI/REPL for [Toss Securities Open API](https://developers.tossinvest.com/docs) —
quotes, charts, portfolio, and order placement from your terminal.

> **Official Open API only.** This tool does not reverse-engineer the app's private API,
> so it is conservative about ToS and account safety. Features the official API does not
> expose (investor flows, popularity rankings, AI signals, realtime push) are intentionally
> out of scope. For AI-agent usage conventions, see [AGENTS.md](AGENTS.md).

## Install

```bash
uv tool install tossinvest-cli   # or: pip install tossinvest-cli
```

Requires Python ≥ 3.11. Registers the `toss` command.

## Setup

Get `client_id` / `client_secret` from the [Open API console](https://developers.tossinvest.com),
then copy `.env.example` to `.env` and fill it in. Run `toss auth status` to verify.

## Quick start

```bash
toss                         # REPL (interactive shell)
toss --sim                   # simulation mode — no credentials needed
```

Inside the REPL:

```text
toss> 005930                 # bare symbol → quote (KR codes & US tickers)
toss> w AAPL                 # one-shot symbol dashboard (quote·position·chart·orderbook)
toss> c 005930 -P 3m         # candlestick chart with MA/volume (--rsi 14, --bb 20)
toss> wl add 005930 AAPL     # local watchlist; `wl` shows a board sorted by daily change
toss> 005930 100             # buy 100 shares at market (confirmation prompt)
toss> p                      # holdings with P/L and daily change
toss> ?                      # full command reference
```

## Safety model

Real orders hit your real account. Layers of protection:

- `--dry-run` builds and prints the request without sending.
- Confirmation prompt by default (`-y` to skip); orders ≥ ₩100M require `--confirm-high-value`.
- Per-action kill switches in `.env`: `TOSS_NO_BUY/SELL/MODIFY/CANCEL=1` (sim & dry-run still allowed).
- Idempotency keys are auto-generated to prevent duplicate orders on retries.
- Every order placed through this CLI is journaled locally: `toss ledger show`.

## Machine-friendly output

```bash
toss --json market price 005930 | jq -r '.[0].lastPrice'
toss --csv account holdings > holdings.csv
```

## Disclaimer

Unofficial tool; you are responsible for your trades. API behavior follows the
[official documentation](https://developers.tossinvest.com/docs).

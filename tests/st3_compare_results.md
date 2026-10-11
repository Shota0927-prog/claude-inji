# ST-3 step comparison — SYNTHETIC data (not market performance)

Engine model zones on random-walk 1M data, seeds (4, 5, 6, 7), 12 days each; mirror orders + broker emulator.
Shows only how each step changes the order flow on identical zones. Use the TradingView Strategy Tester for results.

| Mode | Step | Trades | Win % | PF | Avg R | Total R | Pre-check skips | Post-fill RR exits |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| A | Base (A/B/C = ST-2) | 22 | 13.6 | 0.24 | -0.659 | -14.50 | 0 | 0 |
| A | + Session | 26 | 26.9 | 0.52 | -0.327 | -8.50 | 0 | 0 |
| A | + Session + Zone TP | 19 | 31.6 | 0.65 | -0.184 | -3.51 | 573 | 3 |
| A | + Session + Zone TP + BE | 19 | 31.6 | 0.73 | -0.132 | -2.51 | 625 | 3 |
| B | Base (A/B/C = ST-2) | 33 | 33.3 | 0.75 | -0.167 | -5.50 | 0 | 0 |
| B | + Session | 31 | 35.5 | 0.80 | -0.113 | -3.50 | 0 | 0 |
| B | + Session + Zone TP | 23 | 30.4 | 0.67 | -0.253 | -5.82 | 63 | 0 |
| B | + Session + Zone TP + BE | 23 | 34.8 | 1.15 | 0.030 | 0.68 | 70 | 0 |
| C | Base (A/B/C = ST-2) | 24 | 29.2 | 0.61 | -0.271 | -6.50 | 0 | 0 |
| C | + Session | 23 | 34.8 | 0.80 | -0.130 | -3.00 | 0 | 0 |
| C | + Session + Zone TP | 16 | 25.0 | 0.54 | -0.395 | -6.32 | 22 | 0 |
| C | + Session + Zone TP + BE | 16 | 25.0 | 0.63 | -0.270 | -4.32 | 22 | 0 |
| D | Base (A/B/C = ST-2) | 27 | 40.7 | 0.99 | 0.019 | 0.50 | 0 | 0 |
| D | + Session | 26 | 42.3 | 1.05 | 0.058 | 1.50 | 0 | 0 |
| D | + Session + Zone TP | 16 | 31.2 | 0.61 | -0.255 | -4.08 | 24 | 0 |
| D | + Session + Zone TP + BE | 17 | 35.3 | 1.55 | 0.166 | 2.82 | 28 | 0 |

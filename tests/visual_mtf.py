"""ZoneVisualPractical — MTF Authority (V4) helpers.

Pure functions shared by the Pine generator and the fixtures:

  * auth_pack_from_direct(direct)  : the 5M Authority Feed Pack function body, derived *mechanically*
                                     from the 5M direct-path Source / Break / dayId code
  * guard_accept(...)              : Python mirror of the Pine f_authAccept() guard
  * simulate_*                     : mirrors of the =5m / <5m / >5m Authority delivery paths

No Source formula is written here by hand: the pack is a text transform of the direct path.
"""
import re

FEED_FIELDS = ["ma1", "ma1d", "ma2", "ma2d",
               "ph1", "ph1t", "pl1", "pl1t", "ph2", "ph2t", "pl2", "pl2t", "ph3", "ph3t", "pl3", "pl3t",
               "acc1Hi", "acc1Lo", "acc1Id", "acc2Hi", "acc2Lo", "acc2Id", "acc3Hi", "acc3Lo", "acc3Id",
               "dayId", "brClose", "brHigh", "brLow", "brEval",
               "barHigh", "barLow", "barClose", "barTime", "barIndex"]
# value each ZoneFeed field takes on the 5M direct path (same order as FEED_FIELDS)
DIRECT_VALUES = ["ma1Val", "ma1Delta", "ma2Val", "ma2Delta",
                 "ph1", "ph1T", "pl1", "pl1T", "ph2", "ph2T", "pl2", "pl2T", "ph3", "ph3T", "pl3", "pl3T",
                 "acc1Hi", "acc1Lo", "acc1Id", "acc2Hi", "acc2Lo", "acc2Id", "acc3Hi", "acc3Lo", "acc3Id",
                 "tradingDayId", "brClose", "brHigh", "brLow", "brEval",
                 "high", "low", "close", "time", "_aIdx"]
PACK_RETURN = DIRECT_VALUES + ["_aOk"]          # 36 primitives (barIndex = start-relative 5M index)

DIRECT_BEGIN = "float ma1Val   = na\n"
DIRECT_END = "zn.ZoneFeed zoneFeed = zn.ZoneFeed.new("


def direct_segment(visual):
    i = visual.index("\n" + DIRECT_BEGIN) + 1          # column-0 (main context) direct path, not the pack copy
    j = visual.index(DIRECT_END, i)
    return visual[i:j]


def _dedent_block(t, anchor):
    """anchor = 'if is5mChart\n' + first body line: drop the 'if' line, de-indent its body (until a blank line)."""
    i = t.index(anchor)
    head = anchor[:anchor.index("\n") + 1]
    j = t.index("\n\n", i)
    body = t[i + len(head):j + 1]
    assert all(l.startswith("    ") for l in body.splitlines()), anchor
    return t[:i] + "".join(l[4:] for l in body.splitlines(True)) + t[j + 1:]


def auth_pack_from_direct(direct):
    """5M direct path (main context, gated by is5mChart) -> body of f_authPack (evaluated in a 5M context).
    Only mechanical edits: full-line comments dropped, the is5mChart gates dropped (the pack only ever runs
    in a 5M context), blank lines collapsed, and timeframe.in_seconds() -> timeframe.in_seconds(AUTH_TF)
    (inside a request the Engine TF is the 5M Authority TF; on the direct path it is the 5M chart TF)."""
    t = "\n".join(l for l in direct.split("\n") if not l.lstrip().startswith("//"))
    assert t.count("if is5mChart and use") == 3
    t = t.replace("if is5mChart and use", "if use")
    t = _dedent_block(t, "if is5mChart\n    int   brTfSec")
    t = _dedent_block(t, "if is5mChart\n    int _locY")
    assert "is5mChart" not in t
    assert t.count("timeframe.in_seconds()") == 1
    t = t.replace("timeframe.in_seconds()", "timeframe.in_seconds(AUTH_TF)")
    t = re.sub(r"\n{2,}", "\n", t).strip("\n") + "\n"
    return t


def pine_auth_pack(direct):
    body = auth_pack_from_direct(direct)
    body += "[_aIdx, _aOk] = f_authKey(startT)\n"
    body += "[" + ", ".join(PACK_RETURN) + "]\n"
    ind = "".join("    " + l if l.strip() else l for l in body.splitlines(True))
    return "f_authPack(int startT) =>\n" + ind


def pine_auth_pack_prev():
    names = ["q%d" % k for k in range(len(PACK_RETURN))]
    s = "f_authPackPrev(int startT) =>\n"
    s += "    [" + ", ".join(names) + "] = f_authPack(startT)\n"
    s += "    [" + ", ".join(n + "[1]" for n in names) + "]\n"
    return s


def pine_feed_new(vals, indent):
    pad = " " * (indent + 5)
    pairs = ["%s = %s" % (f, v) for f, v in zip(FEED_FIELDS, vals)]
    lines, cur = [], []
    for p in pairs:
        cur.append(p)
        if len(cur) == 5:
            lines.append(", ".join(cur))
            cur = []
    if cur:
        lines.append(", ".join(cur))
    return "zn.ZoneFeed.new(\n" + ",\n".join(pad + l for l in lines) + ")"


# ---------------------------------------------------------------------------
# Python mirror of the Pine guard (f_authAccept) — statuses
# ---------------------------------------------------------------------------
ST_WAIT, ST_OK, ST_INSUFF, ST_BROKEN = 0, 1, 2, 3


class Guard:
    def __init__(self):
        self.firstTime = None
        self.firstIdx = None
        self.lastIdx = None
        self.lastTime = None
        self.count = 0
        self.dupSkip = 0
        self.missing = 0
        self.inversion = 0
        self.status = ST_WAIT

    def copy(self):
        g = Guard()
        g.__dict__.update(self.__dict__)
        return g


def guard_accept(g, rel, start_ok, t):
    acc = False
    if g.status <= ST_OK and rel is not None and rel >= 0:
        if g.lastIdx is None:
            if rel == 0 and start_ok:
                acc = True
                g.firstTime, g.firstIdx, g.status = t, rel, ST_OK
            else:
                g.status = ST_INSUFF
        elif rel == g.lastIdx:
            g.dupSkip += 1
        elif rel == g.lastIdx + 1:
            acc = True
        elif rel < g.lastIdx:
            g.inversion += 1
            g.status = ST_BROKEN
        else:
            g.missing += rel - g.lastIdx - 1
            g.status = ST_BROKEN
        if acc:
            g.lastIdx, g.lastTime, g.count = rel, t, g.count + 1
    return acc


# ---------------------------------------------------------------------------
# Market model: 5M bars (with session gaps) and the 5M context f_authKey
# ---------------------------------------------------------------------------
M5 = 300


def five_min_bars(t0, n, gaps=()):
    """n existing 5M bar open times starting at t0; 'gaps' = set of 5M slot numbers with no bar."""
    out, slot = [], 0
    while len(out) < n:
        if slot not in gaps:
            out.append(t0 + slot * M5)
        slot += 1
    return out


def auth_key_series(ctx_times, start_t):
    """f_authKey over a 5M context whose dataset is ctx_times (bar_index 0 = ctx_times[0])."""
    start_idx, start_ok, out = None, False, []
    for bi, t in enumerate(ctx_times):
        if start_idx is None and t >= start_t:
            start_idx, start_ok = bi, bi > 0
        out.append((None if start_idx is None else bi - start_idx, start_ok))
    return out


def feed_record(t, rel):
    """deterministic stand-in for the 35 primitive fields of the 5M bar at time t (pure function of t)."""
    return (t, rel, (t * 2654435761) % 1000003 / 7.0)


def run_engine(feeds):
    """Engine mirror: zn.update is a pure function of (state, feed) — L3 / V4 static proof.
    State = ordered fold over the processed feeds (any reorder / dup / skip changes it)."""
    st = 0
    for f in feeds:
        st = (st * 1000003 + hash(f)) % (1 << 61)
    return st


def simulate_direct(times_5m, chart_start, start_t):
    """=5m chart: chart bars = 5M bars from chart_start; f_authKey in main context."""
    ctx = [t for t in times_5m if t >= chart_start]
    keys = auth_key_series(ctx, start_t)
    g, fed = Guard(), []
    for t, (rel, ok) in zip(ctx, keys):
        if guard_accept(g, rel, ok, t):
            fed.append(feed_record(t, rel))
    return g, fed


def simulate_lower(times_5m, chart_sec, chart_start, start_t, ctx_start=None, trades=None):
    """<5m chart: request.security(AUTH_TF, f_authPackPrev(), lookahead_on). A chart bar (open on the chart_sec
    grid, exists iff it has a trade) is mapped to the 5M bar containing its open time and receives that 5M
    bar's previous bar ([1]). trades: {5M open time: [trade offsets in s]} (default: a trade every 15 s)."""
    ctx_start = chart_start if ctx_start is None else ctx_start
    ctx = [t for t in times_5m if t >= ctx_start]
    keys = auth_key_series(ctx, start_t)
    pos = {t: k for k, t in enumerate(ctx)}
    opens = set()
    for t5 in ctx:
        offs = trades.get(t5, range(0, M5, 15)) if trades else range(0, M5, 15)
        for o in offs:
            c = (t5 + o) // chart_sec * chart_sec
            if c >= chart_start:
                opens.add(c)
    g, fed, calls = Guard(), [], {}
    for c in sorted(opens):
        t5 = c // M5 * M5
        if t5 not in pos:            # chart bar opens in a 5M slot with no 5M bar
            continue
        k = pos[t5] - 1
        if k < 0:
            continue
        rel, ok = keys[k]
        if guard_accept(g, rel, ok, ctx[k]):
            fed.append(feed_record(ctx[k], rel))
            calls[rel] = calls.get(rel, 0) + 1
    return g, fed, calls


def simulate_upper(times_5m, chart_sec, chart_start, start_t, intrabar_limit=None, live_last=False, ctx_start=None):
    """>5m chart: request.security_lower_tf(AUTH_TF, f_authPack()) — each chart bar receives the array of its
    5M intrabars oldest -> newest; replay i < n-1 or barstate.isconfirmed. Intrabars older than the
    intrabar limit are not delivered (empty arrays). live_last: the last chart bar is a realtime bar."""
    ctx_start = chart_start if ctx_start is None else ctx_start
    ctx = [t for t in times_5m if t >= ctx_start]
    keys = auth_key_series(ctx, start_t)
    delivered = set(range(len(ctx)))
    if intrabar_limit is not None:
        delivered = set(range(max(0, len(ctx) - intrabar_limit), len(ctx)))
    bars = {}
    for k, t in enumerate(ctx):
        cb = (t - chart_start) // chart_sec
        if t >= chart_start:
            bars.setdefault(cb, []).append(k)
    order = sorted(bars)
    g, fed, calls = Guard(), [], {}
    for bno, cb in enumerate(order):
        arr = [k for k in bars[cb] if k in delivered]
        confirmed = not (live_last and bno == len(order) - 1)
        n = len(arr)
        for i, k in enumerate(arr):
            if i < n - 1 or confirmed:
                rel, ok = keys[k]
                if guard_accept(g, rel, ok, ctx[k]):
                    fed.append(feed_record(ctx[k], rel))
                    calls[rel] = calls.get(rel, 0) + 1
    return g, fed, calls

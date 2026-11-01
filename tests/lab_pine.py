"""LAB-1 test harness — runs the LOGIC section of ZoneComboLabXAU.pine itself (not a hand port).

Reuses the mechanical Pine-subset -> Python translator of tests/acc_pine.py (ACC-1) unchanged; only the logic markers, the
feed variables and a few built-ins differ. Anything outside the subset raises (no silent guessing); arithmetic / comparison on na
raises in Python (Pine would give na / false) and the logic section is written to never do that.

LabBroker extends acc_pine.Broker with what the lab needs (assumptions, NOT TradingView's emulator):
  * strategy.exit(id, from_entry, qty = q, stop, limit): an exit closes q of the open trade (the rest stays open, same entry id);
    a filled exit order is consumed; when the trade is flat its other exits are dropped
  * inside one segment of the bar path the exits fill in the order their prices are reached (stop / limit of every leg checked
    independently; equal prices fill in the order the exit orders were first placed)
  * strategy.closedtrades.profit = side x (exit - entry) x qty x pointvalue x USDJPY (no commission / spread / slippage)
  * strategy.convert_to_account(x) = x x USDJPY, strategy.convert_to_symbol(x) = x / USDJPY (fixed rate)
Runner: calc_on_every_tick = false -> one execution per bar at its close (historical and realtime alike: the realtime bar also
executes only on its closing tick). Feeds are given per bar as the values the request.security calls would deliver on that 5m bar.

Evidence class: PINE_NOT_VERIFIED.
"""
import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acc_pine as ap     # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PINE = os.path.join(ROOT, "ZoneComboLabXAU.pine")
LOGIC_BEGIN, LOGIC_END = "// ==== LAB Logic (begin) ", "// ==== LAB Logic (end) "
ap.NAMESPACES.update({"alert", "extend", "map"})
# map.new<K, V>() is outside the ACC tokenizer's generic pattern: add it (same form as array.new<T>)
ap.TOKEN_RE = __import__("re").compile(ap.TOKEN_RE.pattern.replace(r"(?P<gen>array\.new<[\w<>]+>)", r"(?P<gen>(?:array|map)\.new<[\w<>, ]+>)"), ap.re.X)
M5 = 300_000
SRC_OVERRIDE = None      # mutation tests: run a modified source instead of the file


_tok0 = ap.tokenize


def _tokenize(src):
    """acc_pine.tokenize with map.new<K, V> kept as map.new (acc_pine maps every generic constructor to array.new)."""
    toks = _tok0(src)
    gens = [m.group("gen") for m in ap.TOKEN_RE.finditer(src) if m.lastgroup == "gen"]
    gi = 0
    res = []
    for k, v in toks:
        if k == "id" and v == "array.new" and gi < len(gens):
            v = "map.new" if gens[gi].startswith("map.") else v
            gi += 1
        res.append((k, v))
    return res


ap.tokenize = _tokenize


def read_source(path=PINE):
    return open(path, encoding="utf-8").read()


def logic_section(src):
    i = src.index(LOGIC_BEGIN)
    j = src.index(LOGIC_END)
    return src[src.index("\n", i) + 1:j]


def transpile(src=None):
    src = src if src is not None else read_source()
    return ap.Translator().translate(ap.logical_lines(logic_section(src)))


def block(src, begin, end):
    i = src.index(begin)
    return src[src.index("\n", i) + 1:src.index(end, i)]


class LabBroker(ap.Broker):
    def __init__(self, usdjpy=150.0, pointvalue=1.0):
        super().__init__(usdjpy=usdjpy, pointvalue=pointvalue)
        self.exit_seq = {}

    def exit(self, id, from_entry, qty=None, stop=None, limit=None):
        if stop is None and limit is None:
            raise ap.PineRuntimeError("strategy.exit without stop / limit")
        if qty is not None and qty <= 0:
            raise ap.PineRuntimeError("strategy.exit qty <= 0")
        self.exits[id] = dict(from_id=from_entry, stop=stop, limit=limit, qty=qty)
        self.exit_seq.setdefault(id, len(self.exit_seq))
        self.log.append(("order_exit", self.bar, id, from_entry, qty, stop, limit))

    def convert_to_account(self, x):
        return x * self.usdjpy

    def ct_profit(self, i):
        return self.closed[i]["profit"]

    def ct_size(self, i):
        c = self.closed[i]
        return c["side"] * c["qty"]

    def _close_part(self, tr, qty, price, exit_id):
        q = min(qty, tr["qty"])
        self.closed.append(dict(id=tr["id"], side=tr["side"], qty=q, price=tr["price"], exit_id=exit_id, exit_price=price,
                                bar_in=tr["bar"], bar_out=self.bar,
                                profit=tr["side"] * (price - tr["price"]) * q * self.pointvalue * self.usdjpy))
        tr["qty"] -= q
        self.pos -= tr["side"] * q
        if abs(self.pos) < 1e-9:
            self.pos = 0.0
        self.log.append(("fill_exit", self.bar, tr["id"], exit_id, price, q))
        if tr["qty"] <= 1e-9:
            self.open_trades.remove(tr)
            for xid in [x for x, o in self.exits.items() if o["from_id"] == tr["id"]]:
                del self.exits[xid]

    def _close_trade(self, tr, price, exit_id):
        self._close_part(tr, tr["qty"], price, exit_id)

    def _exits_at(self, price, prev=None):
        for tr in list(self.open_trades):
            hits = []
            for xid, o in self.exits.items():
                if o["from_id"] != tr["id"]:
                    continue
                s, lim, side = o["stop"], o["limit"], tr["side"]
                hit = None
                if prev is None:
                    if s is not None and (price <= s if side == 1 else price >= s):
                        hit = price
                    elif lim is not None and (price >= lim if side == 1 else price <= lim):
                        hit = price
                else:
                    lo, hi = min(prev, price), max(prev, price)
                    cands = []
                    if s is not None and lo <= s <= hi and (s < prev if side == 1 else s > prev):
                        cands.append(s)
                    if lim is not None and lo <= lim <= hi and (lim > prev if side == 1 else lim < prev):
                        cands.append(lim)
                    if cands:
                        hit = min(cands, key=lambda x: abs(x - prev))
                if hit is not None:
                    hits.append((0 if prev is None else abs(hit - prev), self.exit_seq.get(xid, 0), xid, hit))
            for _, _, xid, hit in sorted(hits):
                if tr not in self.open_trades or xid not in self.exits:
                    continue
                q = self.exits[xid]["qty"]
                del self.exits[xid]
                self._close_part(tr, tr["qty"] if q is None else q, hit, xid)


FEED_DEFAULT = {}
for _k in (1, 2, 3):
    for _x in "ulia":
        FEED_DEFAULT[f"f{_k}{_x}"] = None
for _k in (1, 2, 3, 4):
    for _x in ("h", "ht", "l", "lt"):
        FEED_DEFAULT[f"s{_k}{_x}"] = None
    for _x in "cul":
        FEED_DEFAULT[f"d{_k}{_x}"] = None
    for _x in ("k", "kc", "c", "d", "t", "b"):
        FEED_DEFAULT[f"g{_k}{_x}"] = None
for _k in (1, 2, 3, 4):     # LAB-2: ZD from MtfPocFeedXAU (input.source); the old d* feeds stay for running the LAB-1 source
    for _x in "LUT":
        FEED_DEFAULT[f"zd{_x}{_k}"] = None
FEED_DEFAULT["zdProto"] = 10001.0
FEED_DEFAULT.update(zbMa1=None, zbMa2=None, labS1=None, labS2=None, labS3=None, satTf4=None, satTf1=None, labRangeOK=True)


class Runner:
    """bars: dicts with t (open time ms), o, h, l, c and any feed variable of FEED_DEFAULT (missing = its default, e.g. na).
    Feed variables persist only for the bar they are given on (request.security delivers a value on every bar: tests that need
    a value on several bars give it on each of them, see lab_sim.Feed)."""

    def __init__(self, overrides=None, usdjpy=150.0, src=None):
        self.src = src if src is not None else (SRC_OVERRIDE or read_source())
        self.code = compile(transpile(self.src), "<ZoneComboLabXAU logic>", "exec")
        self.inp = ap.inputs(self.src)
        for k in (overrides or {}):
            if k not in self.inp:
                raise KeyError("unknown input " + k)
        self.inp.update(overrides or {})
        self.broker = LabBroker(usdjpy=usdjpy)
        self.draws = []
        self.alerts = []
        env = ap.make_env(self.broker, self.draws)
        b = self.broker

        def _set(attr):
            def f(obj, v):
                if obj is None:
                    raise ap.PineRuntimeError("drawing call on na")
                setattr(obj, attr, v)
            return f
        env.update(
            array__insert=self._insert,
            map__new=lambda *a: {}, map__get=lambda m, k: m.get(k), map__put=lambda m, k, v: m.__setitem__(k, v),
            map__remove=lambda m, k: m.pop(k, None), map__clear=lambda m: m.clear(), map__size=len,
            map__contains=lambda m, k: k in m,
            alert=lambda msg, freq=None: self.alerts.append((self.bar_index, msg)), alert__freq_once_per_bar_close="once_per_bar_close",
            extend__right="right", extend__none="none",
            box__set_text=_set("text"), box__set_bgcolor=_set("bgcolor"), box__set_extend=_set("extend"),
            strategy__closedtrades__profit=b.ct_profit, strategy__closedtrades__size=b.ct_size,
            strategy__convert_to_account=b.convert_to_account, strategy__initial_capital=300000.0,
        )
        env.update(self.inp)
        env["_VARS"] = set()
        env["_VARIPS"] = set()
        env["__first__"] = True
        self.env = env
        self.bar_index = -1
        self.bars_done = []
        self.committed = None
        self.trace = []

    @staticmethod
    def _insert(arr, i, v):
        if i is None or i < 0 or i > len(arr):
            raise ap.PineRuntimeError(f"array.insert index {i} out of bounds (size {len(arr)})")
        arr.insert(i, v)

    def _set_series(self, bar):
        e, bd = self.env, self.bars_done
        e["barstate__ishistory"] = True
        e.update(open=bar["o"], high=bar["h"], low=bar["l"], close=bar["c"], time=bar["t"], time_close=bar["t"] + M5,
                 bar_index=self.bar_index, barstate__isconfirmed=True, is5mChart=True,
                 labC1=bd[-1][3] if bd else None, labO1=bd[-1][0] if bd else None,
                 labH2=bd[-2][1] if len(bd) >= 2 else None, labL2=bd[-2][2] if len(bd) >= 2 else None,
                 syminfo__pointvalue=self.broker.pointvalue,
                 strategy__position_size=self.broker.pos, strategy__opentrades=self.broker.opentrades,
                 strategy__closedtrades=self.broker.closedtrades)
        for k, v in FEED_DEFAULT.items():
            e[k] = bar.get(k, v)

    def step(self, bar):
        for k in bar:
            if k not in ("t", "o", "h", "l", "c") and k not in FEED_DEFAULT:
                raise KeyError("unknown feed " + k)
        self.bar_index += 1
        self.broker.bar = self.bar_index
        prev = None
        for p in ap.Broker.bar_path(bar["o"], bar["h"], bar["l"], bar["c"]):
            self.broker.point(p, prev)
            prev = p
        if self.committed is not None:
            # one deepcopy of all var / varip state together keeps objects shared between variables (Pine references)
            self.env.update(copy.deepcopy(self.committed))
        self._set_series(bar)
        exec(self.code, self.env)
        self.env["__first__"] = False
        self.committed = copy.deepcopy({k: self.env[k] for k in self.env["_VARS"] | self.env["_VARIPS"]})
        self.bars_done.append((bar["o"], bar["h"], bar["l"], bar["c"]))
        o = self.env["o"]
        self.trace.append(dict(bar=self.bar_index, state=o.state, id=o.id, side=o.side, stop=o.stop, be=o.be, fill=o.fill,
                               legPx=list(o.legPx), legLots=list(o.legLots), pos=self.broker.pos,
                               waits=[(w.key, w.side, w.cat, w.sBar, w.lBar) for w in self.env["lbWaits"]],
                               tevs=[(t.kind, t.side, t.eBar, t.used) for t in self.env["lbTevs"]]))
        return self

    def run(self, bars):
        for b in bars:
            self.step(b)
        return self

    def __getitem__(self, k):
        return self.env[k]

    # ---- helpers for tests ----
    def entries(self):
        return [e for e in self.broker.log if e[0] == "order_entry"]

    def fills(self):
        return [e for e in self.broker.log if e[0] in ("fill_entry", "fill_exit")]

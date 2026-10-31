"""ACC-1 test harness — runs the LOGIC section of AccumStrategyXAU.pine itself (not a hand port).

  transpile() : a mechanical Pine-subset -> Python translator for the text between the ACC Logic markers
                (types, functions, var / declarations, := / +=, if / else if / else, for .. to .., while, break,
                ternary, and / or / not, na / nz, UDT .new / fields, array.*, math.*, str.*, label.* / line.* stubs,
                strategy.* through the Broker below). Anything outside the subset raises (no silent guessing).
                Arithmetic / comparison on na raises in Python (Pine would give na / false): the logic section is
                written to never do that, and a test run that hits it fails loudly.
  inputs()    : every `name = input.xxx(default, ...)` default of the file (overridable per test).
  Broker      : a small TradingView-like broker emulator (assumptions listed on the class).
  Runner      : executes bars historically (one execution at the close, all bars confirmed) or as realtime ticks
                (one execution per tick, var state rolled back to the last committed bar before each tick, orders kept).

Evidence class: PINE_NOT_VERIFIED. The translator gives Pine's control flow / arithmetic on the subset; TradingView's
compiler, request.security, broker emulator and drawing limits are not reproduced.
"""
import copy
import math
import os
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PINE = os.path.join(ROOT, "AccumStrategyXAU.pine")
LOGIC_BEGIN, LOGIC_END = "// ==== ACC Logic (begin) ", "// ==== ACC Logic (end) "

NAMESPACES = {"strategy", "array", "math", "str", "label", "line", "color", "barstate", "syminfo", "timeframe",
              "xloc", "size", "plot", "display", "barmerge", "ta", "request", "input", "runtime", "box"}
TYPE_WORDS = {"float", "int", "bool", "string", "color", "line", "label", "box"}


# ============================================================================
# source helpers
# ============================================================================
def read_source(path=PINE):
    return open(path, encoding="utf-8").read()


def logic_section(src):
    i = src.index(LOGIC_BEGIN)
    j = src.index(LOGIC_END)
    return src[src.index("\n", i) + 1:j]


def strip_comment(line):
    out, q = [], False
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == '"' and (i == 0 or line[i - 1] != "\\"):
            q = not q
        if not q and line.startswith("//", i):
            break
        out.append(ch)
        i += 1
    return "".join(out).rstrip()


def logical_lines(text):
    """(indent level, text) per logical line; continuation lines (indent not a multiple of 4) are joined."""
    out = []
    for raw in text.split("\n"):
        line = strip_comment(raw)
        if not line.strip():
            continue
        ind = len(line) - len(line.lstrip(" "))
        if ind % 4 != 0:
            if not out:
                raise SyntaxError("continuation without a statement: " + raw)
            lvl, prev = out[-1]
            out[-1] = (lvl, prev + " " + line.strip())
            continue
        out.append((ind // 4, line.strip()))
    return out


# ============================================================================
# expressions
# ============================================================================
TOKEN_RE = re.compile(r"""
    (?P<ws>\s+)
  | (?P<num>\d+\.\d*(?:[eE][-+]?\d+)?|\d*\.\d+(?:[eE][-+]?\d+)?|\d+(?:[eE][-+]?\d+)?)
  | (?P<str>"(?:[^"\\]|\\.)*")
  | (?P<gen>array\.new<[\w<>]+>)
  | (?P<id>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)
  | (?P<op>==|!=|<=|>=|:=|\+=|-=|\*=|/=|=>|[-+*/%<>?:(),\[\]=])
""", re.X)


def tokenize(s):
    toks, pos = [], 0
    while pos < len(s):
        m = TOKEN_RE.match(s, pos)
        if not m:
            raise SyntaxError(f"cannot tokenize at {s[pos:pos + 30]!r} in {s!r}")
        pos = m.end()
        kind = m.lastgroup
        if kind == "ws":
            continue
        val = m.group(kind)
        if kind == "gen":
            kind, val = "id", "array.new"
        toks.append((kind, val))
    toks.append(("end", ""))
    return toks


def map_name(name):
    if name == "na":
        return "None"
    if name == "true":
        return "True"
    if name == "false":
        return "False"
    head = name.split(".")[0]
    if head in NAMESPACES:
        return name.replace(".", "__")
    return name


BIN_PREC = {"or": 2, "and": 3, "==": 4, "!=": 4, "<": 5, ">": 5, "<=": 5, ">=": 5, "+": 6, "-": 6, "*": 7, "/": 7, "%": 7}


class ExprParser:
    def __init__(self, toks):
        self.t, self.i = toks, 0

    def peek(self):
        return self.t[self.i]

    def take(self, val=None):
        tok = self.t[self.i]
        if val is not None and tok[1] != val:
            raise SyntaxError(f"expected {val!r}, got {tok!r}")
        self.i += 1
        return tok

    def parse(self):
        e = self.ternary()
        if self.peek()[0] != "end":
            raise SyntaxError(f"trailing tokens {self.t[self.i:]}")
        return e

    def ternary(self):
        c = self.binary(1)
        if self.peek()[1] == "?":
            self.take("?")
            a = self.ternary()
            self.take(":")
            b = self.ternary()
            return f"({a} if {c} else {b})"
        return c

    def binop(self):
        k, v = self.peek()
        if k == "id" and v in ("and", "or"):
            return v
        if k == "op" and v in BIN_PREC:
            return v
        return None

    def binary(self, minp):
        left = self.unary()
        while True:
            op = self.binop()
            if op is None or BIN_PREC[op] < minp:
                return left
            self.take()
            right = self.binary(BIN_PREC[op] + 1)
            left = f"({left} {op} {right})"

    def unary(self):
        k, v = self.peek()
        if k == "id" and v == "not":
            self.take()
            return f"(not {self.unary()})"
        if k == "op" and v in ("-", "+"):
            self.take()
            return f"({v}{self.unary()})"
        return self.postfix()

    def postfix(self):
        k, v = self.take()
        if k == "num":
            return v
        if k == "str":
            return v
        if k == "op" and v == "(":
            e = self.ternary()
            self.take(")")
            return f"({e})"
        if k != "id":
            raise SyntaxError(f"unexpected token {(k, v)}")
        if self.peek()[1] == "[":
            raise SyntaxError(f"history reference {v}[...] is outside the supported subset")
        if self.peek()[1] == "(":
            self.take("(")
            args = []
            while self.peek()[1] != ")":
                if self.peek()[0] == "id" and self.t[self.i + 1][1] == "=":
                    kw = self.take()[1]
                    self.take("=")
                    args.append(f"{kw}={self.ternary()}")
                else:
                    args.append(self.ternary())
                if self.peek()[1] == ",":
                    self.take(",")
            self.take(")")
            fn = {"na": "_na", "int": "_int", "float": "_float"}.get(v, map_name(v))
            if v.endswith(".new") and v.split(".")[0] not in NAMESPACES:
                fn = v.split(".")[0] + ".new"
            return f"{fn}({', '.join(args)})"
        return map_name(v)


def expr(s):
    return ExprParser(tokenize(s)).parse()


# ============================================================================
# statements
# ============================================================================
DECL_RE = re.compile(r"^(?:(var|varip)\s+)?(?:(array<[\w<>]+>|map<[\w,<> ]+>|[A-Za-z_]\w*)\s+)?([A-Za-z_]\w*)\s*=(?!=)\s*(.+)$")
ASSIGN_RE = re.compile(r"^([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*(:=|\+=|-=|\*=|/=)\s*(.+)$")
TUPLE_RE = re.compile(r"^\[([\w\s,]+)\]\s*=\s*(.+)$")
FOR_RE = re.compile(r"^for\s+(\w+)\s*=\s*(.+?)\s+to\s+(.+)$")
FUNC_RE = re.compile(r"^([A-Za-z_]\w*)\((.*)\)\s*=>\s*(.*)$")


def param_names(p):
    out = []
    for part in [x.strip() for x in p.split(",") if x.strip()]:
        out.append(part.split()[-1])
    return out


class Translator:
    def __init__(self, known_types=()):
        self.types = set(known_types)
        self.out = []

    def emit(self, lvl, s):
        self.out.append("    " * lvl + s)

    def translate(self, lines):
        i = 0
        while i < len(lines):
            i = self.stmt(lines, i, 0, 0, top=True)
        return "\n".join(self.out) + "\n"

    def block(self, lines, i, lvl, plvl, in_func=False):
        """statements at Pine level lvl starting at i; emitted at Python level plvl. Returns next index."""
        start = len(self.out)
        while i < len(lines) and lines[i][0] >= lvl:
            if lines[i][0] > lvl:
                raise SyntaxError(f"unexpected indent: {lines[i]}")
            last = in_func and (i + 1 >= len(lines) or lines[i + 1][0] < lvl)
            i = self.stmt(lines, i, lvl, plvl, last_in_func=last)
        if len(self.out) == start:
            self.emit(plvl, "pass")
        return i

    def stmt(self, lines, i, lvl, plvl, top=False, last_in_func=False):
        _, s = lines[i]
        # type definition
        m = re.match(r"^type\s+(\w+)$", s)
        if m:
            name = m.group(1)
            self.types.add(name)
            fields = []
            j = i + 1
            while j < len(lines) and lines[j][0] > lvl:
                fs = lines[j][1]
                fm = re.match(r"^(?:[\w<>]+)\s+(\w+)(?:\s*=\s*(.+))?$", fs)
                if not fm:
                    raise SyntaxError("bad field " + fs)
                fields.append((fm.group(1), expr(fm.group(2)) if fm.group(2) else "None"))
                j += 1
            self.emit(plvl, f"class {name}(_UDT):")
            self.emit(plvl + 1, f"_fields = {[f for f, _ in fields]!r}")
            self.emit(plvl + 1, f"_defaults = [{', '.join(d for _, d in fields)}]")
            return j
        # function definition
        m = FUNC_RE.match(s)
        if m and not s.startswith(("if ", "for ", "while ")):
            name, params, body = m.groups()
            self.emit(plvl, f"def {name}({', '.join(param_names(params))}):")
            if body.strip():
                self.emit(plvl + 1, "return " + expr(body))
                return i + 1
            return self.block(lines, i + 1, lvl + 1, plvl + 1, in_func=True)
        if s.startswith("if "):
            self.emit(plvl, f"if {expr(s[3:])}:")
            j = self.block(lines, i + 1, lvl + 1, plvl + 1)
            while j < len(lines) and lines[j][0] == lvl and (lines[j][1].startswith("else if ") or lines[j][1] == "else"):
                t = lines[j][1]
                if t == "else":
                    self.emit(plvl, "else:")
                else:
                    self.emit(plvl, f"elif {expr(t[8:])}:")
                j = self.block(lines, j + 1, lvl + 1, plvl + 1)
            if last_in_func:
                raise SyntaxError("an if block as a function's return value is outside the subset")
            return j
        m = FOR_RE.match(s)
        if m:
            v, a, b = m.groups()
            if " by " in b:
                raise SyntaxError("for .. by is outside the subset")
            self.emit(plvl, f"for {v} in _rng({expr(a)}, {expr(b)}):")
            return self.block(lines, i + 1, lvl + 1, plvl + 1)
        if s.startswith("while "):
            self.emit(plvl, f"while {expr(s[6:])}:")
            return self.block(lines, i + 1, lvl + 1, plvl + 1)
        if s in ("break", "continue"):
            self.emit(plvl, s)
            return i + 1
        m = TUPLE_RE.match(s)
        if m:
            names = [x.strip() for x in m.group(1).split(",")]
            self.emit(plvl, f"{', '.join(names)} = {expr(m.group(2))}")
            return i + 1
        m = ASSIGN_RE.match(s)
        if m:
            target, op, e = m.groups()
            pyop = "=" if op == ":=" else op
            self.emit(plvl, f"{target} {pyop} {expr(e)}")
            return i + 1
        m = DECL_RE.match(s)
        if m and (m.group(2) is None or m.group(2) in TYPE_WORDS or m.group(2) in self.types
                  or m.group(2).startswith(("array<", "map<"))):
            var, _typ, name, e = m.groups()
            if var:
                if not top:
                    raise SyntaxError("var outside the global scope is outside the subset: " + s)
                self.emit(plvl, "if __first__:")
                self.emit(plvl + 1, f"{name} = {expr(e)}")
                self.emit(plvl, f"{'_VARIPS' if var == 'varip' else '_VARS'}.add({name!r})")
            else:
                self.emit(plvl, f"{name} = {expr(e)}")
            if last_in_func:
                self.emit(plvl, f"return {name}")
            return i + 1
        if s.startswith("["):
            if not last_in_func:
                raise SyntaxError("tuple expression outside a return position: " + s)
            inner = s[1:-1]
            self.emit(plvl, "return (" + ", ".join(expr(x) for x in split_top(inner)) + ")")
            return i + 1
        # expression statement
        e = expr(s)
        self.emit(plvl, ("return " if last_in_func else "") + e)
        return i + 1


def split_top(s):
    parts, depth, cur, q = [], 0, [], False
    for ch in s:
        if ch == '"':
            q = not q
        if not q:
            if ch in "([":
                depth += 1
            elif ch in ")]":
                depth -= 1
            elif ch == "," and depth == 0:
                parts.append("".join(cur))
                cur = []
                continue
        cur.append(ch)
    parts.append("".join(cur))
    return [p.strip() for p in parts]


def transpile(src=None):
    src = src if src is not None else read_source()
    return Translator().translate(logical_lines(logic_section(src)))


# ============================================================================
# inputs
# ============================================================================
INPUT_RE = re.compile(r"^(\w+)\s*=\s*input\.(bool|int|float|string|timeframe)\((.+)$", re.M)


def inputs(src=None):
    src = src if src is not None else read_source()
    out = {}
    for name, kind, rest in INPUT_RE.findall(src):
        first = split_top(rest.rsplit(")", 1)[0] if rest.rstrip().endswith(")") else rest)[0]
        first = first.strip()
        if kind == "bool":
            out[name] = first == "true"
        elif kind == "int":
            out[name] = int(first)
        elif kind == "float":
            out[name] = float(first)
        else:
            out[name] = first.strip('"')
    return out


# ============================================================================
# runtime library (the Pine built-ins used by the logic section)
# ============================================================================
class PineRuntimeError(Exception):
    pass


class PineScriptStopped(Exception):
    """runtime.error() called by the script."""


def _runtime_error(msg):
    raise PineScriptStopped(msg)


class _UDT:
    _fields, _defaults = [], []

    def __init__(self, *args, **kw):
        if len(args) > len(self._fields):
            raise PineRuntimeError("too many UDT arguments")
        for f, d in zip(self._fields, self._defaults):
            setattr(self, f, d)
        for f, a in zip(self._fields, args):
            setattr(self, f, a)
        for k, v in kw.items():
            if k not in self._fields:
                raise PineRuntimeError("unknown UDT field " + k)
            setattr(self, k, v)

    @classmethod
    def new(cls, *args, **kw):
        return cls(*args, **kw)

    def __setattr__(self, k, v):
        if k not in self._fields:
            raise PineRuntimeError("unknown UDT field " + k)
        object.__setattr__(self, k, v)

    def __repr__(self):
        return f"{type(self).__name__}({', '.join(f'{f}={getattr(self, f)!r}' for f in self._fields if f[:2] not in ('ln', 'lb'))})"


def _rng(a, b):
    a, b = int(a), int(b)
    return range(a, b + 1) if a <= b else range(a, b - 1, -1)


def _na(x):
    return x is None


def _int(x):
    return None if x is None else int(x)


def _float(x):
    return None if x is None else float(x)


def nz(x, y=0):
    return y if x is None else x


def _pine_round(x):
    if x is None:
        return None
    return math.floor(x + 0.5) if x >= 0 else -math.floor(-x + 0.5)


def _chk(arr, i):
    if i is None or i < 0 or i >= len(arr):
        raise PineRuntimeError(f"array index {i} out of bounds (size {len(arr)})")


def _array_get(arr, i):
    _chk(arr, i)
    return arr[i]


def _array_set(arr, i, v):
    _chk(arr, i)
    arr[i] = v


def _array_remove(arr, i):
    _chk(arr, i)
    return arr.pop(i)


def _array_shift(arr):
    if not arr:
        raise PineRuntimeError("array.shift on an empty array")
    return arr.pop(0)


class Drawing:
    def __init__(self, kind, args, kw):
        self.kind, self.args, self.kw, self.deleted = kind, args, dict(kw), False
        self.text = kw.get("text", args[2] if kind == "label" and len(args) > 2 else "")


def make_env(broker, draw_log):
    def label_new(*a, **k):
        d = Drawing("label", a, k)
        draw_log.append(d)
        return d

    def line_new(*a, **k):
        d = Drawing("line", a, k)
        draw_log.append(d)
        return d

    def box_new(*a, **k):
        d = Drawing("box", a, k)
        draw_log.append(d)
        return d

    def _set(attr):
        def f(obj, v):
            if obj is None:
                raise PineRuntimeError("drawing call on na")
            setattr(obj, attr, v)
        return f

    def _delete(obj):
        if obj is not None:
            obj.deleted = True

    def _get_text(obj):
        if obj is None:
            raise PineRuntimeError("label.get_text on na")
        return obj.text

    def tostring(x, fmt=None):
        if x is None:
            return "NaN"
        if fmt == "#.##":
            s = f"{x:.2f}".rstrip("0").rstrip(".")
            return s
        if isinstance(x, float) and x.is_integer():
            return str(int(x))
        return str(x)

    def format_time(t, fmt, tz):
        d = datetime.fromtimestamp(t / 1000, tz=timezone.utc).astimezone(ZoneInfo(tz))
        return d.strftime(fmt.replace("yyyy", "%Y").replace("MM", "%m").replace("dd", "%d").replace("HH", "%H").replace("mm", "%M"))

    def hour(t, tz):
        return datetime.fromtimestamp(t / 1000, tz=timezone.utc).astimezone(ZoneInfo(tz)).hour

    def minute(t, tz):
        return datetime.fromtimestamp(t / 1000, tz=timezone.utc).astimezone(ZoneInfo(tz)).minute

    def mmax(*a):
        if any(x is None for x in a):
            raise PineRuntimeError("math.max on na")
        return max(a)

    def mmin(*a):
        if any(x is None for x in a):
            raise PineRuntimeError("math.min on na")
        return min(a)

    env = dict(
        _UDT=_UDT, _rng=_rng, _na=_na, _int=_int, _float=_float, nz=nz,
        math__max=mmax, math__min=mmin, math__abs=abs, math__floor=math.floor, math__round=_pine_round,
        math__sign=lambda x: (x > 0) - (x < 0),
        array__new=lambda *a: list(a[1:]) if a else [], array__new_float=lambda n=0, v=None: [v] * n, array__new_int=lambda n=0, v=None: [v] * n,
        array__from=lambda *a: list(a), array__size=len, array__get=_array_get, array__set=_array_set,
        array__push=lambda arr, v: arr.append(v), array__remove=_array_remove, array__shift=_array_shift,
        array__clear=lambda arr: arr.clear(),
        str__tostring=tostring, str__format_time=format_time, hour=hour, minute=minute,
        label__new=label_new, label__set_text=_set("text"), label__get_text=_get_text, label__delete=_delete,
        label__set_textcolor=_set("textcolor"), label__set_color=_set("color"),
        line__new=line_new, line__set_color=_set("color"), line__set_style=_set("style"), line__delete=_delete,
        box__new=box_new, box__set_right=_set("right"), box__delete=_delete,
        color__maroon="maroon", color__navy="navy", color__purple="purple", size__tiny="tiny",
        label__style_label_up="up", label__style_label_down="down", label__style_label_lower_left="ll",
        label__style_label_upper_left="ul", line__style_dotted="dotted",
        color__new=lambda c, t=0: (c, t), color__teal="teal", color__orange="orange", color__fuchsia="fuchsia",
        color__gray="gray", color__green="green", color__red="red", color__white="white",
        xloc__bar_time="bar_time", size__small="small",
        strategy__long=1, strategy__short=-1, runtime__error=_runtime_error,
        strategy__entry=broker.entry, strategy__exit=broker.exit, strategy__close=broker.close,
        strategy__cancel=broker.cancel, strategy__convert_to_symbol=broker.convert_to_symbol,
        strategy__opentrades__entry_id=broker.ot_entry_id, strategy__opentrades__entry_price=broker.ot_entry_price,
        strategy__closedtrades__entry_id=broker.ct_entry_id, strategy__closedtrades__entry_price=broker.ct_entry_price,
        strategy__closedtrades__exit_price=broker.ct_exit_price, strategy__closedtrades__exit_id=broker.ct_exit_id,
    )
    return env


# ============================================================================
# broker emulator
# ============================================================================
class Broker:
    """TradingView-like order handling, as assumed here (NOT TradingView's emulator):
      * market entry / close orders sent during an execution fill at the next price point (historical: next bar open;
        ticks: the next tick); strategy.entry in the opposite direction reverses: closes the open trades and opens qty,
        the size being decided when the order fills; with pyramiding 0 an entry in the same direction is ignored
      * strategy.exit (stop / limit) works on the open trade of its from_entry; same exit id = modified; it is dropped
        when that trade closes; a stop / limit already passed at a price point fills at that point's price (gap),
        inside a segment at its own price
      * historical bar path: open -> high -> low -> close when the high is nearer the open, else open -> low -> high
        -> close; ticks: the given tick prices in order
      * at one price point: pending market orders first, then exits; an exit changed by an execution at the previous point
        and already passed there fills at that point's price"""

    def __init__(self, usdjpy=150.0, pointvalue=1.0):
        self.usdjpy, self.pointvalue = usdjpy, pointvalue
        self.pos = 0.0
        self.open_trades = []          # dict(id, side, qty, price, bar)
        self.closed = []               # dict(id, side, qty, price, exit_id, exit_price, bar_in, bar_out)
        self.pend = []                 # market orders: ("entry", id, side, qty) / ("close", id)
        self.exits = {}                # exit id -> dict(from_id, stop, limit)
        self.log = []
        self.bar = 0
        self.max_abs_pos = 0.0

    # ---- strategy.* --------------------------------------------------------
    def entry(self, id, direction, qty=None):
        self.pend = [p for p in self.pend if not (p[0] == "entry" and p[1] == id)]
        self.pend.append(("entry", id, direction, qty))
        self.log.append(("order_entry", self.bar, id, direction, qty))

    def exit(self, id, from_entry, stop=None, limit=None):
        if stop is None and limit is None:
            raise PineRuntimeError("strategy.exit without stop / limit")
        self.exits[id] = dict(from_id=from_entry, stop=stop, limit=limit)
        self.log.append(("order_exit", self.bar, id, from_entry, stop, limit))

    def close(self, id):
        self.pend.append(("close", id))
        self.log.append(("order_close", self.bar, id))

    def cancel(self, id):
        self.pend = [p for p in self.pend if not (p[0] == "entry" and p[1] == id)]
        self.exits.pop(id, None)
        self.log.append(("cancel", self.bar, id))

    def convert_to_symbol(self, x):
        return x / self.usdjpy

    @property
    def opentrades(self):
        return len(self.open_trades)

    @property
    def closedtrades(self):
        return len(self.closed)

    def ot_entry_id(self, i):
        return self.open_trades[i]["id"]

    def ot_entry_price(self, i):
        return self.open_trades[i]["price"]

    def ct_entry_id(self, i):
        return self.closed[i]["id"]

    def ct_entry_price(self, i):
        return self.closed[i]["price"]

    def ct_exit_price(self, i):
        return self.closed[i]["exit_price"]

    def ct_exit_id(self, i):
        return self.closed[i]["exit_id"]

    # ---- fills ---------------------------------------------------------------
    def _close_trade(self, tr, price, exit_id):
        self.open_trades.remove(tr)
        self.closed.append(dict(id=tr["id"], side=tr["side"], qty=tr["qty"], price=tr["price"], exit_id=exit_id,
                                exit_price=price, bar_in=tr["bar"], bar_out=self.bar))
        self.pos -= tr["side"] * tr["qty"]
        for xid in [x for x, o in self.exits.items() if o["from_id"] == tr["id"]]:
            del self.exits[xid]
        self.log.append(("fill_exit", self.bar, tr["id"], exit_id, price))

    def _market(self, price):
        pend, self.pend = self.pend, []
        for p in pend:
            if p[0] == "close":
                for tr in [t for t in self.open_trades if t["id"] == p[1]]:
                    self._close_trade(tr, price, "close")
            else:
                _, id, side, qty = p
                if self.pos != 0 and (self.pos > 0) == (side > 0):
                    self.log.append(("ignored_entry", self.bar, id))
                    continue
                for tr in list(self.open_trades):
                    self._close_trade(tr, price, id)
                self.open_trades.append(dict(id=id, side=side, qty=qty, price=price, bar=self.bar))
                self.pos += side * qty
                self.log.append(("fill_entry", self.bar, id, side, qty, price))
        self.max_abs_pos = max(self.max_abs_pos, abs(self.pos))

    def _exits_at(self, price, prev=None):
        """check exits at a point (prev None: gap check at the point) or along the segment prev -> price."""
        for tr in list(self.open_trades):
            for xid, o in list(self.exits.items()):
                if o["from_id"] != tr["id"] or tr not in self.open_trades:
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
                    self._close_trade(tr, hit, xid)
                    break

    def point(self, p, prev=None):
        """one price point: pending market orders fill here, then exits (prev None = gap check at the point, else the segment
        prev -> p). Returns the number of fills at this point."""
        n0 = sum(1 for e in self.log if e[0] in ("fill_entry", "fill_exit"))
        self._market(p)
        if prev is not None:
            self._exits_at(prev)          # orders changed by an execution at the previous point: already through -> fill there
        self._exits_at(p, prev)
        return sum(1 for e in self.log if e[0] in ("fill_entry", "fill_exit")) - n0

    def run_points(self, points):
        """points: price points of one bar / tick group."""
        prev = None
        for p in points:
            self.point(p, prev)
            prev = p

    @staticmethod
    def bar_path(o, h, l, c):
        return [o, h, l, c] if abs(h - o) < abs(l - o) else [o, l, h, c]


# ============================================================================
# runner
# ============================================================================
M5 = 300_000


class Runner:
    """bars: dicts with t (open time ms), o, h, l, c, feed = {1: (u, l, id, acc), 2: ..., 3: ...} (missing = na),
    optional ticks = [prices] (realtime mode for that bar; the last tick must equal c)."""

    def __init__(self, overrides=None, usdjpy=150.0, src=None, recalc_fills=False, recalc_confirmed=True, varip_rollback=False,
                 history_ticks=None, tick_segments=False):
        """recalc_fills: emulate the Properties setting "Recalculate: After order is filled" (calc_on_order_fills = true): one
        extra execution after every price point with a fill. On historical bars it sees the bar's FINAL values (the documented
        lookahead) with barstate.isconfirmed = recalc_confirmed (not documented; True = worst case); on ticks the tick's values.
        var state is rolled back before every execution of a bar; varip too only when varip_rollback (not documented)."""
        self.recalc_fills, self.recalc_confirmed, self.varip_rollback = recalc_fills, recalc_confirmed, varip_rollback
        # ACC-3: bars given with ticks run as HISTORICAL bars ("On history bar tick" / calc_on_every_history_tick):
        #   None            -> ticks are realtime (barstate.ishistory false, isconfirmed on the last tick only)
        #   "all_confirmed" -> barstate.ishistory true and barstate.isconfirmed true on EVERY tick (the behaviour cited for the
        #                      setting; not verified here)
        #   "last_confirmed"-> barstate.ishistory true, isconfirmed on the last tick only (hypothetical oracle: what the setting
        #                      would give if the final tick were identifiable)
        # tick_segments: exits between two ticks fill at their own price (a path, not a gap at every tick)
        self.history_ticks, self.tick_segments = history_ticks, tick_segments
        self.src = src if src is not None else read_source()
        self.code = compile(transpile(self.src), "<AccumStrategyXAU logic>", "exec")
        self.inp = inputs(self.src)
        for k in (overrides or {}):
            if k not in self.inp:
                raise KeyError("unknown input " + k)
        self.inp.update(overrides or {})
        self.broker = Broker(usdjpy=usdjpy)
        self.draws = []
        self.env = make_env(self.broker, self.draws)
        self.env.update(self.inp)
        self.env["_VARS"] = set()
        self.env["_VARIPS"] = set()
        self.varip_bar_start = None
        self.env["__first__"] = True
        self.bar_index = -1
        self.prev_close = None
        self.bars_done = []           # (o, h, l, c) of the completed bars (history references)
        self.committed = None
        self.trace = []

    def _set_series(self, b, o, h, l, c, confirmed, history=True):
        e = self.env
        e["barstate__ishistory"] = history
        e.update(open=o, high=h, low=l, close=c, time=b["t"], time_close=b["t"] + M5, bar_index=self.bar_index,
                 barstate__isconfirmed=confirmed, is5mChart=True, acPrevClose=self.prev_close,
                 acH2=self.bars_done[-2][1] if len(self.bars_done) >= 2 else None,      # ACC-5A: high[2] / low[2] / open[1] / close[1]
                 acL2=self.bars_done[-2][2] if len(self.bars_done) >= 2 else None,
                 acO1=self.bars_done[-1][0] if self.bars_done else None,
                 acC1=self.bars_done[-1][3] if self.bars_done else None,
                 **{f"dv{x}{k}": (b.get("dv", {}).get(k, (None, None, None))["hlt".index(x)]) for k in (1, 2, 3, 4) for x in "hlt"},
                 syminfo__pointvalue=self.broker.pointvalue,
                 strategy__position_size=self.broker.pos, strategy__opentrades=self.broker.opentrades,
                 strategy__closedtrades=self.broker.closedtrades)
        fd = b.get("feed", {})
        for k in (1, 2, 3):
            u, l2, i, a = fd.get(k, (None, None, None, None))
            e[f"f{k}u"], e[f"f{k}l"], e[f"f{k}i"], e[f"f{k}a"] = u, l2, i, a

    def _exec(self):
        exec(self.code, self.env)
        self.env["__first__"] = False

    def _snapshot(self):
        return {k: copy.deepcopy(self.env[k]) for k in self.env["_VARS"]}

    def _rollback(self):
        if self.committed is not None:
            for k, v in self.committed.items():
                self.env[k] = copy.deepcopy(v)
        if self.varip_rollback and self.varip_bar_start is not None:
            for k, v in self.varip_bar_start.items():
                self.env[k] = copy.deepcopy(v)

    def step(self, b):
        self.bar_index += 1
        self.broker.bar = self.bar_index
        self.varip_bar_start = {k: copy.deepcopy(self.env[k]) for k in self.env["_VARIPS"]}
        ticks = b.get("ticks")
        if ticks is None:
            prev = None
            for p in Broker.bar_path(b["o"], b["h"], b["l"], b["c"]):
                n = self.broker.point(p, prev)
                prev = p
                if n and self.recalc_fills:
                    self._rollback()
                    self._set_series(b, b["o"], b["h"], b["l"], b["c"], self.recalc_confirmed)
                    self._exec()
            self._rollback()
            self._set_series(b, b["o"], b["h"], b["l"], b["c"], True)
            self._exec()
        else:
            assert ticks[0] == b["o"] and ticks[-1] == b["c"] and max(ticks) == b["h"] and min(ticks) == b["l"]
            hi = lo = ticks[0]
            hist = self.history_ticks is not None
            prev = None
            for n, p in enumerate(ticks):
                nf = self.broker.point(p, prev if self.tick_segments else None)   # market orders, then exits
                prev = p
                hi, lo = max(hi, p), min(lo, p)
                last = n == len(ticks) - 1
                conf = True if self.history_ticks == "all_confirmed" else last
                if nf and self.recalc_fills and not last:
                    self._rollback()
                    self._set_series(b, ticks[0], hi, lo, p, False, history=hist)
                    self._exec()
                self._rollback()
                self._set_series(b, ticks[0], hi, lo, p, conf, history=hist)
                self._exec()
        self.committed = self._snapshot()
        self.prev_close = b["c"]
        self.bars_done.append((b["o"], b["h"], b["l"], b["c"]))
        self.trace.append(dict(bar=self.bar_index, t=b["t"], **{k: copy.deepcopy(self.env[k]) for k in
                                                                 ("oState", "oSide", "oId", "oSL", "oTP", "oStop", "oBE", "oFill", "oPat", "oTf", "oQty", "oRRPlan", "oRRReal")},
                               pos=self.broker.pos))
        return self

    def run(self, bars):
        for b in bars:
            self.step(b)
        return self

    def __getitem__(self, k):
        return self.env[k]

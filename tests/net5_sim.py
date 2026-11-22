"""PM-NET5（PointMasterNet5Strategy.pine）の固定ケース。

Pine ファイルの「NET5 Logic」区間そのものを tests/acc_pine.py の変換器（Pine サブセット → Python）で実行する（手書きの移植ではない）。
入力は Source（PM-A/B/C-515）の STUDY DATA / META BUS を、Source の f_study() と同じ式で合成したもの。
約定は acc_pine.Broker（TradingView 風の仮定。成行 = 次の価格点 / 履歴足の経路 O→H→L→C か O→L→H→C）に
strategy.exit の loss（tick）を足したもの。TradingView のコンパイラ・ブローカーエミュレーターそのものではない。

実行 : python3 tests/net5_sim.py
"""
import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acc_pine as ap  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PINE = os.path.join(ROOT, "PointMasterNet5Strategy.pine")
BEGIN, END = "// ==== NET5 Logic (begin)", "// ==== NET5 Logic (end)"
M5 = 300_000
BUS_BASE = 1577836800000
T0 = 1767571200000          # 2026-01-05 00:00 UTC（月曜）
MINTICK = 0.01

ok = 0


def check(name, cond):
    global ok
    assert cond, name
    ok += 1
    print("OK ", name)


# ---------------------------------------------------------------------------
# Source の出力（PM-A/B/C-515 f_study と同じ配置）
# ---------------------------------------------------------------------------
LOGICS = {"05": (1, 5, "d05", "m05"), "09": (1, 9, "d09", "m09"), "16": (2, 16, "d16", "m16"),
          "15": (2, 15, "d15", "m15"), "24": (3, 24, "d24", "m24")}


def meta(sid, lg, slot, st=0, adopt=1, fmt=2, tf=1):
    return float(fmt + 4 * sid + 16 * tf + 64 * lg + 2048 * st + 16384 * adopt + 32768 * slot)


def data(slot, rawL=False, rawS=False, curL=False, curS=False, negL=False, negS=False, nb=True, junk=0):
    v = (1 if rawL else 0) + (2 if rawS else 0) + (4 if curL else 0) + (8 if curS else 0)
    v += (256 if negL else 0) + (512 if negS else 0)
    # 使わないフィールド（PRE 強度・期限切れ・経過本数）にも値を入れて、読み飛ばされることを確かめる
    v += 16 * (junk % 4) + 1024 * (junk % 2) + 4096 * (junk % 64) + 262144 * ((junk + 3) % 64) + 16777216 * ((junk + 7) % 64)
    v += (2 ** 36 if nb else 0) + 2 ** 37 * (slot % 16384)
    return float(v)


# ---------------------------------------------------------------------------
# ブローカー（acc_pine.Broker + loss / comment / profit）
# ---------------------------------------------------------------------------
class Broker(ap.Broker):
    def __init__(self):
        super().__init__(pointvalue=1.0)

    def entry(self, id, direction, qty=None, comment=None):
        super().entry(id, direction, 1.0 if qty is None else qty)

    def exit(self, id, from_entry=None, stop=None, limit=None, loss=None, comment=None):
        self.exits[id] = dict(from_id=from_entry, stop=stop, limit=limit, loss=loss)
        self.log.append(("order_exit", self.bar, id, from_entry, stop, limit, loss))

    def close(self, id, comment=None):
        super().close(id)

    def _market(self, price):
        super()._market(price)
        # loss（tick）は約定価格から計算する（TradingView の strategy.exit loss と同じ考え方）
        for tr in self.open_trades:
            for o in self.exits.values():
                if o["from_id"] == tr["id"] and o.get("loss") is not None and o["stop"] is None:
                    o["stop"] = round(tr["price"] - tr["side"] * o["loss"] * MINTICK, 10)

    def ct_profit(self, i):
        c = self.closed[i]
        return (c["exit_price"] - c["price"]) * c["side"] * c["qty"] * self.pointvalue


# ---------------------------------------------------------------------------
# 実行器
# ---------------------------------------------------------------------------
SRC = open(PINE, encoding="utf-8").read()
LOGIC = SRC[SRC.index("\n", SRC.index(BEGIN)) + 1:SRC.index(END)]
CODE = compile(ap.Translator().translate(ap.logical_lines(LOGIC)), "<PM-NET5 logic>", "exec")
INPUTS = ap.inputs(SRC)


class Run:
    def __init__(self, **over):
        self.b = Broker()
        self.env = ap.make_env(self.b, [])
        self.env.update(INPUTS)
        self.env["netConnected"] = True
        for k, v in over.items():
            assert k in self.env, k
            self.env[k] = v
        self.env.update(
            _VARS=set(), _VARIPS=set(), __first__=True, isChart5M=True, syminfo__mintick=MINTICK,
            math__pow=lambda a, b: a ** b,
            strategy__closedtrades__profit=self.b.ct_profit,
        )
        self.i = -1
        self.rows = []

    def bar(self, o=2000.0, h=None, l=None, c=None, ins=None, conf=True, again=False):
        """ins : {入力名: 値}（未指定は na）。again = 同じ足をもう一度実行（リアルタイムの再計算を想定）"""
        if not again:
            self.i += 1
            self.b.bar = self.i
            c = o if c is None else c
            h = max(o, c) + 0.5 if h is None else h
            l = min(o, c) - 0.5 if l is None else l
            prev = None
            for p in ap.Broker.bar_path(o, h, l, c):
                self.b.point(p, prev)
                prev = p
            self.cur = (o, h, l, c)
        o, h, l, c = self.cur
        e = self.env
        t = T0 + self.i * M5
        e.update(time=t, time_close=t + M5, open=o, high=h, low=l, close=c, bar_index=self.i, barstate__isconfirmed=conf,
                 strategy__position_size=self.b.pos, strategy__opentrades=self.b.opentrades,
                 strategy__closedtrades=self.b.closedtrades)
        for nm in ("d05", "m05", "d09", "m09", "d16", "m16", "d15", "m15", "d24", "m24"):
            e[nm] = (ins or {}).get(nm)
        exec(CODE, e)
        e["__first__"] = False
        snap = {k: copy.deepcopy(e[k]) for k in ("nL", "nS", "nNet", "nMaL", "nMaS", "nWvL", "nWvS", "nSaL", "nSaS",
                                                 "nFamL", "nFamS", "nNewL", "nNewS", "EV_DIR", "EV_T", "satDir", "IN_ST",
                                                 "GONE", "nHoldSt", "nHoldWhy", "nLastChg", "nPosDir", "nAllOk", "nBoth",
                                                 "nSlPrice", "nFillPrice", "dSigDir", "dExitSig", "dFillDir", "dCloseDir",
                                                 "dCloseTxt", "nBlockSame", "TS", "nEntryPend", "nExitPend")}
        snap["i"] = self.i
        self.rows.append(snap)
        return snap

    def orders(self, kind):
        return [x for x in self.b.log if x[0] == kind]


def slot_of(i):
    return (T0 + i * M5 + M5 - BUS_BASE) // M5


class Feed:
    """バーごとの Source 出力を組み立てる。ev : {バー: {"05": "L" / "S" / "LS" / "negL" ...}}、sat : {バー: +1 / -1 / 0}（以後その状態）"""

    def __init__(self, ev=None, sat=None, sat0=0):
        self.ev, self.sat, self.satNow = ev or {}, sat or {}, sat0

    def ins(self, i, override=None):
        if i in self.sat:
            self.satNow = self.sat[i]
        s = slot_of(i)
        out = {}
        for key, (sid, lg, dn, mn) in LOGICS.items():
            tags = self.ev.get(i, {}).get(key, "")
            if key == "24":
                d = data(s, rawL=self.satNow == 1, rawS=self.satNow == -1, curL=self.satNow == 1, curS=self.satNow == -1, junk=i)
            else:
                d = data(s, rawL="L" in tags.replace("negL", ""), rawS="S" in tags.replace("negS", ""),
                         negL="negL" in tags, negS="negS" in tags, junk=i)
            out[dn], out[mn] = d, meta(sid, lg, s)
        out.update(override or {})
        return out


def play(feed, n, prices=None, **over):
    """prices : {バー: (o, h, l, c)}（未指定は 2000 の小さな足）"""
    r = Run(**over)
    for i in range(n):
        o, h, l, c = (prices or {}).get(i, (2000.0, None, None, None))
        r.bar(o, h, l, c, ins=feed.ins(i))
    return r


def mirror_feed(ev, sat):
    sw = {"L": "S", "S": "L"}
    ev2 = {}
    for b, d in ev.items():
        ev2[b] = {}
        for k, v in d.items():
            v2 = v.replace("negL", "#1").replace("negS", "#2")
            v2 = "".join(sw.get(ch, ch) for ch in v2).replace("#1", "negS").replace("#2", "negL")
            ev2[b][k] = v2
    return ev2, {b: -x for b, x in sat.items()}


def mirror_prices(pr):
    return {b: (4000 - o, None if l is None else 4000 - l, None if h is None else 4000 - h, None if c is None else 4000 - c)
            for b, (o, h, l, c) in pr.items()}


# ===========================================================================
# 1. 系統別上限
# ===========================================================================
r = play(Feed({3: {"05": "L", "09": "L"}}), 4)
check("⑤買い＋⑨買い = LONG 2（MA 系上限 2）", r.rows[3]["nL"] == 2 and r.rows[3]["nMaL"] == 2 and r.rows[3]["nFamL"] == 1)
r = play(Feed({3: {"05": "L", "16": "L"}}), 4)
check("⑤買い＋⑯買い = LONG 4", r.rows[3]["nL"] == 4 and r.rows[3]["nFamL"] == 2)
r = play(Feed({3: {"05": "L", "16": "L"}}, sat={0: 1}), 4)
check("⑤買い＋⑯買い＋SAT買い = LONG 5", r.rows[3]["nL"] == 5 and r.rows[3]["nNet"] == 5)
r = play(Feed({3: {"16": "L", "15": "L"}}), 4)
check("⑯買い＋⑮買い = 波形系 2（上限 2）", r.rows[3]["nWvL"] == 2 and r.rows[3]["nL"] == 2)
r = play(Feed({3: {"15": "S"}}), 4)
check("⑮売りだけ = SHORT 1", r.rows[3]["nS"] == 1 and r.rows[3]["nWvS"] == 1)
r = play(Feed({3: {"05": "L", "16": "S"}}), 4)
check("異なるロジックの逆方向根拠は両方残る（⑤買い＋⑯売り = 2 / 2 / NET 0）",
      r.rows[3]["nL"] == 2 and r.rows[3]["nS"] == 2 and r.rows[3]["nNet"] == 0)
r = play(Feed({3: {"05": "L", "09": "L", "16": "L", "15": "L"}}, sat={0: 1}), 4)
check("全部買い = LONG 5（最大 5）", r.rows[3]["nL"] == 5)

# ===========================================================================
# 2. 保持（同方向再成立・逆方向・期限・価格否定・同時両方向）
# ===========================================================================
r = play(Feed({3: {"05": "L"}, 5: {"05": "L"}}), 10)
check("同方向再成立で点数が積み上がらない（⑤買い 2 回 = 2）", r.rows[5]["nL"] == 2)
check("同方向再成立で期限を更新（2 回目から 15 分 = 3 本有効、4 本目で期限切れ）",
      [x["nL"] for x in r.rows[5:10]] == [2, 2, 2, 0, 0] and r.rows[8]["GONE"][0] == 1)
r = play(Feed({3: {"05": "L"}}), 8)
check("保持 15 分 : 成立足 + 2 本まで有効、成立時刻 + 15 分の確定足で期限切れ",
      [x["nL"] for x in r.rows[3:8]] == [2, 2, 2, 0, 0])
r = play(Feed({3: {"05": "L"}}), 9, holdMin=25)
check("保持時間は設定で変更可能（25 分 = 5 本）", [x["nL"] for x in r.rows[3:9]] == [2, 2, 2, 2, 2, 0])
r = play(Feed({3: {"05": "L"}, 4: {"05": "S"}}), 6)
check("逆方向成立で同一ロジックの旧方向が消える（⑤買い→⑤売り）",
      r.rows[4]["EV_DIR"][0] == -1 and r.rows[4]["nL"] == 0 and r.rows[4]["nS"] == 2 and r.rows[4]["GONE"][0] == 3)
r = play(Feed({3: {"16": "L"}, 4: {"16": "negL"}}), 6)
check("Source の価格否定（解除通知）でその足に解除", r.rows[4]["EV_DIR"][2] == 0 and r.rows[4]["GONE"][2] == 2 and r.rows[4]["nL"] == 0)
r = play(Feed({3: {"16": "L"}, 4: {"16": "negS"}}), 6)
check("逆方向の価格否定は保持中の方向を消さない", r.rows[4]["EV_DIR"][2] == 1)
r = play(Feed({3: {"05": "L"}, 4: {"05": "LS"}}), 6)
check("同じ足の両方向は変更しない（件数だけ数える）", r.rows[4]["EV_DIR"][0] == 1 and r.rows[4]["nBoth"] == 1)

# ===========================================================================
# 3. SAT（状態型）
# ===========================================================================
r = play(Feed(sat={0: 1}), 6)
check("最初の受信で既にある SAT 状態は新規イベントにしない（点数は 1）",
      not any(x["nNewL"] for x in r.rows) and r.rows[5]["nSaL"] == 1)
r = play(Feed(sat={3: 1, 15: -1, 20: 0}), 23)
newL = [x["i"] for x in r.rows if x["nNewL"]]
newS = [x["i"] for x in r.rows if x["nNewS"]]
check("SAT 継続中に新規イベントを連発しない（無し→買い は 1 回だけ）", newL == [3])
check("SAT の方向転換は新しいイベント（買い→売り 1 回）", newS == [15] and r.rows[15]["GONE"][4] == 5)
check("SAT 解除に追従（0 点・解除理由 4・新規イベントなし）", r.rows[20]["nSaS"] == 0 and r.rows[20]["GONE"][4] == 4 and not r.rows[20]["nNewL"])
check("SAT は有効な間だけ 1 点", [x["nSaL"] for x in r.rows[2:5]] == [0, 1, 1] and r.rows[14]["nSaL"] == 1 and r.rows[15]["nSaL"] == 0)
r = Run()
f = Feed(sat={0: 1})
for i in range(8):
    ins = f.ins(i)
    if i == 4:
        ins["m24"] = None                     # Source 出力なし
    r.bar(ins=ins)
check("SAT のデータ不備から復帰した足は基準だけ（既にある状態を新規扱いしない）",
      r.rows[4]["IN_ST"][4] == 2 and not r.rows[5]["nNewL"] and r.rows[5]["nSaL"] == 1)

# ===========================================================================
# 4. 受信の検証（データ不備を 0 点と区別）
# ===========================================================================
r = play(Feed({3: {"05": "L", "16": "L"}}, sat={0: 1}), 6, netConnected=False)
check("未接続 : 全入力 1（未接続）・判定停止・注文なし", r.rows[3]["IN_ST"] == [1] * 5 and not r.rows[3]["nAllOk"] and not r.b.log)
cases = {
    "旧形式（META format 1）→ 3": (dict(m05=meta(1, 5, slot_of(3), fmt=1)), 3),
    "Logic 取り違え（Logic06）→ 4": (dict(m05=meta(1, 6, slot_of(3))), 4),
    "Source 取り違え（B）→ 4": (dict(m05=meta(2, 5, slot_of(3))), 4),
    "15M の診断 → 4": (dict(m05=meta(1, 5, slot_of(3), tf=2)), 4),
    "前の足の値（時刻不一致）→ 5": (dict(m05=meta(1, 5, slot_of(2))), 5),
    "Source 準備中 → 6": (dict(m05=meta(1, 5, slot_of(3), st=1), d05=None), 6),
    "Source 不整合 → 7": (dict(m05=meta(1, 5, slot_of(3), st=4), d05=None), 7),
    "DATA の slot 不一致 → 9": (dict(d05=data(slot_of(2), rawL=True)), 9),
    "META na → 2": (dict(m05=None), 2),
    "SAT の採用 OFF → 8": (dict(m24=meta(3, 24, slot_of(3), adopt=0)), 8),
}
for nm, (ov, want) in cases.items():
    r = Run()
    f = Feed({3: {"05": "L", "16": "L"}}, sat={0: 1})
    for i in range(4):
        r.bar(ins=f.ins(i, ov if i == 3 else None))
    k = 4 if "SAT" in nm else 0
    check("受信状態 " + nm, r.rows[3]["IN_ST"][k] == want and not r.rows[3]["nAllOk"] and not r.orders("order_entry"))
r = Run()
f = Feed({3: {"05": "L"}})
for i in range(4):
    r.bar(ins=f.ins(i, dict(m05=meta(1, 5, slot_of(3), adopt=0)) if i == 3 else None))
check("イベント型は採用 OFF でも生シグナルを読む（採用は B の系統点の設定）", r.rows[3]["IN_ST"][0] == 0 and r.rows[3]["nL"] == 2)

# ===========================================================================
# 5. エントリー・次足約定・SL
# ===========================================================================
PR = {i: (2000.0, None, None, None) for i in range(40)}
PR[4] = (2000.0, 2001.0, 1999.0, 2000.5)
PR[5] = (2002.0, 2003.0, 2001.0, 2002.5)        # 約定足（始値 2002）
PR[9] = (2001.0, 2001.5, 1986.0, 1990.0)        # SL 1987 に到達
ev = {4: {"05": "L", "16": "L"}, 9: {"05": "S", "16": "S", "09": "S"}}
r = play(Feed(ev, sat={0: 1}), 12, PR)
ent = r.orders("order_entry")
check("LONG 合図は判定足（4）で 1 回、約定は次足（5）始値", len(ent) == 1 and ent[0][1] == 4 and r.rows[4]["dSigDir"] == 1
      and [x for x in r.b.log if x[0] == "fill_entry"][0][1:] == (5, "L", 1, 1.0, 2002.0))
check("SL は実際の約定価格 − 15 = 1987（合図価格 2000.5 ではない）", r.rows[5]["nSlPrice"] == 1987.0 and r.rows[5]["nFillPrice"] == 2002.0
      and [x for x in r.b.log if x[0] == "order_exit"][0][6] == 1500)
fx = [x for x in r.b.log if x[0] == "fill_exit"]
check("SL は足の途中で約定（9 で 1987）", len(fx) == 1 and fx[0][1] == 9 and fx[0][3] == "L-SL" and fx[0][4] == 1987.0)
check("SL 約定後に NET 決済を重複して出さない", not r.orders("order_close") and r.rows[9]["dExitSig"] == 0)
check("SL で決済した足では、売り条件が揃っても新規エントリーしない", len(r.orders("order_entry")) == 1 and r.rows[9]["nBlockSame"] == 1)
check("SL 決済は損失決済として記録（LONG 1 件・負け 1・−15・SL 1）",
      r.rows[9]["TS"][0:8] == [1, 0, 1, 0, -15.0, -15.0, 1, 0] and "損失決済" in r.rows[9]["dCloseTxt"])
check("同時保有 1（最大ポジション 1）", r.b.max_abs_pos == 1.0)
r = play(Feed(ev, sat={0: 1}), 12, PR, slUsd=7.5)
check("SL 幅は設定で変更可能（7.5 → 1994.5）", r.rows[5]["nSlPrice"] == 1994.5)
# 約定足で SL
PR2 = dict(PR)
PR2[5] = (2002.0, 2002.5, 1980.0, 1985.0)
r = play(Feed({4: {"05": "L", "16": "L"}}, sat={0: 1}), 8, PR2)
check("約定足の中で SL に到達しても 1 回だけ約定・記録", len([x for x in r.b.log if x[0] == "fill_exit"]) == 1
      and r.rows[5]["dFillDir"] == 1 and r.rows[5]["dCloseDir"] == 1 and r.rows[5]["nPosDir"] == 0 and r.rows[5]["TS"][0] == 1)

# 2 系統の要件
r = play(Feed({4: {"05": "L", "09": "L"}}, sat={0: 0}), 6)
check("⑤＋⑨ だけ（1 系統・LONG 2）ではエントリーしない", not r.orders("order_entry") and r.rows[4]["nFamL"] == 1)
r = play(Feed({4: {"05": "L", "09": "L"}}, sat={0: 1}), 6)
check("⑤＋⑨＋SAT（2 系統・NET 3）はエントリー", len(r.orders("order_entry")) == 1)
r = play(Feed({3: {"16": "S"}, 4: {"05": "L", "15": "L"}}, sat={0: 1}), 6)
check("SHORT 2 があると NET ≥ 3 でも SHORT ≤ 1 を満たさず入らない（LONG 4 / SHORT 2）",
      r.rows[4]["nL"] == 4 and r.rows[4]["nS"] == 2 and not r.orders("order_entry"))
# 期限切れだけでは入らない
r = play(Feed({1: {"09": "S"}, 4: {"05": "L", "15": "L"}, 9: {"15": "L"}}, sat={0: 1}), 11, holdMin=30)
check("逆方向の期限切れで条件が揃っただけでは入らない（7・8 は NET 4・新規イベントなし）",
      r.rows[7]["nNet"] == 4 and r.rows[7]["nS"] == 0 and r.rows[7]["GONE"][1] == 1 and
      not any(x[1] in (4, 5, 6, 7, 8) for x in r.orders("order_entry")))
check("その後の新しい買いイベント（9 の ⑮ 再成立）でエントリー", [x[1] for x in r.orders("order_entry")] == [9])

# ===========================================================================
# 6. 保有中の判断・NET 決済・再エントリー
# ===========================================================================
PR3 = {i: (2000.0 + i, None, None, None) for i in range(40)}
ev3 = {4: {"05": "L", "16": "L"}}
r = play(Feed(ev3, sat={0: 1}), 12, PR3)
check("約定後 保有支持あり（LONG 5 / NET 5）", r.rows[5]["nHoldSt"] == 1)
check("期限切れだけでは決済しない（7 で ⑤⑯ 期限切れ → LONG 1）", r.rows[7]["nL"] == 1 and not r.orders("order_close") and r.rows[11]["nPosDir"] == 1)
check("期限切れで 支持低下・理由「保有方向の根拠の期限切れ」", r.rows[7]["nHoldSt"] == 2 and "保有方向の根拠の期限切れ（⑤）" in r.rows[7]["nHoldWhy"]
      and "（⑯）" in r.rows[7]["nHoldWhy"])

ev4 = {4: {"05": "L", "16": "L"}, 6: {"15": "S", "09": "S"}, 8: {"05": "S", "16": "S"}, 9: {}, 10: {"09": "S"}}
r = play(Feed(ev4, sat={0: 1}), 14, PR3)
check("新しい売りイベントで SHORT ≥ 2 → 反転警戒（NET 2 > 0 なので決済しない）",
      r.rows[6]["nHoldSt"] == 3 and r.rows[6]["nS"] == 3 and r.rows[6]["nNet"] == 2 and not any(x[1] < 8 for x in r.orders("order_close")))
check("反転警戒の理由「新しい逆方向根拠の成立」", "新しい逆方向根拠の成立（⑨）" in r.rows[6]["nHoldWhy"] and "（⑮）" in r.rows[6]["nHoldWhy"])
check("反転警戒は SHORT ≥ 2 の間継続（7 は保有方向の期限切れも重なるが反転警戒のまま）", r.rows[7]["nHoldSt"] == 3 and r.rows[7]["nNet"] == -2)
check("NET ≤ 0 でも新しい売りイベントがない足（7）では決済しない", not any(x[1] == 7 for x in r.orders("order_close")))
cl = r.orders("order_close")
check("新しい売り＋SHORT ≥ 2＋NET ≤ 0 で NET 決済注文（判定足 8）", len(cl) == 1 and cl[0][1] == 8 and r.rows[8]["dExitSig"] == 1)
check("決済と同じ判定足で逆エントリーしない（8 の SHORT 条件は成立しているが注文なし）",
      r.rows[8]["nNet"] <= -3 and [x[1] for x in r.orders("order_entry")] == [4, 10])
fx = [x for x in r.b.log if x[0] == "fill_exit"]
check("NET 決済は次足（9）始値で約定", fx[0][1] == 9 and fx[0][3] == "close" and fx[0][4] == 2009.0)
check("NET 決済の利益は利確として記録（2005 → 2009 = +4）", r.rows[9]["TS"][0:8] == [1, 1, 0, 4.0, 0, 4.0, 0, 1]
      and "利確" in r.rows[9]["dCloseTxt"] and "NET決済" in r.rows[9]["dCloseTxt"])
check("決済後、以前の条件が残っているだけでは再エントリーしない（9 は新規イベントなし）", r.rows[9]["nNet"] <= -3 and not any(x[1] == 9 for x in r.orders("order_entry")))
check("決済後に新しく成立した売り（10 の ⑨）で SHORT エントリー", r.orders("order_entry")[1][1:4] == (10, "S", -1))
check("エントリー注文中・決済注文中の重複注文なし（エントリー 2・決済 1・最大ポジション 1）",
      len(r.orders("order_entry")) == 2 and len(r.orders("order_close")) == 1 and r.b.max_abs_pos == 1.0)

# 同じ足の再実行（リアルタイムの再計算）で二重処理しない
r = Run()
f = Feed({4: {"05": "L", "16": "L"}}, sat={0: 1})
for i in range(6):
    ins = f.ins(i)
    r.bar(ins=ins)
    if i == 4:
        r.bar(ins=ins, again=True)
check("同じ確定足を 2 回実行しても元シグナルを重複処理しない（注文 1 回）", len(r.orders("order_entry")) == 1 and r.rows[5]["EV_T"][0] == r.rows[4]["EV_T"][0])
r = Run()
for i in range(6):
    r.bar(ins=f.ins(i), conf=(i != 4))
check("未確定の足では判定しない", not any(x[1] == 4 for x in r.orders("order_entry")))

# ===========================================================================
# 7. LONG / SHORT の対称性
# ===========================================================================
for nm, ev_, sat_, pr_, n in (("エントリー・SL", ev, {0: 1}, PR, 12), ("NET 決済・再エントリー", ev4, {0: 1}, PR3, 14),
                               ("期限切れ", ev3, {0: 1}, PR3, 12)):
    a = play(Feed(ev_, sat=sat_), n, pr_)
    ev2, sat2 = mirror_feed(ev_, sat_)
    b = play(Feed(ev2, sat=sat2), n, mirror_prices(pr_))
    same = True
    for x, y in zip(a.rows, b.rows):
        same &= (x["nL"], x["nS"], x["nNet"], x["nHoldSt"], x["nPosDir"], x["dSigDir"], x["dExitSig"]) == \
                (y["nS"], y["nL"], -y["nNet"], y["nHoldSt"], -y["nPosDir"], -y["dSigDir"], -y["dExitSig"])
        same &= x["TS"][0:8] == y["TS"][8:16] and x["TS"][8:16] == y["TS"][0:8]
    sw = {"L": "S", "S": "L", "L-SL": "S-SL", "S-SL": "L-SL", "close": "close"}
    def norm(e):
        k = e[0]
        if k == "order_entry":
            return (k, e[1], sw[e[2]], -e[3], e[4])
        if k == "order_exit":
            return (k, e[1], sw[e[2]], sw[e[3]]) + e[4:]
        if k == "fill_entry":
            return (k, e[1], sw[e[2]], -e[3], e[4], round(4000 - e[5], 6))
        if k == "fill_exit":
            return (k, e[1], sw[e[2]], sw[e[3]], round(4000 - e[4], 6))
        if k == "order_close":
            return (k, e[1], sw[e[2]])
        return e
    ob = [tuple(round(v, 6) if isinstance(v, float) else v for v in e) for e in b.b.log]
    oa = [norm(e) for e in a.b.log]
    same &= oa == ob and len(oa) > 0
    check("LONG / SHORT 対称（" + nm + "：左右反転した入力で点数・判断・注文・成績が反転）", same)

print(f"\n{ok} checks passed")

"""PM-NET5（PointMasterNet5Strategy.pine）の固定ケース。

Pine ファイルの「NET5 Logic」区間そのものを tests/acc_pine.py の変換器（Pine サブセット → Python）で実行する（手書きの移植ではない）。
入力は Source（PM-A/B/C-515）の STUDY DATA / META BUS を、Source の f_study() と同じ式で合成したもの。
約定は acc_pine.Broker（TradingView 風の仮定。成行 = 次の価格点 / 履歴足の経路 O→H→L→C か O→L→H→C）に
strategy.exit の loss（tick）を足したもの。TradingView のコンパイラ・ブローカーエミュレーターそのものではない。

§1〜7 は NET5-1 の仕様（建値 OFF で実行）。§8 は tests/net5_v1_reference.pine（NET5-1 の凍結コピー）と
現行版（建値 OFF・他は初期値）をランダム入力で走らせ、全足の状態・全注文・成績が一致することを確かめる。
§9〜12 は NET5-2 の入力・建値移動・対称性。

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
# NET5-1（建値移動・入力化の前）の凍結コピー。「建値 OFF + 初期値 = 従来版と同じ」の照合に使う
SRC_V1 = open(os.path.join(ROOT, "tests", "net5_v1_reference.pine"), encoding="utf-8").read()
CODE_V1 = compile(ap.Translator().translate(ap.logical_lines(SRC_V1[SRC_V1.index("\n", SRC_V1.index(BEGIN)) + 1:SRC_V1.index(END)])),
                  "<PM-NET5 v1 logic>", "exec")
INPUTS_V1 = ap.inputs(SRC_V1)
BASE = {}          # 各 Run の既定上書き（§1〜7 は NET5-1 の仕様確認なので beUse=False）


class Run:
    def __init__(self, code=None, inputs=None, **over):
        self.code = CODE if code is None else code
        self.b = Broker()
        self.env = ap.make_env(self.b, [])
        self.env.update(INPUTS if inputs is None else inputs)
        self.env["netConnected"] = True
        over = dict(BASE if code is None else {}, **over)
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
        exec(self.code, e)
        e["__first__"] = False
        snap = {k: copy.deepcopy(e[k]) for k in ("nL", "nS", "nNet", "nMaL", "nMaS", "nWvL", "nWvS", "nSaL", "nSaS",
                                                 "nFamL", "nFamS", "nNewL", "nNewS", "EV_DIR", "EV_T", "satDir", "IN_ST",
                                                 "GONE", "nHoldSt", "nHoldWhy", "nLastChg", "nPosDir", "nAllOk", "nBoth",
                                                 "nSlPrice", "nFillPrice", "dSigDir", "dExitSig", "dFillDir", "dCloseDir",
                                                 "dCloseTxt", "nBlockSame", "TS", "nEntryPend", "nExitPend")}
        for k in ("nBeDone", "nBeTrigLine", "nBeClose", "dBeDir", "dBeStop", "nEntNg", "nExNg", "nMaxScore", "nBothEnt"):
            snap[k] = copy.deepcopy(e.get(k))
        snap["i"] = self.i
        snap["exits"] = {k: (v["stop"], v.get("loss")) for k, v in self.b.exits.items()}     # この足の実行後に有効な保護注文
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


BASE = dict(beUse=False)

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
r = play(Feed({3: {"05": "L"}}), 9, hold05=25)
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
      r.rows[9]["TS"][0:9] == [1, 0, 1, 0, -15.0, -15.0, 1, 0, 0] and "損失決済" in r.rows[9]["dCloseTxt"])
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
r = play(Feed({1: {"09": "S"}, 4: {"05": "L", "15": "L"}, 9: {"15": "L"}}, sat={0: 1}), 11, hold05=30, hold09=30, hold15=30)
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
check("NET 決済の利益は利確として記録（2005 → 2009 = +4）", r.rows[9]["TS"][0:9] == [1, 1, 0, 4.0, 0, 4.0, 0, 0, 1]
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
SW = {"L": "S", "S": "L", "L-SL": "S-SL", "S-SL": "L-SL", "close": "close"}


def mir(v):
    return None if v is None else round(4000 - v, 6)


def norm(e):
    k = e[0]
    if k == "order_entry":
        return (k, e[1], SW[e[2]], -e[3], e[4])
    if k == "order_exit":
        return (k, e[1], SW[e[2]], SW[e[3]], mir(e[4]), mir(e[5]), e[6])
    if k == "fill_entry":
        return (k, e[1], SW[e[2]], -e[3], e[4], mir(e[5]))
    if k == "fill_exit":
        return (k, e[1], SW[e[2]], SW[e[3]], mir(e[4]))
    if k == "order_close":
        return (k, e[1], SW[e[2]])
    return e


def symmetric(ev_, sat_, pr_, n, **over):
    a = play(Feed(ev_, sat=sat_), n, pr_, **over)
    ev2, sat2 = mirror_feed(ev_, sat_)
    b = play(Feed(ev2, sat=sat2), n, mirror_prices(pr_), **over)
    same = True
    for x, y in zip(a.rows, b.rows):
        same &= (x["nL"], x["nS"], x["nNet"], x["nHoldSt"], x["nPosDir"], x["dSigDir"], x["dExitSig"]) == \
                (y["nS"], y["nL"], -y["nNet"], y["nHoldSt"], -y["nPosDir"], -y["dSigDir"], -y["dExitSig"])
        same &= x["TS"][0:9] == y["TS"][9:18] and x["TS"][9:18] == y["TS"][0:9]
        same &= x["nBeDone"] == y["nBeDone"] and (x["nSlPrice"] is None) == (y["nSlPrice"] is None)
        same &= x["nSlPrice"] is None or round(4000 - x["nSlPrice"], 6) == round(y["nSlPrice"], 6)
    ob = [tuple(round(v, 6) if isinstance(v, float) else v for v in e) for e in b.b.log]
    oa = [norm(e) for e in a.b.log]
    return same and oa == ob and len(oa) > 0, a


for nm, ev_, sat_, pr_, n in (("エントリー・SL", ev, {0: 1}, PR, 12), ("NET 決済・再エントリー", ev4, {0: 1}, PR3, 14),
                               ("期限切れ", ev3, {0: 1}, PR3, 12)):
    check("LONG / SHORT 対称（" + nm + "：左右反転した入力で点数・判断・注文・成績が反転）", symmetric(ev_, sat_, pr_, n)[0])

# ### NET5-2 ###
BASE = {}
import random

# ===========================================================================
# 8. 建値 OFF + 全入力初期値 = NET5-1 と同じ売買判定（凍結コピーとランダム入力で照合）
# ===========================================================================
def rand_case(seed, n=160):
    rnd = random.Random(seed)
    ev, sat, faults = {}, {}, {}
    for i in range(n):
        d = {}
        for k in ("05", "09", "16", "15"):
            x = rnd.random()
            if x < 0.07:
                d[k] = "L"
            elif x < 0.14:
                d[k] = "S"
            elif x < 0.15:
                d[k] = "LS"
            elif x < 0.17:
                d[k] = rnd.choice(["negL", "negS"])
        if d:
            ev[i] = d
        if rnd.random() < 0.06:
            sat[i] = rnd.choice([1, -1, 0])
        if rnd.random() < 0.02:
            faults[i] = rnd.choice(["m05", "m16", "m24", "m15"])
    pr, p = {}, 2000.0
    for i in range(n):
        o = round(p + rnd.uniform(-2, 2), 2)
        c = round(o + rnd.uniform(-9, 9), 2)
        h = round(max(o, c) + rnd.uniform(0, 6), 2)
        l = round(min(o, c) - rnd.uniform(0, 6), 2)
        pr[i], p = (o, h, l, c), c
    return ev, sat, faults, pr


def play_case(case, code=None, inputs=None, **over):
    ev_, sat_, faults, pr = case
    r = Run(code=code, inputs=inputs, **over)
    f = Feed(ev_, sat=sat_)
    for i in range(len(pr)):
        ins = f.ins(i)
        if i in faults:
            ins[faults[i]] = None
        r.bar(*pr[i], ins=ins)
    return r


KEYS = ("nL", "nS", "nNet", "nMaL", "nMaS", "nWvL", "nWvS", "nSaL", "nSaS", "nFamL", "nFamS", "nNewL", "nNewS", "EV_DIR",
        "satDir", "GONE", "nHoldSt", "nHoldWhy", "nLastChg", "nPosDir", "nAllOk", "nSlPrice", "nFillPrice", "dSigDir",
        "dExitSig", "dFillDir", "dCloseDir", "nBlockSame")
mism, trades, nexit, nsl = 0, 0, 0, 0
for seed in range(60):
    case = rand_case(seed)
    a = play_case(case, code=CODE_V1, inputs=INPUTS_V1)
    b = play_case(case, beUse=False)
    for x, y in zip(a.rows, b.rows):
        if any(x[k] != y[k] for k in KEYS):
            mism += 1
        tx, ty = x["TS"], y["TS"]
        for d in (0, 1):
            if tx[d * 8:d * 8 + 6] != ty[d * 9:d * 9 + 6] or tx[d * 8 + 6] != ty[d * 9 + 6] + ty[d * 9 + 7] or tx[d * 8 + 7] != ty[d * 9 + 8]:
                mism += 1
    if a.b.log != b.b.log:
        mism += 1
    trades += len(a.b.closed)
    nexit += len(a.orders("order_close"))
    nsl += sum(1 for c in a.b.closed if c["exit_id"].endswith("SL"))
check(f"建値 OFF・他は初期値 : NET5-1 と全足・全注文が一致（ランダム 60 ケース × 160 本、決済 {trades} 件 = NET {nexit} / SL {nsl}）",
      mism == 0 and trades > 50 and nexit > 5 and nsl > 5)
nbe = sum(1 for seed in range(60) for r_ in play_case(rand_case(seed)).rows if r_["dBeDir"] != 0)
check(f"建値 ON（初期値）の同じランダム入力では建値移動が起きる（{nbe} 回。照合ケースが建値の場面を含む）", nbe > 0)

# ===========================================================================
# 9. 配点・上限・使用 ON/OFF・保持時間の入力
# ===========================================================================
r = play(Feed({3: {"05": "L"}}), 4, pt05=3)
check("⑤ 配点 3 でも MA 上限 2 で 2", r.rows[3]["nL"] == 2)
r = play(Feed({3: {"05": "L"}}), 4, pt05=3, capMa=3)
check("⑤ 配点 3・MA 上限 3 → 3、最大スコア表示 = 3+2+1 = 6", r.rows[3]["nL"] == 3 and r.rows[3]["nMaxScore"] == 6)
r = play(Feed({3: {"05": "L", "09": "L"}}), 4, capMa=4)
check("MA 上限 4 なら ⑤＋⑨ = 4（最大 7）", r.rows[3]["nMaL"] == 4 and r.rows[3]["nMaxScore"] == 7)
r = play(Feed({3: {"16": "S", "15": "S"}}), 4, capWv=3)
check("波形系 上限 3 なら ⑯＋⑮ = 3（SHORT も同じ配点・上限）", r.rows[3]["nS"] == 3)
r = play(Feed(sat={0: -1}), 3, pt24=2, capSa=2)
check("SAT 配点 2・上限 2 → 2", r.rows[2]["nSaS"] == 2)
r = Run(use05=False)
f = Feed({3: {"05": "L", "16": "L"}}, sat={0: 1})
for i in range(5):
    ins = f.ins(i)
    ins["m05"] = ins["d05"] = None             # 使用 OFF の入力は未接続でよい
    r.bar(ins=ins)
check("⑤ 使用 OFF : 入力未接続でも判定（状態 11）・⑤ の点なし（LONG 3）", r.rows[3]["IN_ST"][0] == 11 and r.rows[3]["nAllOk"]
      and r.rows[3]["EV_DIR"][0] == 0 and r.rows[3]["nL"] == 3 and r.rows[3]["nMaxScore"] == 5)
r = play(Feed(), 2, use05=False, use09=False)
check("⑤⑨ とも使用 OFF : MA 系の最大 0・各方向の最大 3", r.rows[1]["nMaxScore"] == 3)
r = play(Feed({3: {"05": "L"}}, sat={0: 1}), 5, use05=False)
check("⑤ 使用 OFF : ⑤ の成立は新しいシグナルにならない", not r.rows[3]["nNewL"] and not r.orders("order_entry"))
r = play(Feed({3: {"05": "L", "16": "L"}}, sat={0: 1}), 5, use24=False)
check("SAT 使用 OFF : SAT の点・系統を数えない（LONG 4・系統 2）", r.rows[3]["nL"] == 4 and r.rows[3]["nSaL"] == 0 and r.rows[3]["IN_ST"][4] == 11)
r = play(Feed(sat={0: 0, 3: 1}), 5, use24=False)
check("SAT 使用 OFF : SAT の有効化は新しいシグナルにならない", not any(x["nNewL"] for x in r.rows))
r = play(Feed({3: {"05": "L", "09": "L"}}, sat={0: 1}), 6, use24=False)
check("SAT OFF で ⑤＋⑨ だけ → 系統 1・エントリーなし", r.rows[3]["nFamL"] == 1 and not r.orders("order_entry"))
r = play(Feed({3: {"05": "L", "16": "L", "09": "L", "15": "L"}}), 9, hold16=25, hold09=5, hold15=10)
check("保持時間はロジックごと（⑤ 15 / ⑨ 5 / ⑮ 10 / ⑯ 25 分）",
      [x["EV_DIR"] for x in r.rows[3:9]] == [[1, 1, 1, 1], [1, 0, 1, 1], [1, 0, 1, 0], [0, 0, 1, 0], [0, 0, 1, 0], [0, 0, 0, 0]])
r = play(Feed(sat={0: 1}), 12, hold05=5, hold09=5, hold16=5, hold15=5)
check("SAT には保持時間を適用しない（状態が続く間 11 本とも 1 点）", all(x["nSaL"] == 1 for x in r.rows))

# ===========================================================================
# 10. エントリー条件の入力
# ===========================================================================
F3 = lambda: Feed({4: {"05": "L", "09": "L"}}, sat={0: 1})          # LONG 3 / 2 系統
r = play(F3(), 6, entNet=4)
check("NET 最低値 4 : NET 3 では入らない", not r.orders("order_entry"))
r = play(F3(), 6)
check("初期値（NET 3）: 入る", len(r.orders("order_entry")) == 1)
r = play(Feed({3: {"15": "S"}, 4: {"05": "L", "16": "L"}}, sat={0: 1}), 6)
check("反対方向 1 は上限 1 で可（LONG 5 / SHORT 1）", len(r.orders("order_entry")) == 1)
r = play(Feed({3: {"15": "S"}, 4: {"05": "L", "16": "L"}}, sat={0: 1}), 6, entOpp=0)
check("反対方向の上限 0 : SHORT 1 で入らない", not r.orders("order_entry"))
r = play(Feed({4: {"05": "L", "16": "L"}}, sat={0: 0}), 6, entFam=3)
check("必要系統 3 : 2 系統（LONG 4）では入らない", not r.orders("order_entry"))
r = play(Feed({4: {"05": "L", "16": "L"}}, sat={0: 1}), 6, entFam=3)
check("必要系統 3 : 3 系統で入る", len(r.orders("order_entry")) == 1)
r = play(Feed({2: {"05": "L", "16": "L"}}, sat={0: 1}), 6, entNeedNew=False, use05=True)
check("新シグナル必須 OFF でも、条件が揃った足（2）で入る", [x[1] for x in r.orders("order_entry")][:1] == [2])
r = play(Feed(sat={0: 1, 3: 1}), 6, entNeedNew=False, entNet=1, entFam=1)
check("新シグナル必須 OFF : 新しいイベントのない足（0 の SAT 基準足）でも入る", [x[1] for x in r.orders("order_entry")][:1] == [0])
r = play(Feed({4: {"05": "L", "16": "L"}}, sat={0: 1}), 6, entNet=6)
check("満たせない設定（NET 最低値 6 > 最大 5）: 補正せず表示・エントリーなし",
      "最大スコア 5 < NET 最低値 6" in r.rows[-1]["nEntNg"] and not r.orders("order_entry"))
r = play(F3(), 6, entFam=3, use24=False)
check("満たせない設定（点を持てる系統 2 < 必要 3）を表示", "必要系統数 3" in r.rows[-1]["nEntNg"])
r = play(F3(), 6, capMa=0, capWv=0, capSa=0)
check("上限がすべて 0 : 最大 0 で満たせない表示", r.rows[-1]["nMaxScore"] == 0 and r.rows[-1]["nEntNg"] != "")
r = play(F3(), 6)
check("初期値では満たせない表示なし", r.rows[-1]["nEntNg"] == "" and r.rows[-1]["nExNg"] == "")
r = play(F3(), 6, exOpp=6)
check("NET 決済の反対方向 6 > 最大 5 を表示", "反対方向の最低値 6" in r.rows[-1]["nExNg"])

# ===========================================================================
# 11. 保有判断（表示用）と NET 決済条件の入力
# ===========================================================================
PR3 = {i: (2000.0 + i * 0.1, None, None, None) for i in range(40)}
ev5 = {4: {"05": "L", "16": "L"}, 6: {"15": "S"}, 8: {"09": "S"}}
r = play(Feed(ev5, sat={0: 1}), 12, PR3, beUse=False)
check("初期値 : 6 の ⑮売り（SHORT 1）は警戒なし・支持あり", r.rows[6]["nHoldSt"] == 1)
r = play(Feed(ev5, sat={0: 1}), 12, PR3, beUse=False, hdWarn=1)
check("反転警戒の反対方向 1 : 6 で反転警戒（決済条件は変わらない）", r.rows[6]["nHoldSt"] == 3 and not any(x[1] == 6 for x in r.orders("order_close")))
r = play(Feed(ev5, sat={0: 1}), 12, PR3, beUse=False, hdOwn=6)
check("保有支持の最低値 6 : 支持低下（表示だけ。決済なし）", r.rows[5]["nHoldSt"] == 2 and not any(x[1] < 8 for x in r.orders("order_close")))
r = play(Feed(ev5, sat={0: 1}), 12, PR3, beUse=False, hdNet=5)
check("保有 NET 最低値 5 : NET 4 の 6 で支持低下", r.rows[5]["nHoldSt"] == 1 and r.rows[6]["nHoldSt"] == 2)
# 8 : ⑨売り（SHORT 3）・⑤⑯ は 7 で期限切れ → LONG 1 / SHORT 3 / NET −2 → 初期値で決済
r = play(Feed(ev5, sat={0: 1}), 12, PR3, beUse=False)
check("初期値 : 8 で NET 決済（新しい売り・反対 3 ≥ 2・NET −2 ≤ 0）", [x[1] for x in r.orders("order_close")] == [8])
r = play(Feed(ev5, sat={0: 1}), 12, PR3, beUse=False, exUse=False)
check("NET 決済 OFF : 決済注文なし（SL のみ）", not r.orders("order_close") and r.rows[-1]["nPosDir"] == 1)
r = play(Feed(ev5, sat={0: 1}), 12, PR3, beUse=False, exOpp=4)
check("反対方向の最低値 4 : SHORT 3 では決済しない", not r.orders("order_close"))
r = play(Feed(ev5, sat={0: 1}), 12, PR3, beUse=False, exNet=-3)
check("決済境界 −3 : NET −2 では決済しない", not r.orders("order_close"))
r = play(Feed({4: {"05": "L", "16": "L"}, 6: {"09": "S"}}, sat={0: 1}), 12, PR3, beUse=False)
check("初期値 : 6 は NET 1 > 0 で決済せず、7 の期限切れ（NET −1）でも新シグナルがないので決済しない",
      r.rows[7]["nNet"] == -1 and not r.orders("order_close"))
r = play(Feed({4: {"05": "L", "16": "L"}, 6: {"09": "S"}}, sat={0: 1}), 12, PR3, beUse=False, exNeedNew=False)
check("新しい逆方向シグナル必須 OFF : 期限切れによる点数変化だけで 7 に決済", [x[1] for x in r.orders("order_close")] == [7])
EV6 = {4: {"05": "L", "16": "L"}, 6: {"09": "S"}}
r = play(Feed(EV6, sat={0: 1, 6: -1}), 12, PR3, beUse=False)
check("初期値 : 6 は NET +1（LONG 4 / SHORT 3）なので決済しない", r.rows[6]["nNet"] == 1 and not any(x[1] == 6 for x in r.orders("order_close")))
r = play(Feed(EV6, sat={0: 1, 6: -1}), 12, PR3, beUse=False, exNet=1)
check("決済境界 1 : NET +1 でも（新しい売り・反対 3）6 で決済", [x[1] for x in r.orders("order_close")] == [6])

# ===========================================================================
# 12. 建値移動
# ===========================================================================
def pr_be(extra):
    p = {i: (2000.0, None, None, None) for i in range(30)}
    p[5] = (2002.0, 2003.0, 2001.0, 2002.0)      # 約定足（始値 2002）
    p.update(extra)
    return p


EVB = {4: {"05": "L", "16": "L"}}
# 7 : 安値 2001（移動後 SL 2002 より下）を付けた後に終値 2012 → 発動。8 : 安値 2001.5 で建値 SL 約定
PB = pr_be({6: (2003.0, 2010.0, 2002.5, 2008.0), 7: (2008.0, 2012.5, 2001.0, 2012.0), 8: (2012.0, 2012.5, 2001.5, 2004.0)})
r = play(Feed(EVB, sat={0: 1}), 10, PB)
ox = r.orders("order_exit")
check("初期値（建値 ON）: 終値 2012 ≥ 2002 + 10 の確定足 7 で SL を 2002 へ（同じ ID の置き換え 1 回）",
      r.rows[7]["nBeDone"] and r.rows[7]["nSlPrice"] == 2002.0 and [(x[1], x[2], x[4]) for x in ox] == [(4, "L-SL", None), (7, "L-SL", 2002.0)])
check("発動前（6、終値 2008）は未発動・SL 1987", not r.rows[6]["nBeDone"] and r.rows[6]["nSlPrice"] == 1987.0 and r.rows[6]["nBeTrigLine"] == 2012.0)
check("遡及なし : 発動足 7 の安値 2001 では建値 SL を約定させない", not any(x[0] == "fill_exit" and x[1] == 7 for x in r.b.log))
fx = [x for x in r.b.log if x[0] == "fill_exit"]
check("建値 SL は次の足（8）で 2002 に約定し、「建値移動後の SL」として 1 回だけ記録",
      len(fx) == 1 and fx[0][1] == 8 and fx[0][4] == 2002.0 and r.rows[8]["TS"][0:9] == [1, 0, 0, 0, 0, 0.0, 0, 1, 0]
      and "建値移動後の SL" in r.rows[8]["dCloseTxt"] and "損益ゼロ" in r.rows[8]["dCloseTxt"])
check("ポジションは常に 1 本・保護注文は ID 1 つ（L-SL）。発動足 7 の実行後に 2002 へ置き換わり、それまでは loss 1500 tick（1987）",
      r.b.max_abs_pos == 1.0 and {x[2] for x in ox} == {"L-SL"} and r.rows[6]["exits"] == {"L-SL": (1987.0, 1500)}
      and r.rows[7]["exits"] == {"L-SL": (2002.0, None)})
r = play(Feed(EVB, sat={0: 1}), 10, pr_be({6: (2003.0, 2013.5, 2002.5, 2011.0)}))
check("高値 2013.5 が発動幅を超えても、終値 2011 なら発動しない（終値判定のみ）", not any(x["nBeDone"] for x in r.rows))
r = play(Feed(EVB, sat={0: 1}), 10, pr_be({6: (2003.0, 2012.5, 2002.5, 2012.0)}), beOff=3.0)
check("利益側の幅 3 : SL = 2002 + 3 = 2005", r.rows[6]["nSlPrice"] == 2005.0 and r.orders("order_exit")[-1][4] == 2005.0)
r = play(Feed(EVB, sat={0: 1}), 10, pr_be({6: (2003.0, 2010.5, 2002.5, 2009.0)}), beTrig=7.0)
check("発動幅 7 : 終値 2009 ≥ 2009 で発動", r.rows[6]["nBeDone"] and r.rows[6]["nSlPrice"] == 2002.0)
r = play(Feed(EVB, sat={0: 1}), 10, pr_be({6: (2003.0, 2012.5, 2002.5, 2012.0)}), beUse=False)
check("建値移動 OFF : 発動せず SL 1987 のまま", not r.rows[6]["nBeDone"] and r.rows[9]["nSlPrice"] == 1987.0 and len(r.orders("order_exit")) == 1)
r = play(Feed(EVB, sat={0: 1}), 10, pr_be({6: (2003.0, 2012.5, 2002.5, 2012.0)}), beOff=10.0)
check("利益側の幅 ≥ 発動幅は無効（補正せず、建値移動しない）", not any(x["nBeDone"] for x in r.rows) and len(r.orders("order_exit")) == 1
      and r.env["beValid"] is False)
# 発動後に NET 低下・期限切れ・データ不備があっても SL は戻らない
PB2 = pr_be({6: (2003.0, 2012.5, 2002.5, 2012.0), 7: (2012.0, 2012.5, 2010.0, 2011.0), 8: (2011.0, 2011.5, 2009.0, 2010.0),
             9: (2010.0, 2010.5, 2008.0, 2009.0), 10: (2009.0, 2009.5, 2007.0, 2008.0)})
r = Run()
f = Feed({4: {"05": "L", "16": "L"}, 9: {"09": "S"}}, sat={0: 1, 9: -1})
for i in range(12):
    ins = f.ins(i)
    if i == 8:
        ins["m24"] = None                         # データ不備
    r.bar(*PB2.get(i, (2000.0, None, None, None)), ins=ins)
check("発動後、期限切れ（7）・データ不備（8）・NET 低下（9 で NET −3）でも SL 2002 のまま・注文の追加なし",
      [r.rows[i]["nSlPrice"] for i in (6, 7, 8, 9)] == [2002.0] * 4 and r.rows[7]["nL"] == 1 and not r.rows[8]["nAllOk"]
      and r.rows[9]["nNet"] < 0 and len(r.orders("order_exit")) == 2)
check("NET 決済注文中も SL は有効（9 で決済注文、建値 SL 2002 の L-SL が残る → 10 始値で NET 決済 1 回）",
      [x[1] for x in r.orders("order_close")] == [9] and r.rows[9]["exits"] == {"L-SL": (2002.0, None)} and r.rows[10]["exits"] == {} and len([x for x in r.b.log if x[0] == "fill_exit"]) == 1
      and [x for x in r.b.log if x[0] == "fill_exit"][0][3] == "close" and r.rows[10]["TS"][8] == 1 and r.rows[10]["TS"][7] == 0)
# 新しいポジションで未発動に戻る
PB3 = pr_be({6: (2003.0, 2012.5, 2002.5, 2012.0), 8: (2012.0, 2012.5, 2001.5, 2004.0),
             11: (2004.0, 2004.5, 2003.0, 2004.0)})
r = play(Feed({4: {"05": "L", "16": "L"}, 10: {"05": "L", "16": "L"}}, sat={0: 1}), 14, PB3)
check("建値 SL 決済の後、新しいポジション（11 約定）は未発動・SL = 新しい約定価格 − 15",
      r.rows[6]["nBeDone"] and r.rows[11]["dFillDir"] == 1 and not r.rows[11]["nBeDone"] and r.rows[11]["nSlPrice"] == 1989.0
      and r.rows[11]["nBeTrigLine"] == 2014.0 and r.rows[8]["TS"][7] == 1)
fe = [x for x in r.b.log if x[0] == "fill_entry"]
check("2 本目のポジションは loss（tick）の新しい SL で保護", len(fe) == 2 and r.b.exits.get("L-SL", {}).get("stop") == 1989.0)
# 約定足の終値で発動
r = play(Feed(EVB, sat={0: 1}), 8, pr_be({5: (2002.0, 2012.5, 2001.0, 2012.0)}))
fx = [x for x in r.b.log if x[0] == "fill_exit"]
check("約定足（5）の終値で発動し得る（その足の安値 2001 には遡らない。6 の始値 2000 は建値 SL 2002 を越えたギャップで 2000 約定）",
      r.rows[5]["nBeDone"] and [(x[1], x[4]) for x in fx] == [(6, 2000.0)] and r.rows[6]["TS"][7] == 1)
# 通常 SL は 通常 SL として記録
r = play(Feed(EVB, sat={0: 1}), 8, pr_be({6: (2002.0, 2003.0, 1985.0, 1990.0)}))
check("建値前の SL は「通常 SL」", r.rows[6]["TS"][6] == 1 and r.rows[6]["TS"][7] == 0 and "通常 SL" in r.rows[6]["dCloseTxt"])

# 対称性（建値・入力変更込み）
for nm, ev_, sat_, pr_, n, over in (
        ("建値発動→建値 SL", EVB, {0: 1}, PB, 10, {}),
        ("建値 利益側 3・発動幅 7", EVB, {0: 1}, pr_be({6: (2003.0, 2010.5, 2002.5, 2009.0), 8: (2009.0, 2009.5, 2004.0, 2006.0)}), 10, dict(beOff=3.0, beTrig=7.0)),
        ("建値後 NET 決済", {4: {"05": "L", "16": "L"}, 9: {"09": "S"}}, {0: 1, 9: -1}, PB2, 12, {}),
        ("入力変更（配点・上限・条件）", ev5, {0: 1}, PR3, 12, dict(pt05=3, capMa=3, entNet=4, hdWarn=1, exOpp=1, exNet=1)),
        ("新シグナル不要", {4: {"05": "L", "16": "L"}, 6: {"09": "S"}}, {0: 1}, PR3, 12, dict(exNeedNew=False, entNeedNew=False))):
    check("LONG / SHORT 対称（" + nm + "）", symmetric(ev_, sat_, pr_, n, **over)[0])
ok_r = True
for seed in range(20):
    case = rand_case(100 + seed)
    ev_, sat_, faults, pr = case
    if faults:
        continue
    ok_r &= symmetric(ev_, sat_, pr, len(pr))[0]
check("LONG / SHORT 対称（建値 ON の初期値・ランダム入力）", ok_r)

print(f"\n{ok} checks passed")

//+------------------------------------------------------------------+
//| XauShortDemoEA.mq5  —  Gold Short automation, stage 3 (DEMO ONLY)  |
//|                                                                    |
//| TradingView (ZoneStrategyXAU_Auto, signal source) -> Windows       |
//| receiver (records) -> ea_bridge.py (claims ENTRY, writes command   |
//| files) -> THIS EA (checks with live XS prices, sends the demo      |
//| order with its initial SL, manages its own position: TP0 at the    |
//| fill-bar close, breakeven 15 USD on closed M5 bars, reports).      |
//|                                                                    |
//| Defaults: DRY_RUN = true (no trade API write of any kind),         |
//| new entries OFF. Real / contest accounts are refused in code       |
//| (no input can allow them). NOT compiled / NOT run by the author:   |
//| see STAGE3_ja.md before any use.                                   |
//+------------------------------------------------------------------+
#property copyright "shota0927-prog"
#property version   "0.30"
#property description "XAU Short demo EA (stage 3). DRY_RUN by default. Demo accounts only."

//--- approved rules (constants on purpose: not changeable from the inputs)
const double RISK_FRACTION = 0.03;   // loss budget = balance right before the decision x 3 %
const int    MAX_AGE_SEC   = 60;     // ENTRY bar close -> 60 s (received / claimed / right before OrderSend)
const double MAX_DEV_FRAC  = 0.20;   // |Bid - ENTRY.px| <= 20 % of (ENTRY.sl - ENTRY.px)
const double MAX_SPREAD    = 0.50;   // Ask - Bid <= 0.50 USD (price units, not points / pips)
const double BE_DIST       = 15.0;   // breakeven trigger, Fixed Distance 15 USD (cfg stBEDist)
const int    BAR_SEC       = 300;    // M5
const string CMD_VERSION   = "1";

enum ENUM_FILLBAR_BE
  {
   FILLBAR_TICKS_SINCE_FILL = 0,     // fill bar: lowest Bid seen by this EA after the fill (skipped after a restart)
   FILLBAR_SKIP             = 1      // fill bar: not used for breakeven
  };

//--- inputs (set on the PC; never a password here)
input bool   InpDryRun          = true;              // DRY_RUN: true = no trade API write at all (orders / closes / SL-TP changes)
input bool   InpAllowNewEntries = false;             // new entries (also needs DryRun = false); protection of own positions is separate
input long   InpExpectedLogin   = 0;                 // demo account login (must be set; 0 = trade writes stay disabled)
input string InpExpectedServer  = "XSFintech-DEMO";  // trade server
input string InpSymbol          = "XAUUSDs";         // XS symbol
input string InpExpectedCurrency= "JPY";             // account currency
input string InpExpectedSid     = "XAU-SHORT|XA-23|AU-2";
input string InpExpectedCfgSha  = "72fa9868a3e196ebcd02e37a12f82416d1149e5bd0567d8bf426e2c49f4695ee";
input string InpExpectedTvSym   = "OANDA:XAUUSD";
input long   InpMagic           = 26102801;          // identification aid only (ownership = journal + live ticket)
input string InpExchangeDir     = "XauShortDemo";    // under Terminal\Common\Files
input int    InpTimerMs         = 500;
input ENUM_FILLBAR_BE InpFillBarBe = FILLBAR_TICKS_SINCE_FILL;   // PROPOSAL (undecided item): fill-bar breakeven source

//--- state
struct OwnedPos
  {
   string   key;
   string   khash;
   ulong    posTicket;
   ulong    orderTicket;
   ulong    dealTicket;
   double   fill;        // actual XS fill price (deal price)
   double   sl0;         // initial SL sent with the order
   double   tp0;         // TP0 of the ENTRY (SATS: fixed at the wait prep)
   double   volume;
   datetime fillTimeSrv; // deal time (server time)
   bool     tpSet;
   bool     beDone;
   bool     tracked;     // the EA saw every tick since the fill (fill-bar extreme valid)
   double   minBid;      // lowest Bid since the fill (short: favourable side)
   datetime lastBarDone; // open time of the last M5 bar evaluated for breakeven
   bool     bePending;   // breakeven triggered but the SL change has not succeeded yet (retried once per closed bar)
   datetime lastTpTry;   // server time of the last TP0 attempt (a failed change is retried once per M5 bar, not every timer)
  };

OwnedPos g_pos;
bool     g_hasPos     = false;
bool     g_envOk      = false;   // demo / login / server / currency / hedging / symbol verified
bool     g_ready      = false;   // startup reconciliation finished
bool     g_haltNew    = false;   // new entries stopped (persisted in the journal); protection continues
string   g_haltReason = "";
bool     g_critical   = false;   // critical error: no new entries, operator action needed
string   g_inflightKey= "";      // PRE_SEND written, final result not known yet -> occupies the single slot
int      g_lock       = INVALID_HANDLE;
int      g_rptSeq     = 0;
string   g_seenKeys[];           // key hashes that already have a journal record (duplicate guard)
bool     g_dryMgmtNoted = false; // DRY_RUN with an own position: noted once in the journal

//+------------------------------------------------------------------+
//| small helpers                                                     |
//+------------------------------------------------------------------+
//--- TimeGMT() has a 1 s resolution: the deadline uses the LATEST possible now (expiry never late) and the future check the
//--- EARLIEST possible now (a future bar is never "in time")
long NowMs() { return (long)TimeGMT() * 1000; }
long NowMsLate() { return (long)TimeGMT() * 1000 + 999; }

//--- first 16 hex chars of SHA-256(key) — the same identity the bridge writes (key_hash) and puts in the file name
string Sha16(const string s)
  {
   uchar src[], k[], dst[];
   StringToCharArray(s, src, 0, StringLen(s), CP_UTF8);
   if(CryptEncode(CRYPT_HASH_SHA256, src, k, dst) < 8)
      return("");
   string h = "";
   for(int i = 0; i < 8; i++)
      h += StringFormat("%02x", dst[i]);
   return(h);
  }

//--- open time of the M5 bar that contains t (integer arithmetic, no operator on datetime)
datetime BarOpenOf(const datetime t) { return((datetime)((long)t - (long)t % BAR_SEC)); }

//--- server time minus GMT in seconds (POSITION_TIME_MSC is server time, the journal is GMT)
long ServerOffsetSec() { return((long)TimeTradeServer() - (long)TimeGMT()); }

string Dir(const string sub) { return(sub == "" ? InpExchangeDir : InpExchangeDir + "\\" + sub); }

bool SeenKey(const string key)
  {
   for(int i = 0; i < ArraySize(g_seenKeys); i++)
      if(g_seenKeys[i] == key)
         return(true);
   return(false);
  }

void AddSeen(const string key)
  {
   if(key == "" || SeenKey(key))
      return;
   int n = ArraySize(g_seenKeys);
   ArrayResize(g_seenKeys, n + 1);
   g_seenKeys[n] = key;
  }

string Sanitize(string s)
  {
   StringReplace(s, "\n", " ");
   StringReplace(s, "\r", " ");
   StringReplace(s, "|", "/");
   return(s);
  }

//--- report file for the bridge (tmp + move = atomic for the reader; an existing report is never overwritten)
void Report(const string key, const string state, const string fields)
  {
   for(int attempt = 0; attempt < 5; attempt++)
     {
      g_rptSeq++;
      string base = IntegerToString(NowMs(), 13, '0') + "_" + IntegerToString(g_rptSeq, 8, '0') + "_" +
                    IntegerToString((long)GetTickCount(), 10, '0');
      string tmp  = Dir("rpt") + "\\" + base + ".tmp";
      string dst  = Dir("rpt") + "\\" + base + ".rpt";
      int h = FileOpen(tmp, FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
      if(h == INVALID_HANDLE)
        {
         Print("report write failed ", GetLastError());
         return;
        }
      FileWriteString(h, "t_ms=" + IntegerToString(NowMs()) + "\n");
      FileWriteString(h, "key_hash=" + Sanitize(key) + "\n");
      FileWriteString(h, "state=" + state + "\n");
      string parts[];
      int n = StringSplit(fields, ';', parts);
      for(int i = 0; i < n; i++)
         if(StringFind(parts[i], "=") > 0)
            FileWriteString(h, Sanitize(parts[i]) + "\n");
      FileClose(h);
      if(FileMove(tmp, FILE_COMMON, dst, FILE_COMMON))
         return;
      FileDelete(tmp, FILE_COMMON);              // the name exists (same ms / sequence after a restart): next sequence
     }
   Print("report move failed ", GetLastError());
  }

//--- append-only journal (flushed before any trade API call) + report. `key` is the 16-hex key hash ("" = EA-level line).
void Journal(const string key, const string state, const string fields)
  {
   string line = IntegerToString(NowMs()) + "|" + Sanitize(key) + "|" + state + "|" + Sanitize(fields);
   int h = FileOpen(Dir("") + "\\journal.txt", FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON | FILE_SHARE_READ);
   if(h == INVALID_HANDLE)
     {
      // a journal that cannot be written makes every later decision unsafe
      g_critical = true;
      Print("CRITICAL: journal write failed ", GetLastError(), " ", line);
      return;
     }
   FileSeek(h, 0, SEEK_END);
   FileWriteString(h, line + "\n");
   FileFlush(h);
   FileClose(h);
   AddSeen(key);
   Report(key, state, fields);
   Print(line);
  }

void HaltNew(const string reason)
  {
   if(!g_haltNew)
     {
      g_haltNew = true;
      g_haltReason = reason;
      Journal("", "HALT_NEW", "reason=" + reason);
     }
  }

bool HaltFileExists() { return(FileIsExist(Dir("") + "\\halt_new", FILE_COMMON)); }

//+------------------------------------------------------------------+
//| environment: demo only                                            |
//+------------------------------------------------------------------+
bool IsDemoAccount() { return(AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_DEMO); }

bool VerifyEnvironment(string &why)
  {
   why = "";
   if(!IsDemoAccount())
      why = "not_demo_account";
   else if(InpExpectedLogin <= 0)
      why = "expected_login_not_set";
   else if(AccountInfoInteger(ACCOUNT_LOGIN) != InpExpectedLogin)
      why = "login_mismatch";
   else if(AccountInfoString(ACCOUNT_SERVER) != InpExpectedServer)
      why = "server_mismatch";
   else if(AccountInfoString(ACCOUNT_CURRENCY) != InpExpectedCurrency)
      why = "currency_mismatch";
   else if(AccountInfoInteger(ACCOUNT_MARGIN_MODE) != ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
      why = "not_hedging_account";
   else if(!SymbolSelect(InpSymbol, true))
      why = "symbol_not_available";
   return(why == "");
  }

//--- every trade API write goes through this gate (DRY_RUN blocks all of them)
bool TradeWritesAllowed()
  {
   if(InpDryRun || !g_envOk || !g_ready || !IsDemoAccount())
      return(false);
   if(AccountInfoInteger(ACCOUNT_LOGIN) != InpExpectedLogin || AccountInfoString(ACCOUNT_SERVER) != InpExpectedServer)
      return(false);
   return(true);
  }

bool NewEntriesAllowed(string &why)
  {
   why = "";
   if(InpDryRun)                 why = "dry_run";
   else if(!InpAllowNewEntries)  why = "new_entries_off";
   else if(!TradeWritesAllowed()) why = "trade_writes_not_allowed";
   else if(g_critical)           why = "critical";
   else if(g_haltNew)            why = "halt_new:" + g_haltReason;
   else if(HaltFileExists())     why = "halt_file";
   else if(g_inflightKey != "")  why = "in_flight:" + g_inflightKey;
   return(why == "");
  }

//+------------------------------------------------------------------+
//| command parsing                                                   |
//+------------------------------------------------------------------+
struct Cmd
  {
   string v, key, khash, tid, ev, side, otype, path, cfg, sid, sym;
   double px, sl, tp;
   long   barCloseMs;
  };

bool ReadCmd(const string file, Cmd &c)
  {
   int h = FileOpen(file, FILE_READ | FILE_TXT | FILE_ANSI | FILE_COMMON | FILE_SHARE_READ);
   if(h == INVALID_HANDLE)
      return(false);
   c.v = ""; c.key = ""; c.khash = ""; c.tid = ""; c.ev = ""; c.side = ""; c.otype = ""; c.path = ""; c.cfg = ""; c.sid = ""; c.sym = "";
   c.px = 0; c.sl = 0; c.tp = 0; c.barCloseMs = 0;
   while(!FileIsEnding(h))
     {
      string line = FileReadString(h);
      int p = StringFind(line, "=");
      if(p <= 0)
         continue;
      string k = StringSubstr(line, 0, p), val = StringSubstr(line, p + 1);
      if(k == "v") c.v = val;
      else if(k == "key") c.key = val;
      else if(k == "key_hash") c.khash = val;
      else if(k == "tid") c.tid = val;
      else if(k == "ev") c.ev = val;
      else if(k == "side") c.side = val;
      else if(k == "otype") c.otype = val;
      else if(k == "path") c.path = val;
      else if(k == "cfg_sha256") c.cfg = val;
      else if(k == "sid") c.sid = val;
      else if(k == "sym") c.sym = val;
      else if(k == "px") c.px = StringToDouble(val);
      else if(k == "sl") c.sl = StringToDouble(val);
      else if(k == "tp") c.tp = StringToDouble(val);
      else if(k == "bar_close_ms") c.barCloseMs = StringToInteger(val);
     }
   FileClose(h);
   return(true);
  }

//--- static checks of the command (no market data); "" = ok
string CheckCmd(const Cmd &c)
  {
   if(c.v != CMD_VERSION)                         return("cmd_version");
   if(c.key == "" || c.khash == "" || Sha16(c.key) != c.khash) return("cmd_key");
   if(c.ev != "ENTRY")                            return("not_entry");
   if(c.side != "SHORT")                          return("side_not_short");
   if(c.otype == "LIMIT")                         return("limit_not_supported");
   if(c.otype != "MARKET")                        return("otype");
   if(c.path != "SATS_PULL" && c.path != "SATS_NOW") return("path_not_initial_settings");
   if(c.sid != InpExpectedSid)                    return("sid_mismatch");
   if(c.cfg != InpExpectedCfgSha)                 return("cfg_mismatch");
   if(c.sym != InpExpectedTvSym)                  return("tv_symbol_mismatch");
   if(!MathIsValidNumber(c.px) || !MathIsValidNumber(c.sl) || !MathIsValidNumber(c.tp)) return("price_not_finite");
   if(!(c.px > 0 && c.sl > 0 && c.tp > 0))        return("price_not_positive");
   if(!(c.sl > c.px && c.px > c.tp))              return("price_geometry");
   if(c.barCloseMs <= 0 || c.barCloseMs % ((long)BAR_SEC * 1000) != 0) return("bar_time");
   return("");
  }

//--- the 60 s deadline; a negative age (clock / future bar) is a rejection, never "in time"
string CheckDeadline(const Cmd &c)
  {
   if(NowMs() - c.barCloseMs < 0)                          return("clock_or_future_bar");
   if(NowMsLate() - c.barCloseMs > (long)MAX_AGE_SEC * 1000) return("expired");
   return("");
  }

//+------------------------------------------------------------------+
//| market / account checks and the lot size                         |
//+------------------------------------------------------------------+
bool InTradeSession()
  {
   MqlDateTime t;
   datetime now = TimeTradeServer();
   TimeToStruct(now, t);
   datetime day0 = (datetime)((long)now - (long)now % 86400);
   datetime from, to;
   for(uint i = 0; i < 10; i++)
     {
      if(!SymbolInfoSessionTrade(InpSymbol, (ENUM_DAY_OF_WEEK)t.day_of_week, i, from, to))
         break;
      long f = (long)from % 86400, e = (long)to % 86400;
      if((long)now >= (long)day0 + f && (e == 0 ? (long)now < (long)day0 + 86400 : (long)now < (long)day0 + e))
         return(true);
     }
   return(false);
  }

ENUM_ORDER_TYPE_FILLING FillingMode()
  {
   long fm = SymbolInfoInteger(InpSymbol, SYMBOL_FILLING_MODE);
   if((fm & SYMBOL_FILLING_FOK) == SYMBOL_FILLING_FOK)
      return(ORDER_FILLING_FOK);
   if((fm & SYMBOL_FILLING_IOC) == SYMBOL_FILLING_IOC)
      return(ORDER_FILLING_IOC);
   return(ORDER_FILLING_RETURN);
  }

//--- builds the request; "" = ok. Every value comes from the terminal right now (no fixed contract size / rate).
string PrepareOrder(const Cmd &c, MqlTradeRequest &req, string &detail)
  {
   detail = "";
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED)) return("terminal_trade_not_allowed");
   if(!AccountInfoInteger(ACCOUNT_TRADE_ALLOWED) || !AccountInfoInteger(ACCOUNT_TRADE_EXPERT)) return("account_trade_not_allowed");
   long tm = SymbolInfoInteger(InpSymbol, SYMBOL_TRADE_MODE);
   if(tm != SYMBOL_TRADE_MODE_FULL && tm != SYMBOL_TRADE_MODE_SHORTONLY) return("symbol_sell_not_allowed");
   if(!InTradeSession())                                    return("outside_trade_session");
   // account-wide single slot: any position or pending order (manual / other EA included) blocks a new entry
   if(PositionsTotal() > 0)                                 return("max1_position_exists");
   if(OrdersTotal() > 0)                                    return("max1_pending_order_exists");
   if(g_hasPos)                                             return("max1_own_position");
   MqlTick tk;
   if(!SymbolInfoTick(InpSymbol, tk) || tk.bid <= 0 || tk.ask <= 0) return("no_price");
   double spread = tk.ask - tk.bid;
   if(spread > MAX_SPREAD + 1e-9)                           return("spread:" + DoubleToString(spread, 3));
   double slw = c.sl - c.px;
   if(slw <= 0)                                             return("sl_width_not_positive");
   double dev = MathAbs(tk.bid - c.px);
   if(dev > MAX_DEV_FRAC * slw + 1e-9)                      return("price_deviation:" + DoubleToString(dev, 3));
   double tick = SymbolInfoDouble(InpSymbol, SYMBOL_TRADE_TICK_SIZE);
   double point = SymbolInfoDouble(InpSymbol, SYMBOL_POINT);
   int digits = (int)SymbolInfoInteger(InpSymbol, SYMBOL_DIGITS);
   if(tick <= 0 || point <= 0)                              return("symbol_spec");
   // SL on the price grid, never widened: a short's SL is rounded DOWN (towards the entry)
   double sl = NormalizeDouble(MathFloor(c.sl / tick + 1e-9) * tick, digits);
   double price = NormalizeDouble(tk.bid, digits);
   long stops = SymbolInfoInteger(InpSymbol, SYMBOL_TRADE_STOPS_LEVEL);
   if(sl <= tk.ask + stops * point)                         return("sl_too_close_or_crossed");
   double budget = AccountInfoDouble(ACCOUNT_BALANCE) * RISK_FRACTION;
   if(budget <= 0)                                          return("budget");
   double p1 = 0;
   if(!OrderCalcProfit(ORDER_TYPE_SELL, InpSymbol, 1.0, price, sl, p1) || p1 >= 0) return("order_calc_profit_failed");
   double lossPerLot = -p1;
   double vmin = SymbolInfoDouble(InpSymbol, SYMBOL_VOLUME_MIN), vmax = SymbolInfoDouble(InpSymbol, SYMBOL_VOLUME_MAX);
   double vstep = SymbolInfoDouble(InpSymbol, SYMBOL_VOLUME_STEP), vlim = SymbolInfoDouble(InpSymbol, SYMBOL_VOLUME_LIMIT);
   if(vmin <= 0 || vstep <= 0 || vmax <= 0)                 return("volume_spec");
   double vol = MathFloor(budget / lossPerLot / vstep + 1e-9) * vstep;
   if(vol > vmax) vol = MathFloor(vmax / vstep + 1e-9) * vstep;
   if(vlim > 0 && vol > vlim) vol = MathFloor(vlim / vstep + 1e-9) * vstep;
   double loss = 0;
   for(int guard = 0; guard < 1000 && vol >= vmin - 1e-9; guard++)
     {
      double p = 0;
      if(!OrderCalcProfit(ORDER_TYPE_SELL, InpSymbol, vol, price, sl, p)) return("order_calc_profit_failed");
      loss = -p;
      if(loss <= budget + 1e-6)
         break;
      vol -= vstep;                                          // the final volume must stay within the budget
     }
   vol = NormalizeDouble(vol, 8);
   if(vol < vmin - 1e-9)                                    return("below_min_lot");
   double margin = 0;
   if(!OrderCalcMargin(ORDER_TYPE_SELL, InpSymbol, vol, price, margin)) return("order_calc_margin_failed");
   if(margin > AccountInfoDouble(ACCOUNT_MARGIN_FREE))      return("margin");
   ZeroMemory(req);
   req.action       = TRADE_ACTION_DEAL;
   req.symbol       = InpSymbol;
   req.type         = ORDER_TYPE_SELL;
   req.volume       = vol;
   req.price        = price;
   req.sl           = sl;                                   // initial SL always attached
   req.tp           = 0.0;                                  // TP0 is set at the fill-bar close (as the Strategy does)
   req.magic        = (ulong)InpMagic;
   req.comment      = "XSD:" + c.khash;
   req.type_filling = FillingMode();
   req.type_time    = ORDER_TIME_GTC;
   double remain = MAX_DEV_FRAC * slw - dev;                // execution deviation limited to the remaining 20 % allowance
   req.deviation    = (ulong)MathMax(0.0, MathFloor(remain / point));
   MqlTradeCheckResult chk;
   ZeroMemory(chk);
   if(!OrderCheck(req, chk))                                return("order_check:" + IntegerToString((int)chk.retcode));
   detail = "bid=" + DoubleToString(tk.bid, digits) + ";ask=" + DoubleToString(tk.ask, digits) + ";spread=" + DoubleToString(spread, 3) +
            ";dev=" + DoubleToString(dev, 3) + ";sl=" + DoubleToString(sl, digits) + ";volume=" + DoubleToString(vol, 2) +
            ";budget_jpy=" + DoubleToString(budget, 0) + ";planned_loss_jpy=" + DoubleToString(loss, 0) +
            ";margin_jpy=" + DoubleToString(margin, 0) +
            ";note=actual loss can exceed 3% (fill slippage / SL slippage / conversion / commission / swap not in the budget)";
   return("");
  }

//+------------------------------------------------------------------+
//| trade API wrappers (the only OrderSend calls)                     |
//+------------------------------------------------------------------+
bool IsDefiniteReject(uint rc)
  {
   switch(rc)
     {
      case TRADE_RETCODE_REQUOTE: case TRADE_RETCODE_REJECT: case TRADE_RETCODE_CANCEL: case TRADE_RETCODE_INVALID:
      case TRADE_RETCODE_INVALID_VOLUME: case TRADE_RETCODE_INVALID_PRICE: case TRADE_RETCODE_INVALID_STOPS:
      case TRADE_RETCODE_TRADE_DISABLED: case TRADE_RETCODE_MARKET_CLOSED: case TRADE_RETCODE_NO_MONEY:
      case TRADE_RETCODE_PRICE_CHANGED: case TRADE_RETCODE_PRICE_OFF: case TRADE_RETCODE_INVALID_EXPIRATION:
      case TRADE_RETCODE_TOO_MANY_REQUESTS: case TRADE_RETCODE_SERVER_DISABLES_AT: case TRADE_RETCODE_CLIENT_DISABLES_AT:
      case TRADE_RETCODE_INVALID_FILL: case TRADE_RETCODE_LIMIT_ORDERS: case TRADE_RETCODE_LIMIT_VOLUME:
      case TRADE_RETCODE_LIMIT_POSITIONS: case TRADE_RETCODE_SHORT_ONLY: case TRADE_RETCODE_LONG_ONLY: case TRADE_RETCODE_FIFO_CLOSE:
      case TRADE_RETCODE_HEDGE_PROHIBITED:
         return(true);
     }
   return(false);
  }

//--- confirm a fill from the deal / position, never from OrderSend's bool alone
//--- an open position of this symbol + magic whose comment is exactly the tag of this key hash (0 = none)
ulong FindTaggedPosition(const string khash)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t > 0 && PositionSelectByTicket(t) && PositionGetString(POSITION_SYMBOL) == InpSymbol &&
         PositionGetInteger(POSITION_MAGIC) == InpMagic && PositionGetString(POSITION_COMMENT) == "XSD:" + khash)
         return(t);
     }
   return(0);
  }

bool ConfirmFill(const string key, const string khash, ulong orderTicket, ulong dealTicket, double sl0, double tp0)
  {
   ulong posId = 0;
   for(int i = 0; i < 20 && posId == 0; i++)        // the deal can reach the history a little after OrderSend returns
     {
      if(dealTicket > 0 && HistoryDealSelect(dealTicket))
         posId = (ulong)HistoryDealGetInteger(dealTicket, DEAL_POSITION_ID);
      if(posId == 0)
         Sleep(100);
     }
   if(posId == 0)
      posId = FindTaggedPosition(khash);
   if(posId == 0 || !PositionSelectByTicket(posId))
      return(false);
   if(PositionGetString(POSITION_SYMBOL) != InpSymbol || PositionGetInteger(POSITION_MAGIC) != InpMagic ||
      PositionGetInteger(POSITION_TYPE) != POSITION_TYPE_SELL)
      return(false);
   g_pos.key = key; g_pos.khash = khash; g_pos.posTicket = posId; g_pos.orderTicket = orderTicket; g_pos.dealTicket = dealTicket;
   g_pos.fill = PositionGetDouble(POSITION_PRICE_OPEN);  // actual XS fill (average price if the fill came in parts)
   g_pos.volume = PositionGetDouble(POSITION_VOLUME);
   g_pos.sl0 = sl0; g_pos.tp0 = tp0;
   g_pos.fillTimeSrv = (datetime)PositionGetInteger(POSITION_TIME);
   g_pos.tpSet = false; g_pos.beDone = false; g_pos.tracked = true; g_pos.minBid = g_pos.fill; g_pos.lastBarDone = 0;
   g_pos.bePending = false; g_pos.lastTpTry = 0;
   g_hasPos = true;
   Journal(key, "FILLED", "order=" + IntegerToString((long)orderTicket) + ";deal=" + IntegerToString((long)dealTicket) +
           ";position=" + IntegerToString((long)posId) + ";fill_price=" + DoubleToString(g_pos.fill, 5) +
           ";volume=" + DoubleToString(g_pos.volume, 2) + ";sl0=" + DoubleToString(sl0, 5) + ";tp0=" + DoubleToString(tp0, 5) +
           ";fill_time=" + IntegerToString((long)g_pos.fillTimeSrv));
   return(true);
  }

bool ClosePosition(const string key, const string reason)
  {
   if(!TradeWritesAllowed() || !g_hasPos || !PositionSelectByTicket(g_pos.posTicket))
      return(false);
   MqlTick tk;
   if(!SymbolInfoTick(InpSymbol, tk))
      return(false);
   MqlTradeRequest r;
   MqlTradeResult res;
   ZeroMemory(r);
   ZeroMemory(res);
   r.action = TRADE_ACTION_DEAL; r.symbol = InpSymbol; r.type = ORDER_TYPE_BUY; r.position = g_pos.posTicket;
   r.volume = PositionGetDouble(POSITION_VOLUME); r.price = tk.ask; r.magic = (ulong)InpMagic; r.comment = "XSD:" + g_pos.khash + ":C";
   r.type_filling = FillingMode(); r.deviation = 1000;
   Journal(key, "CLOSE_PRE_SEND", "reason=" + reason + ";position=" + IntegerToString((long)g_pos.posTicket));
   bool ok = OrderSend(r, res);
   Journal(key, ok && (res.retcode == TRADE_RETCODE_DONE || res.retcode == TRADE_RETCODE_DONE_PARTIAL) ? "CLOSE_SENT" : "CLOSE_FAILED",
           "reason=" + reason + ";retcode=" + IntegerToString((int)res.retcode));
   return(ok && (res.retcode == TRADE_RETCODE_DONE || res.retcode == TRADE_RETCODE_DONE_PARTIAL));
  }

//--- SL / TP change of the OWN position; never loosens a short's SL, never removes it
bool ModifyOwn(const string what, double newSl, double newTp)
  {
   if(!TradeWritesAllowed() || !g_hasPos || !PositionSelectByTicket(g_pos.posTicket))
      return(false);
   double curSl = PositionGetDouble(POSITION_SL);
   if(newSl <= 0 || (curSl > 0 && newSl > curSl + 1e-9))
     {
      Journal(g_pos.key, "MODIFY_REFUSED", "what=" + what + ";reason=would_loosen_or_remove_sl");
      return(false);
     }
   MqlTradeRequest r;
   MqlTradeResult res;
   ZeroMemory(r);
   ZeroMemory(res);
   r.action = TRADE_ACTION_SLTP; r.symbol = InpSymbol; r.position = g_pos.posTicket; r.sl = newSl; r.tp = newTp;
   r.magic = (ulong)InpMagic;
   bool ok = OrderSend(r, res);
   if(!ok || res.retcode != TRADE_RETCODE_DONE)
     {
      Journal(g_pos.key, "MODIFY_FAILED", "what=" + what + ";retcode=" + IntegerToString((int)res.retcode) + ";sl_kept=" + DoubleToString(curSl, 5));
      HaltNew("modify_failed:" + what);
      return(false);
     }
   return(true);
  }

//--- the single entry path: deadline + checks right before OrderSend, journal before / after, result classified
void ProcessEntry(const Cmd &c, const string id)
  {
   Journal(id, "SEEN", "tid=" + c.tid + ";bar_close_ms=" + IntegerToString(c.barCloseMs));
   string why = CheckCmd(c);
   if(why == "") why = CheckDeadline(c);
   string gate = "";
   if(why == "" && !NewEntriesAllowed(gate) && gate != "dry_run" && gate != "new_entries_off")
      why = gate;                                    // skipped now, never re-tried later (a skipped signal stays skipped)
   MqlTradeRequest req;
   string detail = "";
   if(why == "") why = PrepareOrder(c, req, detail);
   if(why != "")
     {
      Journal(id, "SKIPPED", "reason=" + why);
      return;
     }
   if(gate == "dry_run" || gate == "new_entries_off")
     {
      Journal(id, "DRY_RUN_NOT_SENT", "gate=" + gate + ";" + detail);
      return;
     }
   Journal(id, "DECIDED", detail);
   why = CheckDeadline(c);                           // re-checked immediately before the send (journal writes take time)
   if(why == "" && !TradeWritesAllowed()) why = "trade_writes_not_allowed";
   if(why != "")
     {
      Journal(id, "SKIPPED", "reason=" + why + ";stage=right_before_send");
      return;
     }
   g_inflightKey = id;
   Journal(id, "PRE_SEND", "volume=" + DoubleToString(req.volume, 2) + ";sl=" + DoubleToString(req.sl, 5) + ";price=" + DoubleToString(req.price, 5));
   MqlTradeResult res;
   ZeroMemory(res);
   bool ok = OrderSend(req, res);
   Journal(id, "SEND_RETURNED", "ok=" + (ok ? "1" : "0") + ";retcode=" + IntegerToString((int)res.retcode) + ";order=" +
           IntegerToString((long)res.order) + ";deal=" + IntegerToString((long)res.deal) + ";fill_price=" + DoubleToString(res.price, 5) +
           ";volume=" + DoubleToString(res.volume, 2));
   if(res.retcode == TRADE_RETCODE_DONE || res.retcode == TRADE_RETCODE_DONE_PARTIAL)
     {
      if(ConfirmFill(id, c.khash, res.order, res.deal, req.sl, c.tp))
        {
         g_inflightKey = "";
         if(res.retcode == TRADE_RETCODE_DONE_PARTIAL)
            Journal(id, "PARTIAL_FILL", "volume=" + DoubleToString(g_pos.volume, 2) + ";requested=" + DoubleToString(req.volume, 2));
         CheckProtection();
         return;
        }
      Journal(id, "UNKNOWN", "reason=done_but_fill_not_confirmed");
      HaltNew("unknown_result:" + c.khash);
      return;                                        // the in-flight slot stays occupied until reconciled
     }
   if(!ok && IsDefiniteReject(res.retcode))
     {
      g_inflightKey = "";
      Journal(id, "REJECTED", "retcode=" + IntegerToString((int)res.retcode));
      return;
     }
   Journal(id, "UNKNOWN", "retcode=" + IntegerToString((int)res.retcode));
   HaltNew("unknown_result:" + c.khash);
  }

//--- after a fill: the initial SL must be on the position; otherwise emergency close of the OWN position + stop new entries
void CheckProtection()
  {
   if(!g_hasPos || !PositionSelectByTicket(g_pos.posTicket))
      return;
   double sl = PositionGetDouble(POSITION_SL);
   double tick = SymbolInfoDouble(InpSymbol, SYMBOL_TRADE_TICK_SIZE);
   if(sl > 0 && MathAbs(sl - g_pos.sl0) <= tick * 0.5 + 1e-9)
     {
      Journal(g_pos.key, "PROTECTED", "sl=" + DoubleToString(sl, 5));
      return;
     }
   HaltNew("initial_sl_missing");
   Journal(g_pos.key, "SL_MISSING", "sl_on_position=" + DoubleToString(sl, 5));
   if(ClosePosition(g_pos.key, "emergency_initial_sl_missing"))
      Journal(g_pos.key, "EMERGENCY_CLOSE", "result=sent");
   else
     {
      g_critical = true;
      Journal(g_pos.key, "CRITICAL", "reason=emergency_close_failed");
     }
  }

//+------------------------------------------------------------------+
//| management of the OWN position (closed M5 bars, server time)      |
//+------------------------------------------------------------------+
void ManageOwn()
  {
   if(!g_hasPos)
      return;
   if(!PositionSelectByTicket(g_pos.posTicket))
     {
      string reason = "unknown";
      if(HistorySelectByPosition(g_pos.posTicket))
        {
         for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
           {
            ulong d = HistoryDealGetTicket(i);
            if(HistoryDealGetInteger(d, DEAL_ENTRY) == DEAL_ENTRY_OUT)
              {
               long dr = HistoryDealGetInteger(d, DEAL_REASON);
               reason = dr == DEAL_REASON_SL ? "sl" : dr == DEAL_REASON_TP ? "tp" : dr == DEAL_REASON_EXPERT ? "expert" :
                        dr == DEAL_REASON_CLIENT ? "manual" : "other";
               Journal(g_pos.key, "CLOSED", "reason=" + reason + ";deal=" + IntegerToString((long)d) + ";price=" +
                       DoubleToString(HistoryDealGetDouble(d, DEAL_PRICE), 5) + ";profit=" + DoubleToString(HistoryDealGetDouble(d, DEAL_PROFIT), 0) +
                       ";commission=" + DoubleToString(HistoryDealGetDouble(d, DEAL_COMMISSION), 0) + ";swap=" + DoubleToString(HistoryDealGetDouble(d, DEAL_SWAP), 0));
               break;
              }
           }
        }
      if(reason == "unknown")
         Journal(g_pos.key, "CLOSED", "reason=not_found_in_history");
      g_hasPos = false;
      return;
     }
   MqlTick tk;
   if(SymbolInfoTick(InpSymbol, tk) && g_pos.tracked && tk.bid > 0)
      g_pos.minBid = MathMin(g_pos.minBid, tk.bid);
   if(!TradeWritesAllowed())
     {
      // DRY_RUN / environment lost: no SL-TP change of any kind (the SL already on the position stays)
      if(!g_dryMgmtNoted)
        {
         g_dryMgmtNoted = true;
         Journal(g_pos.key, "MANAGEMENT_BLOCKED", "reason=trade_writes_not_allowed;note=the_server_side_sl_stays");
        }
      return;
     }
   g_dryMgmtNoted = false;
   datetime now = TimeTradeServer();
   datetime fillBarOpen = BarOpenOf(g_pos.fillTimeSrv);
   datetime fillBarClose = fillBarOpen + BAR_SEC;
   if(now < fillBarClose)
      return;
   int digits = (int)SymbolInfoInteger(InpSymbol, SYMBOL_DIGITS);
   // the Strategy's fill confirmation (SATS) at the fill-bar close: TP stays TP0. A failed TP0 change is retried once per
   // M5 bar (the SL is kept meanwhile) and never blocks the breakeven of the following bars.
   if(!g_pos.tpSet && (g_pos.lastTpTry == 0 || BarOpenOf(now) > BarOpenOf(g_pos.lastTpTry)))
     {
      g_pos.lastTpTry = now;
      if(!(g_pos.sl0 - g_pos.fill > 0 && g_pos.fill - g_pos.tp0 > 0))
        {
         // CLOSE_REQ equivalent, re-checked with the XS fill: a fill beyond SL0 / TP0 is closed at market
         Journal(g_pos.key, "FILL_SIDE_BAD", "fill=" + DoubleToString(g_pos.fill, digits));
         ClosePosition(g_pos.key, "bad_fill_side_mt5");
         return;
        }
      if(!PositionSelectByTicket(g_pos.posTicket))
         return;
      double curSl = PositionGetDouble(POSITION_SL);
      if(ModifyOwn("tp0", curSl, NormalizeDouble(g_pos.tp0, digits)))
        {
         g_pos.tpSet = true;
         Journal(g_pos.key, "TP_SET", "tp=" + DoubleToString(g_pos.tp0, digits) + ";sl_kept=" + DoubleToString(curSl, digits));
        }
     }
   if(g_pos.lastBarDone == 0)
     {
      // breakeven on the fill bar: only the price seen after the fill (no pre-fill low); not after a restart
      if(!g_pos.beDone && InpFillBarBe == FILLBAR_TICKS_SINCE_FILL && g_pos.tracked)
         TryBreakeven(g_pos.minBid, fillBarOpen);
      g_pos.lastBarDone = fillBarOpen;
     }
   if(g_pos.beDone)
      return;
   MqlRates rates[];
   datetime from = g_pos.lastBarDone + BAR_SEC;      // closed bars after the fill bar; a pending breakeven retries on each
   int n = CopyRates(InpSymbol, PERIOD_M5, from, now, rates);
   for(int i = 0; i < n && !g_pos.beDone; i++)
     {
      if(rates[i].time < from || rates[i].time + BAR_SEC > now)
         continue;                                   // only closed bars after the fill bar
      TryBreakeven(rates[i].low, rates[i].time);
      g_pos.lastBarDone = rates[i].time;
     }
  }

void TryBreakeven(double favLow, datetime barOpen)
  {
   if(g_pos.beDone || (favLow <= 0 && !g_pos.bePending))
      return;
   if(g_pos.bePending || g_pos.fill - favLow >= BE_DIST - 1e-9)
     {
      g_pos.bePending = true;
      int digits = (int)SymbolInfoInteger(InpSymbol, SYMBOL_DIGITS);
      double newSl = NormalizeDouble(g_pos.fill, digits);   // the XS fill price (not TradingView's BE_MOVE price)
      if(!PositionSelectByTicket(g_pos.posTicket))          // fresh snapshot: the TP may have just been set
         return;
      double curTp = PositionGetDouble(POSITION_TP);
      if(ModifyOwn("breakeven", newSl, curTp))
        {
         g_pos.beDone = true;
         g_pos.bePending = false;
         Journal(g_pos.key, "BE_SET", "sl=" + DoubleToString(newSl, digits) + ";bar_open=" + IntegerToString((long)barOpen) +
                 ";fav=" + DoubleToString(favLow, digits));
        }
     }
  }

//+------------------------------------------------------------------+
//| startup reconciliation from the journal + live orders / history   |
//+------------------------------------------------------------------+
void Reconcile()
  {
   string lastKey = "", lastPreSend = "", lastFinal = "";
   long   preSendMs = 0;
   ulong  posTicket = 0;
   string posKey = "";
   double sl0 = 0, tp0 = 0, fill = 0;
   long   fillTime = 0;
   bool   closed = false;
   int h = FileOpen(Dir("") + "\\journal.txt", FILE_READ | FILE_TXT | FILE_ANSI | FILE_COMMON | FILE_SHARE_READ | FILE_SHARE_WRITE);
   if(h != INVALID_HANDLE)
     {
      while(!FileIsEnding(h))
        {
         string parts[];
         string line = FileReadString(h);
         if(StringSplit(line, '|', parts) < 4)
            continue;
         string key = parts[1], st = parts[2], f = parts[3];
         AddSeen(key);
         if(st == "HALT_NEW") { g_haltNew = true; g_haltReason = f; }
         if(st == "RESUME_NEW") { g_haltNew = false; g_haltReason = ""; lastPreSend = ""; }
         if(st == "CRITICAL_CLEARED") g_critical = false;
         if(st == "PRE_SEND") { lastPreSend = key; preSendMs = StringToInteger(parts[0]); }
         if(st == "REJECTED" || st == "FILLED") { if(key == lastPreSend) lastPreSend = ""; }
         if(st == "FILLED")                          // only a confirmed fill of this EA is adopted (never a RECONCILED / unknown one)
           {
            posKey = key; closed = false;
            string kv[];
            int n = StringSplit(f, ';', kv);
            for(int i = 0; i < n; i++)
              {
               int p = StringFind(kv[i], "=");
               if(p <= 0) continue;
               string k = StringSubstr(kv[i], 0, p), v = StringSubstr(kv[i], p + 1);
               if(k == "position") posTicket = (ulong)StringToInteger(v);
               if(k == "sl0") sl0 = StringToDouble(v);
               if(k == "tp0") tp0 = StringToDouble(v);
               if(k == "fill_price") fill = StringToDouble(v);
               if(k == "fill_time") fillTime = StringToInteger(v);
              }
           }
         if(st == "CLOSED" && key == posKey) closed = true;
         if(st == "CRITICAL") g_critical = true;
        }
      FileClose(h);
     }
   // a send whose result was never recorded: UNKNOWN -> no re-order, look for it in the live positions / history
   if(lastPreSend != "")
     {
      g_inflightKey = lastPreSend;
      HaltNew("unknown_result_after_restart");
      Journal(lastPreSend, "UNKNOWN", "reason=pre_send_without_result_at_startup");
     }
   if(posKey != "" && !closed && posTicket > 0)
     {
      if(PositionSelectByTicket(posTicket) && PositionGetString(POSITION_SYMBOL) == InpSymbol && PositionGetInteger(POSITION_MAGIC) == InpMagic)
        {
         g_pos.key = posKey; g_pos.posTicket = posTicket; g_pos.sl0 = sl0; g_pos.tp0 = tp0; g_pos.fill = fill;
         g_pos.fillTimeSrv = (datetime)fillTime; g_pos.volume = PositionGetDouble(POSITION_VOLUME);
         g_pos.khash = posKey;
         double tick = SymbolInfoDouble(InpSymbol, SYMBOL_TRADE_TICK_SIZE);
         g_pos.tpSet = PositionGetDouble(POSITION_TP) > 0;
         g_pos.beDone = MathAbs(PositionGetDouble(POSITION_SL) - fill) <= tick * 0.5 + 1e-9;
         g_pos.tracked = false;                       // ticks since the fill were not seen: the fill bar is not used for breakeven
         g_pos.minBid = fill;
         g_pos.lastBarDone = 0;
         g_pos.bePending = false;
         g_pos.lastTpTry = 0;
         g_hasPos = true;
         Journal(posKey, "OWNED_AT_STARTUP", "position=" + IntegerToString((long)posTicket));
        }
      else
        {
         g_hasPos = true;                              // let ManageOwn read the closing deal from the history
         g_pos.key = posKey; g_pos.khash = posKey; g_pos.posTicket = posTicket;
        }
     }
   if(g_inflightKey != "")
      ReconcileUnknown(g_inflightKey, preSendMs);
  }

//--- look for the order of an unknown send: positions / deals with our magic AND the key hash in the comment AND after PRE_SEND
void ReconcileUnknown(const string key, long preSendMs)
  {
   // the journal id and the order comment both carry the key hash: symbol + magic + exact comment + opened after PRE_SEND
   for(int i = 0; i < PositionsTotal(); i++)
     {
      ulong t = PositionGetTicket(i);
      if(PositionSelectByTicket(t) && PositionGetInteger(POSITION_MAGIC) == InpMagic && PositionGetString(POSITION_SYMBOL) == InpSymbol &&
         PositionGetString(POSITION_COMMENT) == "XSD:" + key &&
         PositionGetInteger(POSITION_TIME_MSC) - ServerOffsetSec() * 1000 >= preSendMs - 60000)
        {
         Journal(key, "RECONCILED", "position=" + IntegerToString((long)t) + ";note=found_open_after_unknown;comment=" +
                 PositionGetString(POSITION_COMMENT) + ";new_entries=still_halted_until_resume");
         // protection continues only after the operator confirms (RESUME file); until then it is not adopted automatically
         return;
        }
     }
   Journal(key, "UNKNOWN_NOT_FOUND", "note=no_open_position_with_magic_and_tag;new_entries=still_halted_until_resume");
  }

//--- operator file resume_new: clears the new-entry halt only when nothing is unknown / critical
void CheckResume()
  {
   string fc = Dir("") + "\\clear_critical";
   if(FileIsExist(fc, FILE_COMMON))
     {
      FileDelete(fc, FILE_COMMON);
      if(g_critical)
        {
         g_critical = false;
         Journal("", "CRITICAL_CLEARED", "by=operator_file;note=new_entries_stay_halted_until_resume_new");
         HaltNew("after_critical");
        }
     }
   string f = Dir("") + "\\resume_new";
   if(!FileIsExist(f, FILE_COMMON))
      return;
   FileDelete(f, FILE_COMMON);
   if(g_critical)
     {
      Journal("", "RESUME_REFUSED", "reason=critical");
      return;
     }
   g_inflightKey = "";
   g_haltNew = false;
   g_haltReason = "";
   Journal("", "RESUME_NEW", "by=operator_file");
  }

//+------------------------------------------------------------------+
//| command loop                                                      |
//+------------------------------------------------------------------+
void PollCommands()
  {
   string name;
   long sh = FileFindFirst(Dir("cmd") + "\\*.cmd", name, FILE_COMMON);
   if(sh == INVALID_HANDLE)
      return;
   string files[];
   do
     {
      int n = ArraySize(files);
      ArrayResize(files, n + 1);
      files[n] = name;
     }
   while(FileFindNext(sh, name));
   FileFindClose(sh);
   for(int a = 1; a < ArraySize(files); a++)          // oldest bar first (ArraySort does not sort strings)
     {
      string v = files[a];
      int b = a - 1;
      while(b >= 0 && StringCompare(files[b], v) > 0)
        {
         files[b + 1] = files[b];
         b--;
        }
      files[b + 1] = v;
     }
   for(int i = 0; i < ArraySize(files); i++)
     {
      string src = Dir("cmd") + "\\" + files[i];
      Cmd c;
      if(!ReadCmd(src, c))
         Journal("", "BAD_CMD", "file=" + files[i] + ";reason=unreadable");
      else if(c.khash == "" || Sha16(c.key) != c.khash)
         Journal("", "BAD_CMD", "file=" + files[i] + ";reason=key_hash");
      else if(SeenKey(c.khash))
         Report(c.khash, "DUPLICATE", "file=" + files[i]);
      else
         ProcessEntry(c, c.khash);
      FileMove(src, FILE_COMMON, Dir("done") + "\\" + files[i], FILE_COMMON | FILE_REWRITE);
     }
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   if(AccountInfoInteger(ACCOUNT_TRADE_MODE) != ACCOUNT_TRADE_MODE_DEMO)
     {
      Print("XauShortDemoEA: refused (not a demo account). No input can change this.");
      return(INIT_FAILED);
     }
   FolderCreate(Dir(""), FILE_COMMON);
   FolderCreate(Dir("cmd"), FILE_COMMON);
   FolderCreate(Dir("rpt"), FILE_COMMON);
   FolderCreate(Dir("done"), FILE_COMMON);
   // one instance: an exclusive handle on the lock file (released by the terminal when the EA stops / crashes)
   g_lock = FileOpen(Dir("") + "\\ea.lock", FILE_WRITE | FILE_BIN | FILE_COMMON);
   if(g_lock == INVALID_HANDLE)
     {
      Print("XauShortDemoEA: another instance holds the lock (", GetLastError(), ")");
      return(INIT_FAILED);
     }
   string why;
   g_envOk = VerifyEnvironment(why);
   Journal("", "START", "dry_run=" + (InpDryRun ? "1" : "0") + ";new_entries=" + (InpAllowNewEntries ? "1" : "0") + ";env=" +
           (g_envOk ? "ok" : why) + ";server=" + AccountInfoString(ACCOUNT_SERVER) + ";symbol=" + InpSymbol);
   Reconcile();
   g_ready = true;
   EventSetMillisecondTimer(MathMax(100, InpTimerMs));
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   if(g_lock != INVALID_HANDLE)                   // a refused second instance never writes into the running one's journal
     {
      Journal("", "STOP", "reason=" + IntegerToString(reason));
      FileClose(g_lock);
     }
   Comment("");
  }

void OnTimer()
  {
   string why;
   bool env = VerifyEnvironment(why);
   if(env != g_envOk)
     {
      g_envOk = env;
      Journal("", env ? "ENV_OK" : "ENV_LOST", "reason=" + why);
     }
   CheckResume();
   ManageOwn();
   PollCommands();
   string gate;
   NewEntriesAllowed(gate);
   Comment("XauShortDemoEA  DRY_RUN=", InpDryRun, "  new=", (gate == "" ? "ON" : "OFF(" + gate + ")"), "  env=", (g_envOk ? "ok" : why),
           "  own_position=", (g_hasPos ? IntegerToString((long)g_pos.posTicket) : "none"), "  critical=", g_critical);
  }

void OnTick()
  {
   if(g_hasPos && g_pos.tracked)
     {
      MqlTick tk;
      if(SymbolInfoTick(InpSymbol, tk) && tk.bid > 0)
         g_pos.minBid = MathMin(g_pos.minBid, tk.bid);
     }
  }

//--- trade transactions are only recorded (the deal / position check stays the source of truth)
void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &request, const MqlTradeResult &result)
  {
   if(trans.type == TRADE_TRANSACTION_DEAL_ADD && trans.symbol == InpSymbol)
      Journal(g_inflightKey != "" ? g_inflightKey : (g_hasPos ? g_pos.key : ""), "TX_DEAL",
              "deal=" + IntegerToString((long)trans.deal) + ";order=" + IntegerToString((long)trans.order) +
              ";position=" + IntegerToString((long)trans.position) + ";price=" + DoubleToString(trans.price, 5) +
              ";volume=" + DoubleToString(trans.volume, 2));
  }
//+------------------------------------------------------------------+

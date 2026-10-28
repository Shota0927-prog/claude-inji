//+------------------------------------------------------------------+
//| XauShortDemoEA.mq5  —  Gold Short automation, stage 3 (DEMO ONLY)  |
//|                                                                    |
//| TradingView (ZoneStrategyXAU_Auto, signal source) -> Windows       |
//| receiver (records) -> ea_bridge.py (claims ENTRY, writes command   |
//| files, gives the FINAL go / no-go) -> THIS EA (checks with live XS |
//| prices, asks the bridge for the final go, records PRE_SEND, checks |
//| everything again, sends the demo order with its initial SL,        |
//| manages its own position, reports).                               |
//|                                                                    |
//| Defaults: DRY_RUN = true (no trade API write of any kind), new     |
//| entries OFF. Real / contest accounts are refused in code. New      |
//| orders also stay refused until every APPROVED_* constant below is  |
//| set by an explicit decision (edit + recompile).                    |
//| NOT compiled / NOT run by the author: see STAGE3_ja.md.            |
//+------------------------------------------------------------------+
#property copyright "shota0927-prog"
#property version   "0.33"
#property description "XAU Short demo EA (stage 3, ST3-4). DRY_RUN by default. Demo accounts only."

//--- approved rules (constants on purpose: not changeable from the inputs)
const double RISK_FRACTION = 0.03;   // loss budget = balance right before the decision x 3 %
const int    MAX_AGE_SEC   = 60;     // ENTRY bar close -> 60 s (read / claim / final go / after the PRE_SEND record)
const double MAX_DEV_FRAC  = 0.20;   // |Bid - ENTRY.px| <= 20 % of (ENTRY.sl - ENTRY.px)
const double MAX_SPREAD    = 0.50;   // Ask - Bid <= 0.50 USD (price units, not points / pips)
const double BE_DIST       = 15.0;   // breakeven trigger, Fixed Distance 15 USD (cfg stBEDist)
const int    BAR_SEC       = 300;    // M5
const string CMD_VERSION   = "2";

//--- NOT approved yet (proposals). While any of these is false, new orders are refused (DRY_RUN still runs everything).
//--- Setting one to true is a decision of the user (edit the source, recompile); no input can do it.
const bool   APPROVED_BE_PRICE_SOURCE = false;  // breakeven judged on XS M5 Bid bars (not the OANDA BAR notifications)
const bool   APPROVED_FILLBAR_METHOD  = false;  // fill bar: Bid ticks after the fill (InpFillBarBe) or not used
const bool   APPROVED_TP_TIMING       = false;  // TP0 set at the close of the MT5 fill bar
const bool   APPROVED_TP_BEYOND       = false;  // TP0 already passed at that moment: change refused, SL kept, retried per bar
const bool   APPROVED_RETRY_INTERVAL  = false;  // TP / breakeven retry once per M5 bar, emergency close retry EMERGENCY_RETRY_SEC
const bool   APPROVED_CLOSE_DEVIATION = false;  // market close deviation CLOSE_DEVIATION_POINTS
const bool   APPROVED_MONITORING      = false;  // ASK_WAIT_MS / bridge GO validity / heartbeat limits below
//--- proposal values (used as they are only after the approvals above)
const int    ASK_WAIT_MS            = 5000;     // how long the EA waits for the bridge's final go / no-go
const int    BRIDGE_HB_MAX_MS       = 5000;     // bridge heartbeat older than this -> no new entry
const int    EMERGENCY_RETRY_SEC    = 5;        // a required close (emergency / fill side) not completed: next attempt after this many seconds
const int    CLOSE_DEVIATION_POINTS = 1000;     // allowed deviation of a market close

#define CLOSE_NOT_ALLOWED 0
#define CLOSE_FULL        1
#define CLOSE_PARTIAL     2
#define CLOSE_FAILED      3
#define CLOSE_UNKNOWN     4

enum ENUM_FILLBAR_BE
  {
   FILLBAR_TICKS_SINCE_FILL = 0,     // fill bar: lowest Bid of the tick history strictly after the fill, before the fill-bar close
   FILLBAR_SKIP             = 1      // fill bar: not used for breakeven
  };

//--- inputs (set on the PC; never a password here)
input bool   InpDryRun          = true;              // DRY_RUN: true = no trade API write at all (orders / closes / SL-TP changes)
input bool   InpAllowNewEntries = false;             // new entries (also needs DryRun = false and the approvals); protection is separate
input long   InpExpectedLogin   = 0;                 // demo account login (must be set; 0 = trade writes stay disabled)
input string InpExpectedServer  = "XSFintech-DEMO";  // trade server
input string InpSymbol          = "XAUUSDs";         // XS symbol
input string InpExpectedCurrency= "JPY";             // account currency
input string InpExpectedSid     = "XAU-SHORT|XA-23|AU-2";
input string InpExpectedCfgSha  = "72fa9868a3e196ebcd02e37a12f82416d1149e5bd0567d8bf426e2c49f4695ee";
input string InpExpectedTvSym   = "OANDA:XAUUSD";
input long   InpMagic           = 26102801;          // identification aid only (ownership = journal + POSITION_IDENTIFIER)
input string InpExchangeDir     = "XauShortDemo";    // under Terminal\Common\Files
input int    InpTimerMs         = 500;
input ENUM_FILLBAR_BE InpFillBarBe = FILLBAR_TICKS_SINCE_FILL;   // PROPOSAL (not approved): fill-bar breakeven source

//--- state
struct OwnedPos
  {
   string   key;           // key hash of the ENTRY
   long     posId;         // POSITION_IDENTIFIER (stable; = DEAL_POSITION_ID)
   ulong    posTicket;     // current POSITION_TICKET (refreshed by SelectOwn; may differ from posId)
   ulong    orderTicket;
   ulong    dealTicket;
   double   fill;          // actual XS fill price = live POSITION_PRICE_OPEN (average when the order filled in parts)
   double   sl0;           // initial SL sent with the order
   double   tp0;           // TP0 of the ENTRY (SATS: fixed at the wait prep)
   double   volume;        // live POSITION_VOLUME (kept in step by RefreshFill)
   datetime fillTimeSrv;   // first fill time (server time): the fill bar
   long     fillTimeMsc;   // first fill time (server time, ms)
   long     lastInMsc;     // time of the last IN deal of the position (server ms): no price before it is used for breakeven
   int      inDeals;       // number of IN deals the fill state was built from
   bool     fillSyncPending; // live volume / average not (yet) explained by the history: breakeven / fill checks wait
   bool     tpSet;
   bool     beDone;
   bool     bePending;     // breakeven condition met (BE_TRIGGERED, persisted), the SL change has not succeeded yet
   double   beFav;         // the favourable price that met the condition
   datetime beBar;         // open time of the bar that met it
   datetime lastBeTry;     // server time of the last breakeven attempt (retried once per M5 bar)
   bool     fillBarDone;   // the fill bar was evaluated for breakeven (tick history read, or not needed)
   bool     fillBarUnavailNoted;
   datetime lastBarDone;   // open time of the last M5 bar evaluated for breakeven
   datetime lastTpTry;     // server time of the last TP0 attempt
   string   closeReason;   // a close is required (CLOSE_REQUIRED, persisted) until the history shows the position closed
   long     lastCloseTry;  // GMT seconds of the last close attempt
   bool     protectedNoted;
   bool     slMissingNoted;
   bool     missingNoted;
  };

OwnedPos g_pos;

//--- every field set explicitly (no ZeroMemory on a structure holding strings)
void ResetPos()
  {
   g_pos.key = ""; g_pos.posId = 0; g_pos.posTicket = 0; g_pos.orderTicket = 0; g_pos.dealTicket = 0;
   g_pos.fill = 0; g_pos.sl0 = 0; g_pos.tp0 = 0; g_pos.volume = 0; g_pos.fillTimeSrv = 0; g_pos.fillTimeMsc = 0; g_pos.lastInMsc = 0;
   g_pos.inDeals = 0; g_pos.fillSyncPending = false;
   g_pos.tpSet = false; g_pos.beDone = false; g_pos.bePending = false; g_pos.beFav = 0; g_pos.beBar = 0; g_pos.lastBeTry = 0;
   g_pos.fillBarDone = false; g_pos.fillBarUnavailNoted = false;
   g_pos.lastBarDone = 0; g_pos.lastTpTry = 0; g_pos.closeReason = ""; g_pos.lastCloseTry = 0;
   g_pos.protectedNoted = false; g_pos.slMissingNoted = false; g_pos.missingNoted = false;
  }
bool     g_hasPos       = false;
bool     g_envOk        = false;   // demo / login / server / currency / hedging / symbol verified
bool     g_bindOk       = true;    // the journal belongs to this account / server / magic / Strategy
bool     g_ready        = false;   // startup reconciliation finished
bool     g_haltNew      = false;   // new entries stopped (persisted in the journal); protection continues
string   g_haltReason   = "";
bool     g_critical     = false;   // critical error: no new entries, operator action needed
string   g_critReason   = "";
bool     g_journalOk    = true;    // the last required journal write succeeded
string   g_inflightKey  = "";      // PRE_SEND written, send in progress
string   g_unknownKey   = "";      // a send whose result is unknown (cleared only by resolve_unknown after the history check)
long     g_unknownPreMs = 0;       // PRE_SEND time (GMT ms) of the unknown key
double   g_unknownSl    = 0;
double   g_unknownTp    = 0;
string   g_journalPath  = "";
int      g_lock         = INVALID_HANDLE;
int      g_rptSeq       = 0;
string   g_seenKeys[];             // key hashes that already have a journal record (duplicate guard)
bool     g_mgmtNoted    = false;   // management blocked (DRY_RUN / environment) noted once

//+------------------------------------------------------------------+
//| small helpers                                                     |
//+------------------------------------------------------------------+
//--- TimeGMT() has a 1 s resolution: the deadline uses the LATEST possible now (expiry never late) and the future check the
//--- EARLIEST possible now (a future bar is never "in time")
long NowMs() { return (long)TimeGMT() * 1000; }
long NowMsLate() { return (long)TimeGMT() * 1000 + 999; }

//--- integer max / min (MathMax / MathMin work on double)
long MaxL(const long a, const long b) { return(a > b ? a : b); }
long MinL(const long a, const long b) { return(a < b ? a : b); }

//--- open time of the M5 bar that contains t (integer arithmetic, no operator on datetime)
datetime BarOpenOf(const datetime t) { return((datetime)((long)t - (long)t % BAR_SEC)); }

//--- server time minus GMT in seconds (POSITION_TIME_MSC / tick times are server time, the journal is GMT)
long ServerOffsetSec() { return((long)TimeTradeServer() - (long)TimeGMT()); }

string Dir(const string sub) { return(sub == "" ? InpExchangeDir : InpExchangeDir + "\\" + sub); }

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

string NameSafe(string s)
  {
   string o = "";
   for(int i = 0; i < StringLen(s); i++)
     {
      ushort ch = StringGetCharacter(s, i);
      bool ok = (ch >= '0' && ch <= '9') || (ch >= 'A' && ch <= 'Z') || (ch >= 'a' && ch <= 'z') || ch == '-';
      o += ok ? ShortToString(ch) : "_";
     }
   return(o);
  }

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

//--- value of k in a "k=v" line list ("" = missing)
string KvGet(const string &lines[], const string k)
  {
   for(int i = 0; i < ArraySize(lines); i++)
      if(StringFind(lines[i], k + "=") == 0)
         return(StringSubstr(lines[i], StringLen(k) + 1));
   return("");
  }

bool ReadLines(const string path, string &lines[])
  {
   ArrayResize(lines, 0);
   int h = FileOpen(path, FILE_READ | FILE_TXT | FILE_ANSI | FILE_COMMON | FILE_SHARE_READ | FILE_SHARE_WRITE);
   if(h == INVALID_HANDLE)
      return(false);
   while(!FileIsEnding(h))
     {
      string l = FileReadString(h);
      int n = ArraySize(lines);
      ArrayResize(lines, n + 1);
      lines[n] = l;
     }
   FileClose(h);
   return(true);
  }

//--- small file via tmp + move (atomic for the reader); true only when every step succeeded
bool WriteFileAtomic(const string dir, const string name, const string body, const bool rewrite)
  {
   string tmp = dir + "\\" + name + ".tmp", dst = dir + "\\" + name;
   ResetLastError();
   int h = FileOpen(tmp, FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
   if(h == INVALID_HANDLE)
      return(false);
   uint w = FileWriteString(h, body);
   FileFlush(h);
   FileClose(h);
   if(w < (uint)StringLen(body) || GetLastError() != 0)
     {
      FileDelete(tmp, FILE_COMMON);
      return(false);
     }
   if(!FileMove(tmp, FILE_COMMON, dst, FILE_COMMON | (rewrite ? FILE_REWRITE : 0)))
     {
      FileDelete(tmp, FILE_COMMON);
      return(false);
     }
   return(true);
  }

//--- report file for the bridge (an existing report is never overwritten)
void Report(const string key, const string state, const string fields)
  {
   string body = "t_ms=" + IntegerToString(NowMs()) + "\nkey_hash=" + Sanitize(key) + "\nstate=" + state + "\n";
   string parts[];
   int n = StringSplit(fields, ';', parts);
   for(int i = 0; i < n; i++)
      if(StringFind(parts[i], "=") > 0)
         body += Sanitize(parts[i]) + "\n";
   for(int attempt = 0; attempt < 5; attempt++)
     {
      g_rptSeq++;
      // name order = write order, also across EA restarts within the same second: GMT ms, then the PC's monotonic tick
      // count (GetTickCount64 does not restart with the EA), then the sequence of this instance
      string base = IntegerToString(NowMs(), 13, '0') + "_" + IntegerToString((long)GetTickCount64(), 20, '0') + "_" +
                    IntegerToString(g_rptSeq, 8, '0');
      if(WriteFileAtomic(Dir("rpt"), base + ".rpt", body, false))
         return;
     }
   Print("report write failed ", GetLastError());
  }

//--- append-only journal. true only when the line is on disk (open, write length, flush, close all checked).
//--- `key` is the 16-hex key hash ("" = EA-level line). A failed write is printed to the Experts log and to journal_fallback.txt.
bool Journal(const string key, const string state, const string fields)
  {
   string line = IntegerToString(NowMs()) + "|" + Sanitize(key) + "|" + state + "|" + Sanitize(fields);
   bool ok = false;
   ResetLastError();
   int h = FileOpen(g_journalPath, FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON | FILE_SHARE_READ);
   if(h != INVALID_HANDLE)
     {
      if(FileSeek(h, 0, SEEK_END))
        {
         uint w = FileWriteString(h, line + "\n");
         FileFlush(h);
         ok = w >= (uint)StringLen(line) + 1 && GetLastError() == 0;
        }
      FileClose(h);
     }
   g_journalOk = ok;
   if(!ok)
     {
      // a journal that cannot be written makes every new decision unsafe: no new entry until an operator checks it.
      // Protection of an own position (emergency close) is NOT blocked by this (see ClosePosition).
      g_critical = true;
      g_critReason = "journal_write_failed";
      Print("CRITICAL: journal write failed ", GetLastError(), " ", line);
      int f = FileOpen(Dir("") + "\\journal_fallback.txt", FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON | FILE_SHARE_READ);
      if(f != INVALID_HANDLE)
        {
         FileSeek(f, 0, SEEK_END);
         FileWriteString(f, line + "\n");
         FileClose(f);
        }
      return(false);
     }
   AddSeen(key);
   Report(key, state, fields);
   Print(line);
   return(true);
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

void SetCritical(const string key, const string reason)
  {
   g_critical = true;
   g_critReason = reason;
   Journal(key, "CRITICAL", "reason=" + reason);
  }

bool HaltFileExists() { return(FileIsExist(Dir("") + "\\halt_new", FILE_COMMON)); }

//--- approvals: the first missing one ("" = all approved) and the full list for the records
string Unapproved()
  {
   if(!APPROVED_BE_PRICE_SOURCE) return("be_price_source");
   if(!APPROVED_FILLBAR_METHOD)  return("fillbar_method");
   if(!APPROVED_TP_TIMING)       return("tp_timing");
   if(!APPROVED_TP_BEYOND)       return("tp_beyond");
   if(!APPROVED_RETRY_INTERVAL)  return("retry_interval");
   if(!APPROVED_CLOSE_DEVIATION) return("close_deviation");
   if(!APPROVED_MONITORING)      return("monitoring");
   return("");
  }

//--- age of the bridge heartbeat in ms (-1 = none / unreadable)
long BridgeHeartbeatAgeMs()
  {
   string l[];
   if(!ReadLines(Dir("") + "\\hb_bridge.txt", l))
      return(-1);
   long t = StringToInteger(KvGet(l, "t_ms"));
   if(t <= 0)
      return(-1);
   return(NowMsLate() - t);
  }

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
   else if(!g_bindOk)
      why = "journal_binding_mismatch";
   return(why == "");
  }

//--- every trade API write goes through this gate (DRY_RUN blocks all of them). A journal failure does NOT block it, so the
//--- protection of an own position stays possible; new entries are blocked separately (NewEntriesAllowed).
bool TradeWritesAllowed()
  {
   if(InpDryRun || !g_envOk || !g_bindOk || !g_ready || !IsDemoAccount())
      return(false);
   if(AccountInfoInteger(ACCOUNT_LOGIN) != InpExpectedLogin || AccountInfoString(ACCOUNT_SERVER) != InpExpectedServer)
      return(false);
   return(true);
  }

//--- `self` = the key being sent right now (its own in-flight mark does not block it)
bool NewEntriesAllowed(string &why, const string self = "")
  {
   why = "";
   string ua = Unapproved();
   long hb = BridgeHeartbeatAgeMs();
   if(InpDryRun)                   why = "dry_run";
   else if(!InpAllowNewEntries)    why = "new_entries_off";
   else if(ua != "")               why = "unapproved:" + ua;
   else if(!TradeWritesAllowed())  why = "trade_writes_not_allowed";
   else if(!g_journalOk)           why = "journal_write_failed";
   else if(g_critical)             why = "critical:" + g_critReason;
   else if(g_unknownKey != "")     why = "unknown_unresolved:" + g_unknownKey;
   else if(g_haltNew)              why = "halt_new:" + g_haltReason;
   else if(HaltFileExists())       why = "halt_file";
   else if(g_inflightKey != "" && g_inflightKey != self) why = "in_flight:" + g_inflightKey;
   else if(g_hasPos)               why = "max1_own_position";
   else if(hb < 0 || hb > BRIDGE_HB_MAX_MS) why = "bridge_heartbeat_stale";
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
   string l[];
   if(!ReadLines(file, l))
      return(false);
   c.v = KvGet(l, "v"); c.key = KvGet(l, "key"); c.khash = KvGet(l, "key_hash"); c.tid = KvGet(l, "tid"); c.ev = KvGet(l, "ev");
   c.side = KvGet(l, "side"); c.otype = KvGet(l, "otype"); c.path = KvGet(l, "path"); c.cfg = KvGet(l, "cfg_sha256");
   c.sid = KvGet(l, "sid"); c.sym = KvGet(l, "sym");
   c.px = StringToDouble(KvGet(l, "px")); c.sl = StringToDouble(KvGet(l, "sl")); c.tp = StringToDouble(KvGet(l, "tp"));
   c.barCloseMs = StringToInteger(KvGet(l, "bar_close_ms"));
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
//| final permission from the bridge (file handshake, also in DRY_RUN) |
//+------------------------------------------------------------------+
//--- "" = GO (goUntil = the GO validity, GMT ms); otherwise "nogo:<reason>". No answer within ASK_WAIT_MS = no go.
string AskBridge(const Cmd &c, const bool dry, long &goUntil)
  {
   goUntil = 0;
   string ans = Dir("ans") + "\\" + c.khash + ".ans";
   if(FileIsExist(ans, FILE_COMMON))
      FileMove(ans, FILE_COMMON, Dir("done") + "\\" + c.khash + ".stale.ans", FILE_COMMON | FILE_REWRITE);   // never used
   string body = "key_hash=" + c.khash + "\nt_ms=" + IntegerToString(NowMs()) + "\ndry_run=" + (dry ? "1" : "0") + "\n";
   if(!WriteFileAtomic(Dir("ask"), c.khash + ".ask", body, true))
      return("nogo:ask_write_failed");
   uint t0 = GetTickCount();
   while(GetTickCount() - t0 < (uint)ASK_WAIT_MS && !IsStopped())
     {
      if(FileIsExist(ans, FILE_COMMON))
        {
         string l[];
         bool rd = ReadLines(ans, l);
         FileMove(ans, FILE_COMMON, Dir("done") + "\\" + c.khash + ".ans", FILE_COMMON | FILE_REWRITE);
         if(!rd || KvGet(l, "key_hash") != c.khash)
            return("nogo:answer_unreadable");
         if(KvGet(l, "decision") != "GO")
            return("nogo:" + KvGet(l, "reason"));
         long until = StringToInteger(KvGet(l, "valid_until_ms"));
         until = MinL(until, c.barCloseMs + (long)MAX_AGE_SEC * 1000);
         if(NowMsLate() > until)
            return("nogo:go_expired_on_arrival");
         goUntil = until;
         return("");
        }
      Sleep(50);
     }
   return("nogo:no_answer");
  }

//--- the checks AFTER the PRE_SEND record (the record itself may take time): first the slow part — the request rebuilt from
//--- the current price / spread / balance (PrepareOrder incl. OrderCheck), which must keep the recorded volume and SL — and
//--- only then FinalGate, so nothing slow runs between the last check and OrderSend.
string SendCheck(const Cmd &c, const string id, const long goUntil, const MqlTradeRequest &base, MqlTradeRequest &out)
  {
   string detail;
   string why = PrepareOrder(c, out, detail);
   if(why != "")                              return(why);
   if(MathAbs(out.volume - base.volume) > 1e-9 || MathAbs(out.sl - base.sl) > 1e-9) return("request_changed");
   return(FinalGate(c, id, goUntil));
  }

//--- the last checks, immediately before OrderSend. First everything that reads files or the terminal (every new-entry gate:
//--- halt file / halt / critical / unknown / bridge heartbeat file / in-flight; account-wide positions and pending orders), and
//--- ONLY THEN the deadline and the GO validity, which read nothing but the clock: a slow file read can never let an expired
//--- ENTRY or GO through. Nothing runs between this function and OrderSend.
string FinalGate(const Cmd &c, const string id, const long goUntil)
  {
   string gate;
   if(!NewEntriesAllowed(gate, id))           return(gate);
   if(PositionsTotal() > 0)                   return("max1_position_exists");
   if(OrdersTotal() > 0)                      return("max1_pending_order_exists");
   string why = CheckDeadline(c);             // clock only, after every read
   if(why != "")                              return(why);
   if(NowMsLate() > goUntil)                  return("go_expired");
   return("");
  }

//+------------------------------------------------------------------+
//| ownership: journal record + POSITION_IDENTIFIER + symbol + magic  |
//+------------------------------------------------------------------+
//--- 1 = the own position is selected (posTicket refreshed); 0 = no open position with that identifier;
//--- -1 = the identifier is open but symbol / magic / type do not match -> quarantined, never written to
int SelectOwn()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0 || PositionGetInteger(POSITION_IDENTIFIER) != g_pos.posId)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != InpSymbol || PositionGetInteger(POSITION_MAGIC) != InpMagic ||
         PositionGetInteger(POSITION_TYPE) != POSITION_TYPE_SELL)
        {
         Quarantine("ownership_mismatch", t);
         return(-1);
        }
      if(t != g_pos.posTicket)
        {
         Journal(g_pos.key, "TICKET_CHANGED", "position_id=" + IntegerToString(g_pos.posId) + ";old=" + IntegerToString((long)g_pos.posTicket) +
                 ";new=" + IntegerToString((long)t));
         g_pos.posTicket = t;
         PositionSelectByTicket(t);
        }
      return(1);
     }
   return(0);
  }

//--- IN / OUT statistics of the position's history (identifier): false when the history cannot be read
bool FillStats(const long posId, double &vin, double &vout, int &nIn, long &lastIn)
  {
   vin = 0; vout = 0; nIn = 0; lastIn = 0;
   if(!HistorySelectByPosition(posId))
      return(false);
   for(int i = 0; i < HistoryDealsTotal(); i++)
     {
      ulong d = HistoryDealGetTicket(i);
      long e = HistoryDealGetInteger(d, DEAL_ENTRY);
      if(e == DEAL_ENTRY_IN)
        {
         vin += HistoryDealGetDouble(d, DEAL_VOLUME);
         nIn++;
         lastIn = MaxL(lastIn, HistoryDealGetInteger(d, DEAL_TIME_MSC));
        }
      else if(e == DEAL_ENTRY_OUT || e == DEAL_ENTRY_OUT_BY)
         vout += HistoryDealGetDouble(d, DEAL_VOLUME);
     }
   return(true);
  }

//--- the fill state (volume, average fill = POSITION_PRICE_OPEN, number / time of the IN deals) must be explained by the history:
//--- IN volume - OUT volume = the live volume. Until it is (the deal reaches the history after the position changed, or the history
//--- cannot be read) the state is NOT taken as synced: FILL_HISTORY_PENDING, and breakeven / fill-side checks wait. A new IN deal
//--- (fill in parts) moves the basis of the breakeven (VoidBreakevenBasis). Needs the own position selected. Never tops up.
bool RefreshFill()
  {
   double v = PositionGetDouble(POSITION_VOLUME), po = PositionGetDouble(POSITION_PRICE_OPEN);
   double vin, vout;
   int nIn;
   long lastIn;
   bool ok = FillStats(g_pos.posId, vin, vout, nIn, lastIn) && nIn > 0 && MathAbs(vin - vout - v) <= 1e-6;
   PositionSelectByTicket(g_pos.posTicket);
   if(!ok)
     {
      if(!g_pos.fillSyncPending)
        {
         g_pos.fillSyncPending = true;
         Journal(g_pos.key, "FILL_HISTORY_PENDING", "live_volume=" + DoubleToString(v, 2) + ";hist_in=" + DoubleToString(vin, 2) +
                 ";hist_out=" + DoubleToString(vout, 2) + ";in_deals=" + IntegerToString(nIn) + ";note=breakeven_and_fill_checks_wait");
        }
      return(false);
     }
   lastIn = MaxL(lastIn, g_pos.fillTimeMsc);
   bool newIn = nIn != g_pos.inDeals || lastIn != g_pos.lastInMsc;
   bool changed = newIn || MathAbs(v - g_pos.volume) > 1e-9 || MathAbs(po - g_pos.fill) > 1e-9 || g_pos.fillSyncPending;
   bool wasPending = g_pos.fillSyncPending;
   g_pos.fillSyncPending = false;
   if(!changed)
      return(true);
   string cause = v > g_pos.volume + 1e-9 ? "add" : v < g_pos.volume - 1e-9 ? "reduce" : newIn || wasPending ? "history" : "price";
   g_pos.volume = v;
   g_pos.fill = po;
   g_pos.inDeals = nIn;
   g_pos.lastInMsc = lastIn;
   Journal(g_pos.key, "POSITION_UPDATED", "cause=" + cause + ";volume=" + DoubleToString(v, 2) + ";fill_price=" + DoubleToString(po, 5) +
           ";last_in_msc=" + IntegerToString(lastIn) + ";in_deals=" + IntegerToString(nIn) + ";position_id=" + IntegerToString(g_pos.posId));
   if(newIn && !g_pos.beDone)
      VoidBreakevenBasis();
   return(true);
  }

//--- PROPOSAL (APPROVED_FILLBAR_METHOD / APPROVED_BE_PRICE_SOURCE, not approved): only prices after the LAST IN deal count. After
//--- a new IN deal a breakeven condition met before it is void (BE_TRIGGER_VOID), and the fill-bar ticks / closed bars after it are
//--- evaluated again against the new average. An SL already set is never loosened (a done breakeven is kept).
void VoidBreakevenBasis()
  {
   if(g_pos.bePending)
     {
      Journal(g_pos.key, "BE_TRIGGER_VOID", "reason=later_in_deal;fav=" + DoubleToString(g_pos.beFav, 5) + ";bar_open=" +
              IntegerToString((long)g_pos.beBar) + ";last_in_msc=" + IntegerToString(g_pos.lastInMsc) + ";fill=" + DoubleToString(g_pos.fill, 5));
      g_pos.bePending = false;
      g_pos.beFav = 0;
      g_pos.beBar = 0;
     }
   datetime fillBarOpen = BarOpenOf(g_pos.fillTimeSrv);
   datetime lastInBar = BarOpenOf((datetime)(g_pos.lastInMsc / 1000));
   g_pos.fillBarDone = false;
   g_pos.fillBarUnavailNoted = false;
   g_pos.lastBarDone = lastInBar > fillBarOpen ? lastInBar : fillBarOpen;
  }

//--- an own record that does not match the live position: not managed, nothing written to it, new entries stop
void Quarantine(const string reason, const ulong ticket)
  {
   Journal(g_pos.key, "QUARANTINE", "reason=" + reason + ";position_id=" + IntegerToString(g_pos.posId) + ";ticket=" +
           IntegerToString((long)ticket) + ";note=no_write_to_this_position");
   g_hasPos = false;
   HaltNew("quarantine:" + reason);
   SetCritical(g_pos.key, "quarantine:" + reason);
  }

//--- volumes of the position's history (identifier): in / out
bool HistoryVolumes(const long posId, double &vin, double &vout, ulong &lastOut)
  {
   vin = 0; vout = 0; lastOut = 0;
   if(!HistorySelectByPosition(posId))
      return(false);
   for(int i = 0; i < HistoryDealsTotal(); i++)
     {
      ulong d = HistoryDealGetTicket(i);
      long e = HistoryDealGetInteger(d, DEAL_ENTRY);
      if(e == DEAL_ENTRY_IN)
         vin += HistoryDealGetDouble(d, DEAL_VOLUME);
      else if(e == DEAL_ENTRY_OUT || e == DEAL_ENTRY_OUT_BY)
        {
         vout += HistoryDealGetDouble(d, DEAL_VOLUME);
         lastOut = d;
        }
     }
   return(true);
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

//--- an open position of this symbol + magic + SELL whose identifier is posId (0 = none)
ulong TicketOfIdentifier(const long posId)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t > 0 && PositionGetInteger(POSITION_IDENTIFIER) == posId && PositionGetString(POSITION_SYMBOL) == InpSymbol &&
         PositionGetInteger(POSITION_MAGIC) == InpMagic && PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_SELL)
         return(t);
     }
   return(0);
  }

//--- adopt an own position (selected) into management and record it as FILLED (the restart adopts it from this record)
void AdoptOwn(const string key, const long posId, const ulong ticket, const ulong orderTicket, const ulong dealTicket,
              const double sl0, const double tp0, const string via)
  {
   ResetPos();
   g_pos.key = key; g_pos.posId = posId; g_pos.posTicket = ticket; g_pos.orderTicket = orderTicket; g_pos.dealTicket = dealTicket;
   g_pos.fill = PositionGetDouble(POSITION_PRICE_OPEN);  // actual XS fill (average price if the fill came in parts)
   g_pos.volume = PositionGetDouble(POSITION_VOLUME);
   g_pos.sl0 = sl0; g_pos.tp0 = tp0;
   g_pos.fillTimeSrv = (datetime)PositionGetInteger(POSITION_TIME);
   g_pos.fillTimeMsc = PositionGetInteger(POSITION_TIME_MSC);
   // the position may already hold several IN deals (fill in parts before the adoption): the last IN deal comes from the history
   double vin, vout;
   int nIn;
   long lastIn;
   bool ok = FillStats(posId, vin, vout, nIn, lastIn) && nIn > 0 && MathAbs(vin - vout - g_pos.volume) <= 1e-6;
   PositionSelectByTicket(ticket);
   g_pos.inDeals = ok ? nIn : 0;
   g_pos.lastInMsc = ok ? MaxL(lastIn, g_pos.fillTimeMsc) : g_pos.fillTimeMsc;
   g_pos.fillSyncPending = !ok;
   datetime fillBarOpen = BarOpenOf(g_pos.fillTimeSrv), lastInBar = BarOpenOf((datetime)(g_pos.lastInMsc / 1000));
   g_pos.lastBarDone = lastInBar > fillBarOpen ? lastInBar : fillBarOpen;
   g_hasPos = true;
   Journal(key, "FILLED", "order=" + IntegerToString((long)orderTicket) + ";deal=" + IntegerToString((long)dealTicket) +
           ";position_id=" + IntegerToString(posId) + ";position=" + IntegerToString((long)ticket) +
           ";fill_price=" + DoubleToString(g_pos.fill, 5) + ";volume=" + DoubleToString(g_pos.volume, 2) +
           ";sl0=" + DoubleToString(sl0, 5) + ";tp0=" + DoubleToString(tp0, 5) +
           ";fill_time=" + IntegerToString((long)g_pos.fillTimeSrv) + ";fill_time_msc=" + IntegerToString(g_pos.fillTimeMsc) +
           ";in_deals=" + IntegerToString(g_pos.inDeals) + ";last_in_msc=" + IntegerToString(g_pos.lastInMsc) +
           ";fill_sync=" + (ok ? "ok" : "pending") + ";via=" + via);
  }

//--- confirm a fill from the deal -> DEAL_POSITION_ID (= POSITION_IDENTIFIER) -> the live position, never from OrderSend's bool
bool ConfirmFill(const string key, ulong orderTicket, ulong dealTicket, double sl0, double tp0)
  {
   long posId = 0;
   for(int i = 0; i < 20 && posId == 0; i++)        // the deal can reach the history a little after OrderSend returns
     {
      if(dealTicket > 0 && HistoryDealSelect(dealTicket))
         posId = HistoryDealGetInteger(dealTicket, DEAL_POSITION_ID);
      if(posId == 0)
         Sleep(100);
     }
   if(posId == 0)
      return(false);
   ulong t = TicketOfIdentifier(posId);
   if(t == 0 || !PositionSelectByTicket(t))
      return(false);
   AdoptOwn(key, posId, t, orderTicket, dealTicket, sl0, tp0, "send");
   return(true);
  }

//--- market close of the OWN position. The result is verified on the live position and its history:
//--- CLOSE_FULL (gone and the history covers the volume), CLOSE_PARTIAL (still open with less volume), CLOSE_FAILED (unchanged),
//--- CLOSE_UNKNOWN (cannot be told). A journal failure does not stop an emergency close (the Experts log keeps a trace).
int ClosePosition(const string key, const string reason, double &remaining)
  {
   remaining = -1;
   if(!TradeWritesAllowed() || !g_hasPos || SelectOwn() != 1)
      return(CLOSE_NOT_ALLOWED);
   MqlTick tk;
   if(!SymbolInfoTick(InpSymbol, tk))
      return(CLOSE_FAILED);
   double vol = PositionGetDouble(POSITION_VOLUME);
   MqlTradeRequest r;
   MqlTradeResult res;
   ZeroMemory(r);
   ZeroMemory(res);
   r.action = TRADE_ACTION_DEAL; r.symbol = InpSymbol; r.type = ORDER_TYPE_BUY; r.position = g_pos.posTicket;
   r.volume = vol; r.price = tk.ask; r.magic = (ulong)InpMagic; r.comment = "XSD:" + g_pos.key + ":C";
   r.type_filling = FillingMode(); r.deviation = (ulong)CLOSE_DEVIATION_POINTS;
   Journal(key, "CLOSE_PRE_SEND", "reason=" + reason + ";position_id=" + IntegerToString(g_pos.posId) + ";volume=" + DoubleToString(vol, 2));
   bool ok = OrderSend(r, res);
   int result = CLOSE_UNKNOWN;
   for(int i = 0; i < 20; i++)
     {
      int sel = SelectOwn();
      if(sel == 1)
        {
         remaining = PositionGetDouble(POSITION_VOLUME);
         if(remaining < vol - 1e-9) { result = CLOSE_PARTIAL; break; }
         if(!ok && IsDefiniteReject(res.retcode)) { result = CLOSE_FAILED; break; }
        }
      else if(sel == 0)
        {
         double vin, vout;
         ulong lo;
         remaining = 0;
         if(HistoryVolumes(g_pos.posId, vin, vout, lo) && vin > 0 && vout >= vin - 1e-9) { result = CLOSE_FULL; break; }
        }
      else
         break;
      Sleep(100);
     }
   string st = result == CLOSE_FULL ? "CLOSE_DONE" : result == CLOSE_PARTIAL ? "CLOSE_PARTIAL" : result == CLOSE_FAILED ? "CLOSE_FAILED" : "CLOSE_UNKNOWN";
   Journal(key, st, "reason=" + reason + ";retcode=" + IntegerToString((int)res.retcode) + ";remaining=" + DoubleToString(remaining, 2));
   return(result);
  }

//--- SL / TP change of the OWN position (ownership re-checked); never loosens a short's SL, never removes it
bool ModifyOwn(const string what, double newSl, double newTp)
  {
   if(!TradeWritesAllowed() || !g_hasPos || SelectOwn() != 1)
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

//--- the single entry path
void ProcessEntry(const Cmd &c, const string id)
  {
   if(!Journal(id, "SEEN", "tid=" + c.tid + ";bar_close_ms=" + IntegerToString(c.barCloseMs)))
      return;                                        // nothing is decided without a record
   string why = CheckCmd(c);
   if(why == "") why = CheckDeadline(c);
   string gate = "";
   bool dry = false;
   if(why == "" && !NewEntriesAllowed(gate))
     {
      if(gate == "dry_run" || gate == "new_entries_off")
         dry = true;
      else
         why = gate;                                 // skipped now, never re-tried later (a skipped signal stays skipped)
     }
   MqlTradeRequest req;
   string detail = "";
   if(why == "") why = PrepareOrder(c, req, detail);
   if(why != "")
     {
      Journal(id, "SKIPPED", "reason=" + why);
      return;
     }
   // final go / no-go from the bridge (a claim is not a permanent permission): also asked in DRY_RUN so the path can be checked
   long goUntil = 0;
   string go = AskBridge(c, dry, goUntil);
   if(dry)
     {
      string ua = Unapproved();
      Journal(id, "DRY_RUN_NOT_SENT", "gate=" + gate + ";go=" + (go == "" ? "granted" : go) + ";unapproved=" + (ua == "" ? "none" : ua) + ";" + detail);
      return;
     }
   if(go != "")
     {
      Journal(id, "SKIPPED", "reason=" + go);
      return;
     }
   if(!Journal(id, "DECIDED", detail))
      return;
   g_inflightKey = id;
   if(!Journal(id, "PRE_SEND", "volume=" + DoubleToString(req.volume, 2) + ";sl=" + DoubleToString(req.sl, 5) + ";price=" +
               DoubleToString(req.price, 5) + ";tp0=" + DoubleToString(c.tp, 5) + ";go_until_ms=" + IntegerToString(goUntil)))
     {
      g_inflightKey = "";                            // nothing was sent: no order without the PRE_SEND record
      HaltNew("journal_write_failed");
      return;
     }
   MqlTradeRequest fin;
   why = SendCheck(c, id, goUntil, req, fin);        // everything again AFTER the record; FinalGate is its last step
   if(why != "")
     {
      if(Journal(id, "SEND_ABORTED", "reason=" + why))
         g_inflightKey = "";
      else
        {
         g_inflightKey = "";                         // the record of the abort failed: keep the key unknown until resolved
         g_unknownKey = id; g_unknownPreMs = NowMs(); g_unknownSl = req.sl; g_unknownTp = c.tp;
        }
      return;
     }
   MqlTradeResult res;
   ZeroMemory(res);
   bool ok = OrderSend(fin, res);
   Journal(id, "SEND_RETURNED", "ok=" + (ok ? "1" : "0") + ";retcode=" + IntegerToString((int)res.retcode) + ";order=" +
           IntegerToString((long)res.order) + ";deal=" + IntegerToString((long)res.deal) + ";fill_price=" + DoubleToString(res.price, 5) +
           ";volume=" + DoubleToString(res.volume, 2) + ";price_sent=" + DoubleToString(fin.price, 5));
   if(res.retcode == TRADE_RETCODE_DONE || res.retcode == TRADE_RETCODE_DONE_PARTIAL)
     {
      if(ConfirmFill(id, res.order, res.deal, fin.sl, c.tp))
        {
         g_inflightKey = "";
         if(res.retcode == TRADE_RETCODE_DONE_PARTIAL)
            Journal(id, "PARTIAL_FILL", "volume=" + DoubleToString(g_pos.volume, 2) + ";requested=" + DoubleToString(fin.volume, 2));
         CheckProtection();
         return;
        }
      MarkUnknown(id, fin.sl, c.tp, "done_but_fill_not_confirmed");
      return;
     }
   if(!ok && IsDefiniteReject(res.retcode))
     {
      g_inflightKey = "";
      Journal(id, "REJECTED", "retcode=" + IntegerToString((int)res.retcode));
      return;
     }
   MarkUnknown(id, fin.sl, c.tp, "retcode_" + IntegerToString((int)res.retcode));
  }

//--- a send whose result is not known: the slot stays occupied, new entries stop, nothing is re-sent
void MarkUnknown(const string id, const double sl, const double tp, const string reason)
  {
   g_inflightKey = "";
   g_unknownKey = id; g_unknownPreMs = NowMs() - 1000; g_unknownSl = sl; g_unknownTp = tp;
   Journal(id, "UNKNOWN", "reason=" + reason);
   HaltNew("unknown_result:" + id);
  }

//--- a close of the OWN position is required (emergency: initial SL missing; bad_fill_side_mt5). Journaled once (CLOSE_REQUIRED,
//--- restored after a restart) and worked off by ProcessCloseObligation until the position's history shows it closed.
void RequireClose(const string reason)
  {
   if(g_pos.closeReason != "")
      return;
   g_pos.closeReason = reason;
   Journal(g_pos.key, "CLOSE_REQUIRED", "reason=" + reason + ";position_id=" + IntegerToString(g_pos.posId));
  }

//--- one close attempt per EMERGENCY_RETRY_SEC (proposal, not approved) while the obligation exists and the position is ours.
//--- CLOSE_FULL: confirmed (CLOSED follows from the history); partial / failed / unknown: new entries stop + CRITICAL, the
//--- remainder stays owned and is retried. The result of every attempt is handled here, whatever the reason of the close.
void ProcessCloseObligation()
  {
   if(!g_hasPos || g_pos.closeReason == "" || !TradeWritesAllowed() || SelectOwn() != 1)
      return;
   long nowS = (long)TimeGMT();
   if(g_pos.lastCloseTry > 0 && nowS - g_pos.lastCloseTry < EMERGENCY_RETRY_SEC)
      return;
   g_pos.lastCloseTry = nowS;
   string reason = g_pos.closeReason;
   bool emergency = reason == "emergency_initial_sl_missing";
   double remaining = -1;
   int r = ClosePosition(g_pos.key, reason, remaining);
   if(r == CLOSE_NOT_ALLOWED)
      return;
   if(r == CLOSE_FULL)
     {
      if(emergency)
         Journal(g_pos.key, "EMERGENCY_CLOSE", "result=closed_confirmed");
      else
         Journal(g_pos.key, "CLOSE_CONFIRMED", "result=closed_confirmed;reason=" + reason);
      return;
     }
   string kind = r == CLOSE_PARTIAL ? "partial" : r == CLOSE_FAILED ? "failed" : "unknown";
   if(r == CLOSE_PARTIAL)
     {
      if(emergency)
         Journal(g_pos.key, "EMERGENCY_CLOSE_PARTIAL", "remaining=" + DoubleToString(remaining, 2) + ";note=unprotected_remainder_retried");
      else
         Journal(g_pos.key, "CLOSE_INCOMPLETE", "remaining=" + DoubleToString(remaining, 2) + ";reason=" + reason + ";note=remainder_retried");
     }
   HaltNew("close_incomplete:" + reason);
   string cr = emergency ? "emergency_close_" + kind : "close_" + kind + ":" + reason;
   if(!g_critical || g_critReason != cr)
      SetCritical(g_pos.key, cr);
  }

//--- the own position must carry an SL that is not looser than the initial SL. Otherwise: new entries stop and a close of the
//--- OWN position is required (ProcessCloseObligation). Checked after the fill, after a restart and on every timer.
void CheckProtection()
  {
   if(!g_hasPos || SelectOwn() != 1)
      return;
   double sl = PositionGetDouble(POSITION_SL);
   double tick = SymbolInfoDouble(InpSymbol, SYMBOL_TRADE_TICK_SIZE);
   if(sl > 0 && sl <= g_pos.sl0 + tick * 0.5 + 1e-9)
     {
      if(!g_pos.protectedNoted)
        {
         g_pos.protectedNoted = true;
         Journal(g_pos.key, "PROTECTED", "sl=" + DoubleToString(sl, 5));
        }
      return;
     }
   g_pos.protectedNoted = false;
   HaltNew("initial_sl_missing");
   if(!g_pos.slMissingNoted)
     {
      g_pos.slMissingNoted = true;
      Journal(g_pos.key, "SL_MISSING", "sl_on_position=" + DoubleToString(sl, 5) + ";sl0=" + DoubleToString(g_pos.sl0, 5));
     }
   RequireClose("emergency_initial_sl_missing");
   ProcessCloseObligation();
  }

//+------------------------------------------------------------------+
//| management of the OWN position (closed M5 bars, server time)      |
//+------------------------------------------------------------------+
//--- the own position is not open: closed only when its history covers the volume; otherwise it is missing (not "closed")
void CheckClosedFromHistory()
  {
   double vin, vout;
   ulong lo;
   if(HistoryVolumes(g_pos.posId, vin, vout, lo) && vin > 0 && vout >= vin - 1e-9)
     {
      long dr = HistoryDealGetInteger(lo, DEAL_REASON);
      string reason = dr == DEAL_REASON_SL ? "sl" : dr == DEAL_REASON_TP ? "tp" : dr == DEAL_REASON_EXPERT ? "expert" :
                      dr == DEAL_REASON_CLIENT ? "manual" : "other";
      double profit = 0, comm = 0, swap = 0;
      for(int i = 0; i < HistoryDealsTotal(); i++)
        {
         ulong d = HistoryDealGetTicket(i);
         profit += HistoryDealGetDouble(d, DEAL_PROFIT);
         comm += HistoryDealGetDouble(d, DEAL_COMMISSION);
         swap += HistoryDealGetDouble(d, DEAL_SWAP);
        }
      Journal(g_pos.key, "CLOSED", "reason=" + reason + ";deal=" + IntegerToString((long)lo) + ";price=" +
              DoubleToString(HistoryDealGetDouble(lo, DEAL_PRICE), 5) + ";profit=" + DoubleToString(profit, 0) +
              ";commission=" + DoubleToString(comm, 0) + ";swap=" + DoubleToString(swap, 0) + ";position_id=" + IntegerToString(g_pos.posId));
      g_hasPos = false;
      return;
     }
   if(!g_pos.missingNoted)
     {
      g_pos.missingNoted = true;
      Journal(g_pos.key, "OWN_POSITION_MISSING", "position_id=" + IntegerToString(g_pos.posId) + ";in=" + DoubleToString(vin, 2) +
              ";out=" + DoubleToString(vout, 2) + ";note=not_treated_as_closed");
      HaltNew("own_position_missing");
     }
  }

//--- lowest Bid of the tick history strictly after the fill (the LAST IN deal when the order filled in parts) and before the
//--- fill-bar close (server ms). >0 = number of ticks, 0 = none, -1 = history not available (NOT "condition not met")
int FillBarLow(const datetime fillBarOpen, double &lo)
  {
   lo = 0;
   MqlTick ticks[];
   ulong from = (ulong)MaxL(g_pos.fillTimeMsc, g_pos.lastInMsc) + 1;
   ulong to = (ulong)((long)fillBarOpen + BAR_SEC) * 1000 - 1;
   if(to < from)
      return(0);
   int n = CopyTicksRange(InpSymbol, ticks, COPY_TICKS_INFO, from, to);
   if(n < 0)
      return(-1);
   int used = 0;
   for(int i = 0; i < n; i++)
     {
      if(ticks[i].bid <= 0 || ticks[i].time_msc < (long)from || ticks[i].time_msc > (long)to)
         continue;
      lo = used == 0 ? ticks[i].bid : MathMin(lo, ticks[i].bid);
      used++;
     }
   return(used);
  }

void ManageOwn()
  {
   if(!g_hasPos)
      return;
   int own = SelectOwn();
   if(own < 0)
      return;                                        // quarantined
   if(own == 0)
     {
      CheckClosedFromHistory();
      return;
     }
   bool fillOk = RefreshFill();                      // every timer: a deal that reaches the history late is still taken in
   if(!TradeWritesAllowed())
     {
      // DRY_RUN / environment lost: no SL-TP change of any kind (the SL already on the position stays)
      if(!g_mgmtNoted)
        {
         g_mgmtNoted = true;
         Journal(g_pos.key, "MANAGEMENT_BLOCKED", "reason=trade_writes_not_allowed;note=the_server_side_sl_stays");
        }
      return;
     }
   g_mgmtNoted = false;
   CheckProtection();
   if(!g_hasPos || SelectOwn() != 1)
      return;
   if(g_pos.closeReason != "")
     {
      ProcessCloseObligation();                      // a required close comes before any TP / breakeven change
      return;
     }
   if(!fillOk || SelectOwn() != 1)
      return;                                        // fill state not explained by the history yet: no fill-side / breakeven decision
   double tick = SymbolInfoDouble(InpSymbol, SYMBOL_TRADE_TICK_SIZE);
   double slNow = PositionGetDouble(POSITION_SL);
   if(!(slNow > 0 && slNow <= g_pos.sl0 + tick * 0.5 + 1e-9))
      return;                                        // unprotected: only the emergency handling above
   datetime now = TimeTradeServer();
   datetime fillBarOpen = BarOpenOf(g_pos.fillTimeSrv);
   if(now < fillBarOpen + BAR_SEC)
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
         RequireClose("bad_fill_side_mt5");
         ProcessCloseObligation();                   // the result (done / partial / failed / unknown) is handled there
         return;
        }
      if(SelectOwn() != 1)
         return;
      double curSl = PositionGetDouble(POSITION_SL);
      if(ModifyOwn("tp0", curSl, NormalizeDouble(g_pos.tp0, digits)))
        {
         g_pos.tpSet = true;
         Journal(g_pos.key, "TP_SET", "tp=" + DoubleToString(g_pos.tp0, digits) + ";sl_kept=" + DoubleToString(curSl, digits));
        }
     }
   RetryBreakeven(now);                              // a condition already met (also before a restart) is applied first
   if(!g_pos.fillBarDone)
     {
      // breakeven on the fill bar: only ticks strictly after the (last) fill and before the fill-bar close (never the next bar)
      if(g_pos.beDone || g_pos.bePending || InpFillBarBe != FILLBAR_TICKS_SINCE_FILL)
         g_pos.fillBarDone = true;
      else
        {
         double lo;
         int n = FillBarLow(fillBarOpen, lo);
         if(n < 0)
           {
            // history not available: NOT the same as "condition not met" -> read again on the next timers (later bars go on)
            if(!g_pos.fillBarUnavailNoted)
              {
               g_pos.fillBarUnavailNoted = true;
               Journal(g_pos.key, "FILLBAR_TICKS_UNAVAILABLE", "fill_bar_open=" + IntegerToString((long)fillBarOpen) + ";note=retried");
              }
           }
         else
           {
            if(n > 0)
               TryBreakeven(lo, fillBarOpen);
            else
               Journal(g_pos.key, "FILLBAR_NO_TICKS", "n=0");
            g_pos.fillBarDone = true;
           }
        }
     }
   if(g_pos.beDone || g_pos.bePending)
      return;
   if(g_pos.lastBarDone < fillBarOpen)
      g_pos.lastBarDone = fillBarOpen;
   // closed bars after the fill bar; a bar holding a later IN deal (fill in parts) is not used (its low may precede that deal)
   datetime lastInBar = BarOpenOf((datetime)(MaxL(g_pos.fillTimeMsc, g_pos.lastInMsc) / 1000));
   MqlRates rates[];
   datetime from = g_pos.lastBarDone + BAR_SEC;
   int n = CopyRates(InpSymbol, PERIOD_M5, from, now, rates);
   for(int i = 0; i < n && !g_pos.beDone && !g_pos.bePending; i++)
     {
      if(rates[i].time < from || rates[i].time + BAR_SEC > now)
         continue;                                   // only closed bars after the fill bar
      if(rates[i].time > lastInBar)
         TryBreakeven(rates[i].low, rates[i].time);
      g_pos.lastBarDone = rates[i].time;
     }
  }

//--- the breakeven condition (Fixed Distance from the XS fill = the live average) on a confirmed price. Once met it is final:
//--- BE_TRIGGERED is journaled BEFORE the SL change, restored after a restart, and retried until the change succeeds.
void TryBreakeven(double favLow, datetime barOpen)
  {
   if(g_pos.beDone || g_pos.bePending || favLow <= 0)
      return;                                        // a pending breakeven is retried by RetryBreakeven
   if(g_pos.fill - favLow >= BE_DIST - 1e-9)
     {
      g_pos.bePending = true;
      g_pos.beFav = favLow;
      g_pos.beBar = barOpen;
      int digits = (int)SymbolInfoInteger(InpSymbol, SYMBOL_DIGITS);
      Journal(g_pos.key, "BE_TRIGGERED", "fav=" + DoubleToString(favLow, digits) + ";bar_open=" + IntegerToString((long)barOpen) +
              ";fill=" + DoubleToString(g_pos.fill, digits) + ";dist=" + DoubleToString(g_pos.fill - favLow, digits) +
              ";last_in_msc=" + IntegerToString(g_pos.lastInMsc) + ";in_deals=" + IntegerToString(g_pos.inDeals));
      ApplyBreakeven();
     }
  }

//--- SL -> the XS fill (the live average; not TradingView's BE_MOVE price). ModifyOwn never loosens / removes the SL.
void ApplyBreakeven()
  {
   g_pos.lastBeTry = TimeTradeServer();
   int digits = (int)SymbolInfoInteger(InpSymbol, SYMBOL_DIGITS);
   if(SelectOwn() != 1)                              // fresh snapshot: the TP may have just been set
      return;
   double newSl = NormalizeDouble(g_pos.fill, digits);
   double curTp = PositionGetDouble(POSITION_TP);
   if(ModifyOwn("breakeven", newSl, curTp))
     {
      g_pos.beDone = true;
      g_pos.bePending = false;
      Journal(g_pos.key, "BE_SET", "sl=" + DoubleToString(newSl, digits) + ";bar_open=" + IntegerToString((long)g_pos.beBar) +
              ";fav=" + DoubleToString(g_pos.beFav, digits));
     }
  }

//--- a met condition whose SL change failed: once per M5 bar (retry interval: proposal, not approved); right away after a restart
void RetryBreakeven(const datetime now)
  {
   if(!g_pos.bePending || g_pos.beDone)
      return;
   if(g_pos.lastBeTry > 0 && BarOpenOf(now) <= BarOpenOf(g_pos.lastBeTry))
      return;
   ApplyBreakeven();
  }

//+------------------------------------------------------------------+
//| result unknown: history check + operator confirmation             |
//+------------------------------------------------------------------+
//--- what the account says about an unknown send: "none" (no order / deal / position with the key's tag), "open" (exactly one
//--- own position, posId / ticket set), "closed" (its history covers the volume) or "ambiguous:<why>"
string DetectUnknown(const string kh, const long preSendMs, long &posId, ulong &posTicket)
  {
   posId = 0; posTicket = 0;
   string tag = "XSD:" + kh;
   long fromSrv = preSendMs / 1000 + ServerOffsetSec() - 120;
   if(!HistorySelect((datetime)fromSrv, TimeTradeServer() + 60))
      return("ambiguous:history_unavailable");
   ulong orders[];
   for(int i = 0; i < HistoryOrdersTotal(); i++)
     {
      ulong o = HistoryOrderGetTicket(i);
      if(HistoryOrderGetString(o, ORDER_SYMBOL) == InpSymbol && HistoryOrderGetInteger(o, ORDER_MAGIC) == InpMagic &&
         HistoryOrderGetString(o, ORDER_COMMENT) == tag)
        {
         int n = ArraySize(orders);
         ArrayResize(orders, n + 1);
         orders[n] = o;
        }
     }
   long pid = 0;
   int nPid = 0;
   for(int i = 0; i < HistoryDealsTotal(); i++)
     {
      ulong d = HistoryDealGetTicket(i);
      if(HistoryDealGetString(d, DEAL_SYMBOL) != InpSymbol || HistoryDealGetInteger(d, DEAL_MAGIC) != InpMagic ||
         HistoryDealGetInteger(d, DEAL_ENTRY) != DEAL_ENTRY_IN)
         continue;
      bool mine = HistoryDealGetString(d, DEAL_COMMENT) == tag;
      for(int k = 0; k < ArraySize(orders) && !mine; k++)
         mine = (ulong)HistoryDealGetInteger(d, DEAL_ORDER) == orders[k];
      if(!mine)
         continue;
      long p = HistoryDealGetInteger(d, DEAL_POSITION_ID);
      if(p != pid)
        {
         nPid++;
         pid = p;
        }
     }
   int nPending = 0;
   for(int i = 0; i < OrdersTotal(); i++)
     {
      ulong o = OrderGetTicket(i);
      if(o > 0 && OrderGetString(ORDER_COMMENT) == tag)
         nPending++;
     }
   int nTagPos = 0;
   for(int i = 0; i < PositionsTotal(); i++)
     {
      ulong t = PositionGetTicket(i);
      if(t > 0 && PositionGetString(POSITION_COMMENT) == tag)
         nTagPos++;
     }
   if(nPending > 0)  return("ambiguous:pending_order");
   if(nPid > 1)      return("ambiguous:several_positions");
   if(nPid == 0)     return(ArraySize(orders) == 0 && nTagPos == 0 ? "none" : "ambiguous:order_or_position_without_deal");
   ulong t = TicketOfIdentifier(pid);
   if(t > 0)
     {
      posId = pid; posTicket = t;
      return("open");
     }
   for(int i = 0; i < PositionsTotal(); i++)
     {
      ulong x = PositionGetTicket(i);
      if(x > 0 && PositionGetInteger(POSITION_IDENTIFIER) == pid)
         return("ambiguous:position_not_own");        // the identifier is open but symbol / magic / type differ
     }
   double vin, vout;
   ulong lo;
   if(HistoryVolumes(pid, vin, vout, lo) && vin > 0 && vout >= vin - 1e-9)
     {
      posId = pid;
      return("closed");
     }
   return("ambiguous:history_incomplete");
  }

//--- operator file resolve_unknown ("key_hash=<16 hex>" and "confirm=none|open|closed"): accepted only when it names the
//--- unknown key AND equals what the history check finds now. "open" adopts the position (ownership + SL checked).
void CheckResolveUnknown()
  {
   string f = Dir("") + "\\resolve_unknown";
   if(!FileIsExist(f, FILE_COMMON))
      return;
   string l[];
   ReadLines(f, l);
   FileDelete(f, FILE_COMMON);
   string kh = KvGet(l, "key_hash"), confirm = KvGet(l, "confirm");
   if(g_unknownKey == "" || kh != g_unknownKey)
     {
      Journal("", "UNKNOWN_RESOLVE_REFUSED", "reason=not_the_unknown_key;given=" + kh + ";unknown=" + g_unknownKey);
      return;
     }
   long posId;
   ulong ticket;
   string detected = DetectUnknown(g_unknownKey, g_unknownPreMs, posId, ticket);
   if(StringFind(detected, "ambiguous") == 0 || confirm != detected)
     {
      Journal(g_unknownKey, "UNKNOWN_RESOLVE_REFUSED", "reason=confirm_mismatch;confirm=" + confirm + ";detected=" + detected);
      return;
     }
   string key = g_unknownKey;
   if(detected == "open")
     {
      if(!PositionSelectByTicket(ticket))
        {
         Journal(key, "UNKNOWN_RESOLVE_REFUSED", "reason=position_vanished");
         return;
        }
      AdoptOwn(key, posId, ticket, 0, 0, g_unknownSl, g_unknownTp, "unknown_resolution");
     }
   if(!Journal(key, "UNKNOWN_RESOLVED", "result=" + detected + ";position_id=" + IntegerToString(posId) +
               ";note=new_entries_stay_halted_until_resume_new"))
      return;
   g_unknownKey = "";
   if(detected == "open")
      CheckProtection();                             // SL missing -> emergency close of the now-owned position
  }

//+------------------------------------------------------------------+
//| startup reconciliation from the journal + live positions / history |
//+------------------------------------------------------------------+
void Reconcile()
  {
   string lastPre = "", unknown = "", posKey = "";
   long   preMs = 0;
   double preSl = 0, preTp = 0;
   long   posId = 0, fillMsc = 0, fillTime = 0;
   ulong  posTicket = 0;
   double sl0 = 0, tp0 = 0, fill = 0, vol = 0, beFav = 0;
   long   lastIn = 0, beBar = 0, beBasis = 0;
   int    inDeals = 0;
   string closeReq = "";
   bool   closed = false, quarantined = false, bindSeen = false, beSet = false, beTrig = false;
   string l[];
   ReadLines(g_journalPath, l);
   for(int li = 0; li < ArraySize(l); li++)
     {
      string parts[];
      if(StringSplit(l[li], '|', parts) < 4)
         continue;
      string key = parts[1], st = parts[2], f = parts[3];
      string kv[];
      StringSplit(f, ';', kv);
      AddSeen(key);
      if(st == "BIND" && !bindSeen)
        {
         bindSeen = true;                            // journal fields are sanitized ('|' -> '/'), so the sid is compared sanitized
         g_bindOk = KvGet(kv, "login") == IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)) &&
                    KvGet(kv, "server") == AccountInfoString(ACCOUNT_SERVER) && KvGet(kv, "magic") == IntegerToString(InpMagic) &&
                    KvGet(kv, "sid") == Sanitize(InpExpectedSid) && KvGet(kv, "cfg") == InpExpectedCfgSha && KvGet(kv, "symbol") == InpSymbol;
        }
      if(st == "HALT_NEW") { g_haltNew = true; g_haltReason = f; }
      if(st == "RESUME_NEW") { g_haltNew = false; g_haltReason = ""; }
      if(st == "CRITICAL") { g_critical = true; g_critReason = KvGet(kv, "reason"); }
      if(st == "CRITICAL_CLEARED") { g_critical = false; g_critReason = ""; }
      if(st == "PRE_SEND")
        {
         lastPre = key; preMs = StringToInteger(parts[0]);
         preSl = StringToDouble(KvGet(kv, "sl")); preTp = StringToDouble(KvGet(kv, "tp0"));
        }
      if((st == "REJECTED" || st == "FILLED" || st == "SEND_ABORTED" || st == "UNKNOWN_RESOLVED") && key == lastPre)
         lastPre = "";
      if(st == "UNKNOWN")
         unknown = key;
      if(st == "UNKNOWN_RESOLVED" && key == unknown)
         unknown = "";
      if(st == "FILLED")
        {
         posKey = key; closed = false; quarantined = false;
         posId = StringToInteger(KvGet(kv, "position_id")); posTicket = (ulong)StringToInteger(KvGet(kv, "position"));
         sl0 = StringToDouble(KvGet(kv, "sl0")); tp0 = StringToDouble(KvGet(kv, "tp0")); fill = StringToDouble(KvGet(kv, "fill_price"));
         fillTime = StringToInteger(KvGet(kv, "fill_time")); fillMsc = StringToInteger(KvGet(kv, "fill_time_msc"));
         vol = StringToDouble(KvGet(kv, "volume"));
         lastIn = MaxL(fillMsc, StringToInteger(KvGet(kv, "last_in_msc"))); inDeals = (int)StringToInteger(KvGet(kv, "in_deals"));
         closeReq = ""; beSet = false; beTrig = false;
        }
      if(key != posKey || posKey == "")
         continue;
      if(st == "POSITION_UPDATED")
        {
         fill = StringToDouble(KvGet(kv, "fill_price")); vol = StringToDouble(KvGet(kv, "volume"));
         lastIn = MaxL(lastIn, StringToInteger(KvGet(kv, "last_in_msc"))); inDeals = (int)StringToInteger(KvGet(kv, "in_deals"));
        }
      if(st == "CLOSE_REQUIRED") closeReq = KvGet(kv, "reason");
      if(st == "BE_TRIGGERED")
        {
         beTrig = true; beFav = StringToDouble(KvGet(kv, "fav")); beBar = StringToInteger(KvGet(kv, "bar_open"));
         beBasis = StringToInteger(KvGet(kv, "last_in_msc"));
        }
      if(st == "BE_TRIGGER_VOID") beTrig = false;
      if(st == "BE_SET") beSet = true;
      if(st == "CLOSED") closed = true;
      if(st == "QUARANTINE") quarantined = true;
     }
   if(!bindSeen)
     {
      g_bindOk = true;
      Journal("", "BIND", "login=" + IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)) + ";server=" + AccountInfoString(ACCOUNT_SERVER) +
              ";magic=" + IntegerToString(InpMagic) + ";sid=" + InpExpectedSid + ";cfg=" + InpExpectedCfgSha + ";symbol=" + InpSymbol);
     }
   else if(!g_bindOk)
      Journal("", "BIND_MISMATCH", "note=journal_of_another_account_or_strategy;all_trade_writes_refused");
   // a send whose result was never recorded / never resolved: UNKNOWN -> no re-order, history check, operator confirmation
   if(lastPre != "" && unknown == "")
     {
      unknown = lastPre;
      Journal(unknown, "UNKNOWN", "reason=pre_send_without_result_at_startup");
     }
   if(unknown != "")
     {
      g_unknownKey = unknown;
      g_unknownPreMs = preMs; g_unknownSl = preSl; g_unknownTp = preTp;
      HaltNew("unknown_result_after_restart");
      long pid;
      ulong tk;
      Journal(unknown, "UNKNOWN_CHECK", "detected=" + DetectUnknown(unknown, preMs, pid, tk) + ";note=resolve_unknown_file_needed");
     }
   if(posKey != "" && !closed && !quarantined && posId > 0)
     {
      ResetPos();
      g_pos.key = posKey; g_pos.posId = posId; g_pos.posTicket = posTicket; g_pos.sl0 = sl0; g_pos.tp0 = tp0; g_pos.fill = fill;
      g_pos.volume = vol; g_pos.fillTimeSrv = (datetime)fillTime; g_pos.fillTimeMsc = fillMsc; g_pos.lastInMsc = lastIn;
      g_pos.inDeals = inDeals;
      datetime fbo = BarOpenOf(g_pos.fillTimeSrv), lib = BarOpenOf((datetime)(lastIn / 1000));
      g_pos.lastBarDone = lib > fbo ? lib : fbo;
      if(beTrig && beBasis != lastIn)
         beTrig = false;                             // a condition met on another basis (before a later IN deal) is not restored
      g_pos.closeReason = closeReq;                  // a required close survives the restart
      g_pos.beDone = beSet;
      g_pos.bePending = beTrig && !beSet;            // a met breakeven condition survives the restart (no re-reading needed)
      g_pos.beFav = beFav; g_pos.beBar = (datetime)beBar;
      g_pos.fillBarDone = beTrig || beSet;
      g_hasPos = true;
      int sel = SelectOwn();
      if(sel == 1)
        {
         RefreshFill();                              // a deal / volume change that happened while the EA was off
         double tick = SymbolInfoDouble(InpSymbol, SYMBOL_TRADE_TICK_SIZE);
         g_pos.tpSet = PositionGetDouble(POSITION_TP) > 0;
         g_pos.beDone = g_pos.beDone || MathAbs(PositionGetDouble(POSITION_SL) - g_pos.fill) <= tick * 0.5 + 1e-9;
         if(g_pos.beDone)
            g_pos.bePending = false;
         Journal(posKey, "OWNED_AT_STARTUP", "position_id=" + IntegerToString(posId) + ";position=" + IntegerToString((long)g_pos.posTicket));
        }
      else if(sel == 0)
         CheckClosedFromHistory();                   // closed while the EA was off, or missing (never "closed" without history)
     }
  }

//--- operator files: clear_critical (after a manual check), resume_new (ordinary halts only; never an unknown result)
void CheckResume()
  {
   string fc = Dir("") + "\\clear_critical";
   if(FileIsExist(fc, FILE_COMMON))
     {
      FileDelete(fc, FILE_COMMON);
      if(g_critical)
        {
         g_critical = false;
         g_critReason = "";
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
   if(g_unknownKey != "")
     {
      Journal("", "RESUME_REFUSED", "reason=unknown_unresolved;key_hash=" + g_unknownKey + ";note=use_resolve_unknown");
      return;
     }
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

void WriteHeartbeat()
  {
   string gate;
   NewEntriesAllowed(gate);
   WriteFileAtomic(Dir(""), "hb_ea.txt", "t_ms=" + IntegerToString(NowMs()) + "\ndry_run=" + (InpDryRun ? "1" : "0") + "\nnew_gate=" +
                   (gate == "" ? "open" : gate) + "\nown_position_id=" + (g_hasPos ? IntegerToString(g_pos.posId) : "0") +
                   "\ncritical=" + (g_critical ? "1" : "0") + "\nunknown=" + g_unknownKey + "\n", true);
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   if(AccountInfoInteger(ACCOUNT_TRADE_MODE) != ACCOUNT_TRADE_MODE_DEMO)
     {
      Print("XauShortDemoEA: refused (not a demo account). No input can change this.");
      return(INIT_FAILED);
     }
   string subs[] = {"", "cmd", "rpt", "done", "ask", "ans"};
   for(int i = 0; i < ArraySize(subs); i++)
      FolderCreate(Dir(subs[i]), FILE_COMMON);
   // one instance: an exclusive handle on the lock file (released by the terminal when the EA stops / crashes)
   g_lock = FileOpen(Dir("") + "\\ea.lock", FILE_WRITE | FILE_BIN | FILE_COMMON);
   if(g_lock == INVALID_HANDLE)
     {
      Print("XauShortDemoEA: another instance holds the lock (", GetLastError(), ")");
      return(INIT_FAILED);
     }
   // the journal belongs to one account / server / magic (file name) and one Strategy (BIND line, checked in Reconcile)
   g_journalPath = Dir("") + "\\journal_" + IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)) + "_" +
                   NameSafe(AccountInfoString(ACCOUNT_SERVER)) + "_" + IntegerToString(InpMagic) + ".txt";
   string why;
   g_envOk = VerifyEnvironment(why);
   Journal("", "START", "dry_run=" + (InpDryRun ? "1" : "0") + ";new_entries=" + (InpAllowNewEntries ? "1" : "0") + ";env=" +
           (g_envOk ? "ok" : why) + ";server=" + AccountInfoString(ACCOUNT_SERVER) + ";symbol=" + InpSymbol + ";unapproved=" + Unapproved());
   Reconcile();
   g_envOk = VerifyEnvironment(why);                 // the journal binding is known now
   g_ready = true;
   EventSetMillisecondTimer((int)MathMax(100, InpTimerMs));
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
   CheckResolveUnknown();
   ManageOwn();
   PollCommands();
   WriteHeartbeat();
   string gate;
   NewEntriesAllowed(gate);
   Comment("XauShortDemoEA  DRY_RUN=", InpDryRun, "  new=", (gate == "" ? "ON" : "OFF(" + gate + ")"), "  env=", (g_envOk ? "ok" : why),
           "  own_position_id=", (g_hasPos ? IntegerToString(g_pos.posId) : "none"), "  critical=", g_critical,
           "  unknown=", (g_unknownKey == "" ? "none" : g_unknownKey));
  }

void OnTick()
  {
   // nothing: management runs on the timer; the fill-bar low comes from the tick history (CopyTicksRange)
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

/*** Campaign Ranking One-Click (個人ランキング / チームランキング) ***/
const CAMPAIGN_CONFIG = {
  sheetName: '7月営業(2026)',
  sourceSheets: ['7月営業(2026)'],

  startDate: new Date('2026-07-01T00:00:00+09:00'),
  endDate:   new Date('2026-07-20T23:59:59+09:00'),

  webhookUrl: 'https://discord.com/api/webhooks/1408433022297964614/iv-pVqT8GhhwrVOSDxISMe62DyTZWIEDPJ_CqrG_zr5iCDYNe9dPD8e8amkRcwIHBB3b',
  outputA1: 'AN1',
  topN: 5,
  timezone: 'Asia/Tokyo',

  excludeNames: ['あずな', '佐久間', 'kamiki', 'kazuki', 'ふうか', 'るる'],
  includeTNamesForTotal: ['あずな', 'kamiki', 'kazuki', 'ふうか'],

  tOnlyNames: ['おぎ'], // ←この人はT(アポ取り)だけ加点する

  // ✅ チーム分け（仮）：名前 → 所属チーム
  teams: {
    'Aチーム': ['きょうか', 'みく', 'しゅう', 'あいり'],
    'Bチーム': ['うめ', 'ましー', 'おぎ', 'あやちゃん', 'はな'],
  },
};

// ⚠️ 列を1つずつ右にずらした（名前は G列 に変更、H列は未使用）
const COL = {
  NAME: 7,   // G列（ポイントの名前）
  T:    21,  // U列（アポ取り 日時）
  V:    23,  // W列（日時） +2pt
  Z:    27,  // AA列（日時） +3pt
  RANK: 15,  // O列（ランク）
};

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Campaign')
    .addItem('ランキング生成（期間内）', 'runCampaignRanking')
    .addSeparator()
    .addItem('毎日23時に自動投稿をセット', 'setupDaily23Trigger')
    .addItem('自動投稿を停止', 'stopDailyPosting')
    .addToUi();
}

function stopDailyPosting() {
  const TARGET_HANDLERS = ['runCampaignRanking', 'setupDaily23Trigger'];
  const triggers = ScriptApp.getProjectTriggers();
  let deleted = 0;
  triggers.forEach(t => {
    const h = t.getHandlerFunction();
    if (TARGET_HANDLERS.includes(h) || t.getEventType() === ScriptApp.EventType.CLOCK) {
      ScriptApp.deleteTrigger(t);
      deleted++;
    }
  });
  try { SpreadsheetApp.getUi().alert(`自動投稿のトリガーを ${deleted} 件削除しました。`); } catch (_) {}
}

function runCampaignRanking() {
  const cfg = CAMPAIGN_CONFIG;
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const start = cfg.startDate;
  const end = cfg.endDate;

  const scoreIndividual = new Map();

  let extraTTotalFromExcluded = 0;
  let hasData = false;

  const sourceSheets = cfg.sourceSheets && cfg.sourceSheets.length
    ? cfg.sourceSheets
    : [cfg.sheetName];

  const addScore = (map, name, pts) => {
    map.set(name, (map.get(name) || 0) + pts);
  };

  sourceSheets.forEach(sheetName => {
    const sh = ss.getSheetByName(sheetName);
    if (!sh) return;

    const lastRow = sh.getLastRow();
    if (lastRow < 2) return;

    hasData = true;
    const values = sh.getRange(2, 1, lastRow - 1, sh.getLastColumn()).getValues();

    for (let i = 0; i < values.length; i++) {
      const row = values[i];
      const name = String(row[COL.NAME - 1] || '').trim();
      const rank = String(row[COL.RANK - 1] || '').trim();

      if (!name) continue;

      const rankMultiplier = (rank === 'D') ? 0.5 : 1;
      const excluded = cfg.excludeNames.includes(name);
      const tOnly = (cfg.tOnlyNames || []).includes(name);

      // --- T列（アポ取り） → ランク別ベース点 ---
      if (isValidDateInRange(row[COL.T - 1], start, end)) {
        const pts = getTBasePoint(rank) * rankMultiplier;
        if (!excluded) addScore(scoreIndividual, name, pts);
        if (cfg.includeTNamesForTotal.includes(name)) extraTTotalFromExcluded += pts;
      }

      // --- V列（日時） +2pt ---
      if (isValidDateInRange(row[COL.V - 1], start, end)) {
        if (!excluded && !tOnly) {
          addScore(scoreIndividual, name, 2 * rankMultiplier);
        }
      }

      // --- Z列（日時） +3pt ---
      if (isValidDateInRange(row[COL.Z - 1], start, end)) {
        if (!excluded && !tOnly) {
          addScore(scoreIndividual, name, 3 * rankMultiplier);
        }
      }
    }
  });

  if (!hasData) return uiSafeAlert('データがありません');

  // 個人ランキング
  const rankingIndividual = toRanking(scoreIndividual);

  // チームランキング（個人スコアをチーム単位で合算）
  const nameToTeam = buildNameToTeam(cfg.teams);
  const scoreTeam = new Map();
  scoreIndividual.forEach((pts, name) => {
    const team = nameToTeam[name];
    if (team) addScore(scoreTeam, team, pts);
  });
  const rankingTeam = toRanking(scoreTeam);

  const header = `【${fmtDate(start)}〜${fmtDate(end)} キャンペーンランキング】`;

  const body = [
    header,
    formatSection('個人ランキング', rankingIndividual, cfg.topN),
    formatSection('チームランキング', rankingTeam, null), // チームは全件表示
    '',
  ].join('\n');

  outputOrPost(body);
}

/* === Utilities === */

// Map -> [{name, pts}] を pt 降順（同点は名前昇順）で
function toRanking(map) {
  return Array.from(map.entries())
    .map(([name, pts]) => ({ name, pts }))
    .sort((a, b) => b.pts - a.pts || a.name.localeCompare(b.name, 'ja'));
}

// 名前 -> チーム名 の逆引きテーブルを作る
function buildNameToTeam(teams) {
  const table = {};
  if (!teams) return table;
  Object.keys(teams).forEach(teamName => {
    (teams[teamName] || []).forEach(name => { table[name] = teamName; });
  });
  return table;
}

// ランキング1セクションを整形。limit=null なら全件
function formatSection(title, rankingArr, limit) {
  if (!rankingArr.length) return ['', `【${title}】`, '該当データなし'].join('\n');
  const arr = (limit == null) ? rankingArr : rankingArr.slice(0, limit);
  const lines = arr.map((r, idx) => {
    const rank = idx + 1;
    const medal = rank === 1 ? '🥇' : rank === 2 ? '🥈' : rank === 3 ? '🥉' : '🏅';
    return `${medal}${rank}位 ${r.name}：${r.pts}pt`;
  });
  return ['', `【${title}】`, ...lines].join('\n');
}

function getTBasePoint(rank) {
  if (rank === 'S') return 3;
  if (rank === 'A') return 2;
  return 1;
}
function isValidDateInRange(value, start, end) {
  if (!(value instanceof Date)) return false;
  const t = value.getTime();
  return t >= start.getTime() && t <= end.getTime();
}
function fmtDate(d) {
  return Utilities.formatDate(d, CAMPAIGN_CONFIG.timezone, 'M/d');
}
function outputOrPost(text) {
  if (CAMPAIGN_CONFIG.webhookUrl && CAMPAIGN_CONFIG.webhookUrl.startsWith('http')) {
    try { postToDiscord(text); uiSafeAlert('Discordに投稿しました。'); }
    catch (e) { uiSafeAlert('Discord投稿に失敗: ' + e); }
  } else {
    outputText(text);
    uiSafeAlert(`${CAMPAIGN_CONFIG.outputA1} に書き出しました。`);
  }
}
function postToDiscord(text) {
  const payload = { content: text };
  const params = { method: 'post', contentType: 'application/json', payload: JSON.stringify(payload), muteHttpExceptions: true };
  const res = UrlFetchApp.fetch(CAMPAIGN_CONFIG.webhookUrl, params);
  if (res.getResponseCode() >= 300) throw new Error(res.getContentText());
}
function outputText(text) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sh = ss.getSheetByName(CAMPAIGN_CONFIG.sheetName) || ss.getActiveSheet();
  sh.getRange(CAMPAIGN_CONFIG.outputA1).setValue(text);
}
function uiSafeAlert(msg) {
  try { SpreadsheetApp.getUi().alert(msg); } catch (_) {}
}

function setupDaily23Trigger() {
  const handler = 'runCampaignRanking';
  ScriptApp.getProjectTriggers().forEach(t => {
    if (t.getHandlerFunction() === handler) ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger(handler)
    .timeBased()
    .atHour(23)
    .everyDays(1)
    .inTimezone(CAMPAIGN_CONFIG.timezone)
    .create();
  uiSafeAlert('毎日23:00の自動投稿トリガーを設定しました。');
}

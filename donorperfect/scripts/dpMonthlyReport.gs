function fetchMonthlyDataViaProcedures(range, config) {
  var records = callDonorPerfect({
    action: 'dp_donorsearch',
    params: {
      '@donor_id': 'null',
      '@last_name': 'null',
      '@first_name': 'null',
      '@opt_line': 'null',
      '@address': 'null',
      '@city': 'null',
      '@state': 'null',
      '@zip': 'null',
      '@country': 'null',
      '@filter_id': 'null',
      '@user_id': 'null'
    }
  }, config);
  if (!records.length) {
    return { gifts: [], donorLookup: {} };
  }
  var donorLookup = {};
  var gifts = [];
  records.forEach(function (record) {
    var donorId = record.donor_id;
    donorLookup[donorId] = {
      donor_id: donorId,
      first_gift: record.first_gift,
      donor_type: record.donor_type,
      org_rec: record.org_rec,
      leader: record.leaderField,
      first_name: record.first_name || '',
      last_name: record.last_name || ''
    };
    var dpGifts = callDonorPerfect({
      action: 'dp_gifts',
      params: {
        '@donor_id': donorId
      }
    }, config);
    dpGifts.forEach(function (gift) {
      var giftDate = parseDpDate(gift.gift_date);
      if (giftDate && giftDate >= range.start && giftDate < range.end) {
        gifts.push({
          gift_id: gift.gift_id,
          donor_id: gift.donor_id,
          amount: parseAmount(gift.amount),
          gift_date: giftDate,
          gift_type: normalizeString(gift.gift_type),
          record_type: normalizeString(gift.record_type),
          pledge_payment: normalizeString(gift.pledge_payment)
        });
      }
    });
  });
  return { gifts: gifts, donorLookup: donorLookup };
}
// set dp_api_url and dp_api_key in script properties
const scriptProperties = PropertiesService.getScriptProperties();

function getConfig() {
  const recurring = scriptProperties.getProperty('DP_RECURRING_GIFT_TYPES');
  const recordTypes = scriptProperties.getProperty('DP_INCLUDED_RECORD_TYPES');
  const config = {
    apiUrl: scriptProperties.getProperty('DP_API_URL') || '',
    apiKey: scriptProperties.getProperty('DP_API_KEY') || '',
    apiUsername: scriptProperties.getProperty('DP_API_USERNAME') || '',
    apiPassword: scriptProperties.getProperty('DP_API_PASSWORD') || '',
    reportSpreadsheetId: scriptProperties.getProperty('DP_REPORT_SPREADSHEET_ID') || '',
    reportSheetName: scriptProperties.getProperty('DP_REPORT_SHEET_NAME') || 'Monthly Summary',
    detailSheetName: scriptProperties.getProperty('DP_REPORT_DETAIL_SHEET_NAME') || 'Monthly Gifts',
    leaderField: scriptProperties.getProperty('DP_LEADER_FIELD') || '',
    recurringGiftTypes: recurring
      ? recurring.split(',').map(function (item) { return item.trim().toUpperCase(); }).filter(function (item) { return item; })
      : ['EFT', 'EFTCC', 'EFTACH', 'ACH', 'RECUR', 'MONTHLY'],
    includedRecordTypes: recordTypes
      ? recordTypes.split(',').map(function (item) { return item.trim().toUpperCase(); }).filter(function (item) { return item; })
      : ['G', 'M'],
    fallbackProceduresEnabled: String(scriptProperties.getProperty('DP_ENABLE_PROCEDURE_FALLBACK') || 'false').toLowerCase() === 'true'
  };
  if (!config.apiUrl) {
    throw new Error('set DP_API_URL in script properties');
  }
  if (!config.apiKey && !(config.apiUsername && config.apiPassword)) {
    throw new Error('set DP_API_KEY or DP_API_USERNAME and DP_API_PASSWORD in script properties');
  }
  return config;
}

function runDpMonthlyReport(options) {
  var config = getConfig();
  var targetDate = resolveTargetDate(options);
  var range = buildMonthRange(targetDate);
  var monthlyData = fetchMonthlyData(range, config);
  var gifts = monthlyData.gifts;
  var donorLookup = monthlyData.donorLookup;
  var donorIds = uniqueValues(gifts.map(function (gift) { return gift.donor_id; })).filter(function (id) { return id; });
  if (!donorLookup) {
    donorLookup = fetchDonorsByIds(donorIds, config);
  }
  var metrics = computeMetrics(range, gifts, donorLookup, config);
  writeMetrics(range, metrics, gifts, donorLookup, config);
  console.log('dp monthly report', metrics);
  return metrics;
}

function fetchMonthlyData(range, config) {
  var gifts = fetchMonthlyGifts(range, config);
  if (gifts.length) {
    return { gifts: gifts, donorLookup: null };
  }
  return fetchMonthlyDataViaProcedures(range, config);
}

function fetchMonthlyDataViaProcedures(range, config) {
  var donors = fetchAllDonors(config);
  if (!donors.length) {
    return { gifts: [], donorLookup: {} };
  }
  var donorLookup = {};
  var gifts = [];
  donors.forEach(function (donor) {
    var donorId = donor.donor_id;
    if (!donorId) {
      return;
    }
    var donorInfo = {
      donor_id: donorId,
      donor_type: donor.donor_type || '',
      org_rec: donor.org_rec || ''
    };
    if (donor.first_gift) {
      donorInfo.first_gift = donor.first_gift;
    }
    if (config.leaderField) {
      donorInfo[config.leaderField] = donor[config.leaderField] || '';
    }
    var donorGifts = callDonorPerfectProcedure('dp_gifts', { '@donor_id': Number(donorId) }, config);
    if (!donorGifts.length) {
      donorLookup[donorId] = donorInfo;
      return;
    }
    var earliestGiftDate = donorInfo.first_gift ? parseDpDate(donorInfo.first_gift) : null;
    donorGifts.forEach(function (gift) {
      if (!donorInfo.first_name && gift.first_name) {
        donorInfo.first_name = gift.first_name;
      }
      if (!donorInfo.last_name && gift.last_name) {
        donorInfo.last_name = gift.last_name;
      }
      var giftDate = parseDpDate(gift.gift_date || gift.gift_date2 || '');
      if (giftDate && giftDate >= range.start && giftDate < range.end) {
        gifts.push({
          gift_id: gift.gift_id,
          donor_id: gift.donor_id,
          amount: parseAmount(gift.amount),
          gift_date: giftDate,
          gift_type: normalizeString(gift.gift_type),
          record_type: normalizeString(gift.record_type),
          pledge_payment: normalizeString(gift.pledge_payment),
          solicit_code: gift.solicit_code || '',
          reference: gift.reference || ''
        });
      }
      if (!earliestGiftDate || (giftDate && giftDate < earliestGiftDate)) {
        earliestGiftDate = giftDate;
      }
    });
    if (earliestGiftDate) {
      donorInfo.first_gift = formatDateForSql(earliestGiftDate);
    }
    donorLookup[donorId] = donorInfo;
  });
  return { gifts: gifts, donorLookup: donorLookup };
}

function fetchAllDonors(config) {
  var donors = [];
  var seen = {};
  var lastDonorId = 0;
  while (true) {
    var selectColumns = 'donor_id, donor_type, org_rec, first_gift';
    if (config.leaderField) {
      selectColumns += ', ' + config.leaderField;
    }
    var sql = 'SELECT TOP 500 ' + selectColumns + ' FROM dp WHERE donor_id > ' + lastDonorId + ' ORDER BY donor_id';
    var batch = callDonorPerfect(sql, config);
    if (!batch.length) {
      break;
    }
    batch.forEach(function (record) {
      var donorId = record.donor_id;
      if (!donorId || seen[donorId]) {
        return;
      }
      seen[donorId] = true;
      var donor = {
        donor_id: donorId,
        donor_type: record.donor_type,
        org_rec: record.org_rec,
        first_gift: record.first_gift
      };
      if (config.leaderField) {
        donor[config.leaderField] = record[config.leaderField];
      }
      donors.push(donor);
    });
    var lastRecord = batch[batch.length - 1];
    lastDonorId = Math.max(lastDonorId, Number(lastRecord.donor_id || lastDonorId));
    if (batch.length < 500) {
      break;
    }
  }
  if (donors.length) {
    return donors;
  }
  return fetchAllDonorsViaProcedure(config);
}

function fetchAllDonorsViaProcedure(config) {
  var donors = [];
  var seen = {};
  var prefixes = [];
  for (var code = 48; code <= 57; code++) { // 0-9
    prefixes.push(String.fromCharCode(code) + '%');
  }
  for (var letter = 65; letter <= 90; letter++) { // A-Z
    prefixes.push(String.fromCharCode(letter) + '%');
  }
  prefixes.push(null);
  prefixes.forEach(function (prefix) {
    var params = buildDonorSearchParams(prefix);
    var batch = callDonorPerfectProcedure('dp_donorsearch', params, config);
    batch.forEach(function (record) {
      var donorId = record.donor_id;
      if (!donorId || seen[donorId]) {
        return;
      }
      seen[donorId] = true;
      var donor = {
        donor_id: donorId,
        donor_type: record.donor_type,
        org_rec: record.org_rec,
        first_gift: record.first_gift
      };
      if (config.leaderField) {
        donor[config.leaderField] = record[config.leaderField];
      }
      donors.push(donor);
    });
  });
  return donors;
}

function buildDonorSearchParams(prefix) {
  return {
    '@donor_id': null,
    '@last_name': prefix,
    '@first_name': null,
    '@opt_line': null,
    '@address': null,
    '@city': null,
    '@state': null,
    '@zip': null,
    '@country': null,
    '@filter_id': null,
    '@user_id': null
  };
}

function resolveTargetDate(options) {
  if (options && options.referenceDate) {
    var parsed = new Date(options.referenceDate);
    if (!isNaN(parsed.getTime())) {
      return parsed;
    }
  }
  return new Date();
}

function buildMonthRange(date) {
  var start = new Date(date.getFullYear(), date.getMonth(), 1);
  var end = new Date(date.getFullYear(), date.getMonth() + 1, 1);
  return {
    start: start,
    end: end,
    startSql: formatDateForSql(start),
    endSql: formatDateForSql(end)
  };
}

function formatDateForSql(date) {
  return Utilities.formatDate(date, Session.getScriptTimeZone(), 'MM/dd/yyyy');
}

function fetchMonthlyGifts(range, config) {
  if (!range || !range.start || !range.startSql || !range.end || !range.endSql) {
    throw new Error('fetchMonthlyGifts expected a range object from buildMonthRange');
  }
  var gifts = [];
  var lastGiftId = 0;
  while (true) {
    var sql = 'SELECT TOP 500 gift_id, donor_id, amount, gift_date, gift_type, record_type, split_gift, pledge_payment, reference, solicit_code, first_name, last_name '
      + 'FROM dpgift '
      + "WHERE gift_date >= '" + range.startSql + "' "
      + "AND gift_date < '" + range.endSql + "' "
      + 'AND gift_id > ' + lastGiftId + ' '
      + 'ORDER BY gift_id';
    var batch = callDonorPerfect(sql, config);
    if (!batch.length) {
      break;
    }
    batch.forEach(function (record) {
      var giftId = Number(record.gift_id || 0);
      if (giftId > lastGiftId) {
        lastGiftId = giftId;
      }
      gifts.push({
        gift_id: giftId,
        donor_id: record.donor_id,
        amount: parseAmount(record.amount),
        gift_date: parseDpDate(record.gift_date || record.gift_date2 || ''),
        gift_type: normalizeString(record.gift_type),
        record_type: normalizeString(record.record_type),
        pledge_payment: normalizeString(record.pledge_payment),
        solicit_code: record.solicit_code || '',
        reference: record.reference || '',
        first_name: record.first_name || '',
        last_name: record.last_name || ''
      });
    });
    if (batch.length < 500) {
      break;
    }
  }
  return gifts;
}

function fetchDonorsByIds(ids, config) {
  if (!ids.length) {
    return {};
  }
  var lookup = {};
  var columns = ['donor_id', 'first_gift', 'donor_type', 'org_rec'];
  if (config.leaderField) {
    columns.push(config.leaderField);
  }
  chunkArray(ids, 90).forEach(function (chunk) {
    var sql = 'SELECT ' + columns.join(', ') + ' FROM dp WHERE donor_id IN (' + chunk.map(function (id) { return Number(id); }).join(',') + ')';
    var records = callDonorPerfect(sql, config);
    records.forEach(function (record) {
      lookup[record.donor_id] = record;
    });
  });
  return lookup;
}

function computeMetrics(range, gifts, donorLookup, config) {
  var filteredGifts = gifts.filter(function (gift) {
    if (!gift.gift_date) {
      return false;
    }
    if (config.includedRecordTypes.indexOf(gift.record_type) === -1) {
      return false;
    }
    return gift.gift_date >= range.start && gift.gift_date < range.end;
  });
  var donorIds = uniqueValues(filteredGifts.map(function (gift) { return gift.donor_id; })).filter(function (id) { return id; });
  var donationTotal = filteredGifts.reduce(function (sum, gift) { return sum + gift.amount; }, 0);
  var recurringDonorIds = new Set();
  var recurringTypeSet = new Set(config.recurringGiftTypes);
  var recurringAmount = 0;
  filteredGifts.forEach(function (gift) {
    var isRecurringGift = gift.pledge_payment === 'Y' || recurringTypeSet.has(gift.gift_type);
    if (isRecurringGift) {
      recurringDonorIds.add(gift.donor_id);
      recurringAmount += gift.amount;
    }
  });
  var amounts = filteredGifts.map(function (gift) { return gift.amount; }).sort(function (a, b) { return a - b; });
  var giftCount = filteredGifts.length;
  var averageGift = giftCount ? donationTotal / giftCount : 0;
  var medianGift = giftCount ? (giftCount % 2 === 1 ? amounts[(giftCount - 1) / 2] : (amounts[giftCount / 2 - 1] + amounts[giftCount / 2]) / 2) : 0;
  var largestGift = giftCount ? amounts[amounts.length - 1] : 0;
  var oneTimeAmount = donationTotal - recurringAmount;
  var newDonorIds = new Set();
  var matchedCompanyIds = new Set();
  var runningLeaderIds = new Set();
  donorIds.forEach(function (donorId) {
    var donor = donorLookup[donorId];
    if (!donor) {
      return;
    }
    var firstGiftDate = parseDpDate(donor.first_gift);
    if (firstGiftDate && firstGiftDate >= range.start && firstGiftDate < range.end) {
      newDonorIds.add(donorId);
    }
    if (String(donor.donor_type || '').toUpperCase() === 'CO' || String(donor.org_rec || '').toUpperCase() === 'Y') {
      matchedCompanyIds.add(donorId);
    }
    if (config.leaderField) {
      var raw = String(donor[config.leaderField] || '').trim().toUpperCase();
      if (raw === 'Y' || raw === 'YES' || raw === 'TRUE' || raw === '1') {
        runningLeaderIds.add(donorId);
      }
    }
  });
  return {
    donorCount: donorIds.length,
    donationTotal: Number(donationTotal.toFixed(2)),
    recurringDonorCount: recurringDonorIds.size,
    newDonorCount: newDonorIds.size,
    runningLeader: runningLeaderIds.size > 0 ? 'Y' : 'N',
    runningLeaderCount: runningLeaderIds.size,
    matchedCompanyCount: matchedCompanyIds.size,
    averageGift: Number(averageGift.toFixed(2)),
    medianGift: Number(medianGift.toFixed(2)),
    largestGift: Number(largestGift.toFixed(2)),
    recurringAmount: Number(recurringAmount.toFixed(2)),
    oneTimeAmount: Number(oneTimeAmount.toFixed(2)),
    giftCount: giftCount
  };
}

function resolveDetailSheet(spreadsheet, config) {
  var sheet = spreadsheet.getSheetByName(config.detailSheetName);
  if (!sheet) {
    sheet = spreadsheet.insertSheet(config.detailSheetName);
  }
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(['Month', 'Gift Date', 'Amount', 'Donor', 'Recurring', 'New Donor', 'Running Leader', 'Company Donor', 'Record Type', 'Gift Type', 'Pledge Payment', 'Solicit Code', 'Reference']);
  }
  return sheet;
}

function writeMetrics(range, metrics, gifts, donorLookup, config) {
  var spreadsheet = config.reportSpreadsheetId
    ? SpreadsheetApp.openById(config.reportSpreadsheetId)
    : SpreadsheetApp.getActiveSpreadsheet();
  if (!spreadsheet) {
    throw new Error('unable to resolve spreadsheet destination');
  }
  var summarySheet = resolveSummarySheet(spreadsheet, config);
  writeSummaryRow(summarySheet, range, metrics);
  var detailSheet = resolveDetailSheet(spreadsheet, config);
  writeDetailRows(detailSheet, range, gifts, donorLookup, config);
}

function resolveSummarySheet(spreadsheet, config) {
  var sheet = spreadsheet.getSheetByName(config.reportSheetName);
  if (!sheet) {
    sheet = spreadsheet.insertSheet(config.reportSheetName);
  }
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(['Month', 'Unique Donors', 'Recurring Donors', 'New Donors', 'Donation Total', 'Running Leader Y/N', 'Donor Matched (Company)', 'Average Gift', 'Median Gift', 'Largest Gift', 'Recurring Amount', 'One-time Amount', 'Gift Count', 'Running Leader Donors']);
  }
  return sheet;
}

function writeSummaryRow(sheet, range, metrics) {
  var tz = Session.getScriptTimeZone();
  var monthLabel = Utilities.formatDate(range.start, tz, 'yyyy-MM');
  sheet.appendRow([
    monthLabel,
    metrics.donorCount,
    metrics.recurringDonorCount,
    metrics.newDonorCount,
    metrics.donationTotal,
    metrics.runningLeader,
    metrics.matchedCompanyCount,
    metrics.averageGift,
    metrics.medianGift,
    metrics.largestGift,
    metrics.recurringAmount,
    metrics.oneTimeAmount,
    metrics.giftCount,
    metrics.runningLeaderCount
  ]);
}

function writeDetailRows(sheet, range, gifts, donorLookup, config) {
  var monthLabel = Utilities.formatDate(range.start, Session.getScriptTimeZone(), 'yyyy-MM');
  var dataRange = sheet.getDataRange();
  var values = dataRange.getValues();
  var header = values.length ? values[0] : ['Month', 'Gift Date', 'Amount', 'Donor', 'Recurring', 'New Donor', 'Running Leader', 'Company Donor', 'Record Type', 'Gift Type', 'Pledge Payment', 'Solicit Code', 'Reference'];
  var headerLength = header.length;
  var keepRows = [];
  for (var i = 1; i < values.length; i++) {
    if (values[i][0] !== monthLabel) {
      var row = values[i];
      while (row.length < headerLength) {
        row.push('');
      }
      keepRows.push(row.slice(0, headerLength));
    }
  }
  if (!gifts.length) {
    sheet.clearContents();
    sheet.getRange(1, 1, keepRows.length + 1, headerLength).setValues([header].concat(keepRows));
    return;
  }

  var rows = gifts.map(function (gift) {
    var donor = donorLookup[gift.donor_id] || {};
    var fullName = '';
    if (donor.first_name || donor.last_name) {
      fullName = (donor.first_name || '') + ' ' + (donor.last_name || '');
      fullName = fullName.trim().replace(/\s+/g, ' ');
    }
    var donorLabel = fullName ? fullName + ' [' + gift.donor_id + ']' : String(gift.donor_id);
    var isRecurring = gift.pledge_payment === 'Y' || (gift.gift_type && gift.gift_type.indexOf('REC') !== -1);
    var firstGiftDate = donor.first_gift ? parseDpDate(donor.first_gift) : null;
    var isNew = firstGiftDate && firstGiftDate >= range.start && firstGiftDate < range.end;
    var isLeader = false;
    if (config.leaderField && donor[config.leaderField]) {
      var flag = String(donor[config.leaderField]).trim().toUpperCase();
      isLeader = (flag === 'Y' || flag === 'YES' || flag === 'TRUE' || flag === '1');
    }
    var isCompany = String(donor.donor_type || '').toUpperCase() === 'CO' || String(donor.org_rec || '').toUpperCase() === 'Y';
    return [
      monthLabel,
      Utilities.formatDate(gift.gift_date, Session.getScriptTimeZone(), 'yyyy-MM-dd'),
      gift.amount,
      donorLabel,
      isRecurring ? 'Y' : 'N',
      isNew ? 'Y' : 'N',
      isLeader ? 'Y' : 'N',
      isCompany ? 'Y' : 'N',
      gift.record_type,
      gift.gift_type,
      gift.pledge_payment,
      gift.solicit_code,
      gift.reference
    ];
  });

  var combined = [header].concat(keepRows, rows);
  sheet.clearContents();
  sheet.getRange(1, 1, combined.length, headerLength).setValues(combined);
}

function scheduleMonthlyTrigger(dayOfMonth, hour) {
  var targetDay = dayOfMonth || 1;
  var targetHour = hour || 6;
  var existing = ScriptApp.getProjectTriggers().filter(function (trigger) {
    return trigger.getHandlerFunction() === 'runDpMonthlyReport';
  });
  if (existing.length) {
    return existing[0];
  }
  return ScriptApp.newTrigger('runDpMonthlyReport').timeBased().onMonthDay(targetDay).atHour(targetHour).create();
}

function callDonorPerfect(request, config) {
  var action;
  var paramsSegment = '';
  if (typeof request === 'string') {
    action = request;
  } else if (request && typeof request === 'object') {
    action = request.action;
    if (!action) {
      throw new Error('callDonorPerfect requires an action string');
    }
    var params = buildParamsValue(request.params);
    if (params) {
      paramsSegment = '&params=' + encodeURIComponent(params);
    }
  } else {
    throw new Error('unsupported request type passed to callDonorPerfect');
  }
  var apiKey = config.apiKey;
  if (/%[0-9A-Fa-f]{2}/.test(apiKey)) {
    try {
      apiKey = decodeURIComponent(apiKey);
    } catch (err) {
      // keep original if decoding fails
    }
  }
  var url = config.apiUrl + '?apikey=' + encodeURIComponent(apiKey) + '&action=' + encodeURIComponent(action) + paramsSegment;
  var response = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
  var status = response.getResponseCode();
  var body = response.getContentText();
  if (status !== 200) {
    throw new Error('donorperfect request failed: ' + status + ' ' + body);
  }
  var records = parseRecords(body);
  return records;
}

function verifyDynamicQueryAccess(config) {
  var probe = callDonorPerfect('SELECT TOP 1 gift_id FROM dpgift ORDER BY gift_id', config);
  if (!probe.length) {
    throw new Error('no results returned from dpgift via dynamic SELECT. ask donorperfect support to enable Dynamic Query access for this API user, or expose an alternate data feed for gifts.');
  }
}

function callDonorPerfectProcedure(action, params, config) {
  return callDonorPerfect({ action: action, params: params }, config);
}

function buildParamsValue(params) {
  if (!params) {
    return '';
  }
  if (typeof params === 'string') {
    return params;
  }
  if (Array.isArray(params)) {
    return params.map(formatParamValue).join(',');
  }
  var segments = [];
  Object.keys(params || {}).forEach(function (key) {
    var value = params[key];
    segments.push(key + '=' + formatParamValue(value));
  });
  return segments.join(',');
}

function formatParamValue(value) {
  if (value === null || value === undefined) {
    return 'null';
  }
  if (value instanceof Date) {
    return "'" + formatDateForSql(value) + "'";
  }
  var type = typeof value;
  if (type === 'number' || type === 'boolean') {
    return String(value);
  }
  var stringValue = String(value);
  var lower = stringValue.trim().toLowerCase();
  if (lower === 'null') {
    return 'null';
  }
  if (/^-?\d+(\.\d+)?$/.test(stringValue.trim())) {
    return stringValue.trim();
  }
  var escaped = stringValue.replace(/'/g, "''");
  return "'" + escaped + "'";
}

function parseRecords(xmlText) {
  if (!xmlText || !xmlText.trim()) {
    return [];
  }
  var document = XmlService.parse(xmlText);
  var root = document.getRootElement();
  var name = root.getName().toLowerCase();
  if (name === 'error') {
    throw new Error(root.getText());
  }
  if (name !== 'result') {
    return [];
  }
  var records = [];
  root.getChildren('record').forEach(function (recordNode) {
    var record = {};
    recordNode.getChildren('field').forEach(function (fieldNode) {
      var fieldNameAttr = fieldNode.getAttribute('name');
      var fieldValueAttr = fieldNode.getAttribute('value');
      if (fieldNameAttr) {
        record[fieldNameAttr.getValue()] = fieldValueAttr ? fieldValueAttr.getValue() : fieldNode.getText();
      }
    });
    records.push(record);
  });
  return records;
}

function uniqueValues(values) {
  return Array.from(new Set(values));
}

function chunkArray(items, size) {
  var chunks = [];
  for (var i = 0; i < items.length; i += size) {
    chunks.push(items.slice(i, i + size));
  }
  return chunks;
}

function parseAmount(value) {
  var amount = parseFloat(String(value || '0').replace(/[^0-9.-]/g, ''));
  return isNaN(amount) ? 0 : amount;
}

function normalizeString(value) {
  return String(value || '').trim().toUpperCase();
}

function parseDpDate(value) {
  if (!value) {
    return null;
  }
  var cleaned = String(value).trim();
  var tokens = cleaned.split(' ');
  var datePart = tokens[0];
  var parts = datePart.split(/[/-]/);
  if (parts.length === 3) {
    var month = Number(parts[0]);
    var day = Number(parts[1]);
    var year = Number(parts[2]);
    if (!isNaN(year) && !isNaN(month) && !isNaN(day)) {
      return new Date(year, month - 1, day);
    }
  }
  var fallback = new Date(cleaned);
  return isNaN(fallback.getTime()) ? null : fallback;
}


function debugMostRecentGifts() {
    var config = getConfig();
    var records = callDonorPerfect(
      'SELECT TOP 5 gift_id, donor_id, amount, gift_date, record_type FROM dpgift ORDER BY gift_date DESC',
      config
    );
    Logger.log(records);
  }
  
   function debugDonorSearch() {
       var config = getConfig();
       var result = callDonorPerfect({
         action: 'dp_donorsearch',
         params: {
           '@donor_id': 'null',
           '@last_name': 'null',
           '@first_name': 'null',
           '@opt_line': 'null',
           '@address': 'null',
           '@city': 'null',
           '@state': 'null',
           '@zip': 'null',
           '@country': 'null',
           '@filter_id': 'null',
           '@user_id': 'null'
         }
       }, config);
       Logger.log(result);
     }

function debugPreviousMonthData() {
  var config = getConfig();
  var today = new Date();
  var reference = new Date(today.getFullYear(), today.getMonth() - 1, 1);
  var range = buildMonthRange(reference);
  var data = fetchMonthlyData(range, config);
  Logger.log({
    label: 'previous month range',
    startSql: range.startSql,
    endSql: range.endSql,
    giftCount: data.gifts.length,
    donorCount: Object.keys(data.donorLookup || {}).length
  });
  var sampleGifts = data.gifts.slice(0, 5).map(function (gift) {
    return {
      gift_id: gift.gift_id,
      donor_id: gift.donor_id,
      amount: gift.amount,
      gift_date: gift.gift_date ? Utilities.formatDate(gift.gift_date, Session.getScriptTimeZone(), 'yyyy-MM-dd') : null,
      record_type: gift.record_type,
      gift_type: gift.gift_type
    };
  });
  Logger.log({ label: 'sample gifts', sampleGifts: sampleGifts });
}

function debugGiftsForDonor(donorId) {
  var config = getConfig();
  var id = Number(donorId);
  if (!id) {
    throw new Error('provide a numeric donorId');
  }
  Logger.log({ label: 'debug config', apiUrl: config.apiUrl, apiKeyPreview: config.apiKey ? config.apiKey.slice(0, 6) : 'missing' });
  var gifts = callDonorPerfectProcedure('dp_gifts', { '@donor_id': id }, config);
  Logger.log({
    donorId: id,
    giftCount: gifts.length,
    gifts: gifts
  });
}


function fetchRunningLeaders(token) {
  var baseUrl = (typeof scriptProperties !== 'undefined' && scriptProperties.getProperty('COURSEMAP_API_URL'))
    || 'https://api.studentsrunphilly.org/api/v2';
  var resolvedToken = token
    || (typeof scriptProperties !== 'undefined' && scriptProperties.getProperty('COURSEMAP_API_TOKEN'))
    || '';

  if (!resolvedToken) {
    throw new Error('set COURSEMAP_API_TOKEN in script properties or pass token to fetchRunningLeaders(token)');
  }

  var url = baseUrl + '/users/get-leaders';
  var options = {
    method: 'get',
    headers: {
      'Authorization': 'Bearer ' + resolvedToken,
      'Accept': 'application/json'
    },
    muteHttpExceptions: true
  };

  var response = UrlFetchApp.fetch(url, options);
  var status = response.getResponseCode();
  var body = response.getContentText();
  if (status < 200 || status >= 300) {
    throw new Error('coursemap get-leaders failed: ' + status + ' ' + body, url, options);
  }

  var parsed = JSON.parse(body || '{}');
  var items = Array.isArray(parsed.data) ? parsed.data
    : (parsed && parsed.data && Array.isArray(parsed.data.items)) ? parsed.data.items
    : [];

  return items.map(function (leader) {
    var fullName = ((leader.first_name || '') + ' ' + (leader.last_name || '')).trim().replace(/\s+/g, ' ');
    var isActive = (typeof leader.is_active === 'boolean')
      ? leader.is_active
      : (leader.status ? String(leader.status).toLowerCase() === 'active'
        : (typeof leader.active === 'boolean' ? leader.active : false));
    return [leader.id, fullName, isActive ? 'active' : 'inactive'];
  });
}

function fetchRunningLeadersByTeam(token) {
  var baseUrl = (typeof scriptProperties !== 'undefined' && scriptProperties.getProperty('COURSEMAP_API_URL'))
    || 'https://api.studentsrunphilly.org/api/v2';
  var resolvedToken = token
    || (typeof scriptProperties !== 'undefined' && scriptProperties.getProperty('COURSEMAP_API_TOKEN'))
    || '';

  if (!resolvedToken) {
    throw new Error('set COURSEMAP_API_TOKEN in script properties or pass token to fetchRunningLeadersByTeam(token)');
  }

  var headers = {
    'Authorization': 'Bearer ' + resolvedToken,
    'Accept': 'application/json'
  };

  var teamsUrl = baseUrl + '/teams/all';
  var teamsResp = UrlFetchApp.fetch(teamsUrl, { method: 'get', headers: headers, muteHttpExceptions: true });
  var teamsStatus = teamsResp.getResponseCode();
  var teamsBody = teamsResp.getContentText();
  if (teamsStatus < 200 || teamsStatus >= 300) {
    throw new Error('coursemap teams/all failed: ' + teamsStatus + ' ' + teamsBody);
  }
  var teamsParsed = JSON.parse(teamsBody || '{}');
  var teams = Array.isArray(teamsParsed.data) ? teamsParsed.data : [];

  var rows = [];
  teams.forEach(function (team) {
    var teamId = team && (team.id || team.team_id);
    if (!teamId) {
      return;
    }
    var teamName = (team.name || team.team_name || team.title || '').toString();
    var detailUrl = baseUrl + '/teams/get-details/' + encodeURIComponent(teamId);
    var detailResp = UrlFetchApp.fetch(detailUrl, { method: 'get', headers: headers, muteHttpExceptions: true });
    var detailStatus = detailResp.getResponseCode();
    if (detailStatus < 200 || detailStatus >= 300) {
      return;
    }
    var detailBody = detailResp.getContentText();
    var detail = JSON.parse(detailBody || '{}');
    var data = detail && detail.data ? detail.data : detail; 

    var leaderCandidates = [];
    if (data && Array.isArray(data.leaders)) {
      leaderCandidates = data.leaders;
    } else if (data && Array.isArray(data.team_leaders)) {
      leaderCandidates = data.team_leaders;
    } else if (data && Array.isArray(data.users)) {
      leaderCandidates = data.users.filter(function (u) {
        var role = (u.role && (u.role.name || u.role)) || u.role_name || u.roleKey || u.role_key || '';
        var roleStr = String(role || '').toLowerCase();
        return roleStr === 'leader' || roleStr === 'team_leader' || roleStr === 'coach';
      });
    } else if (data && Array.isArray(data.members)) {
      leaderCandidates = data.members.filter(function (m) {
        var role = (m.role && (m.role.name || m.role)) || m.role_name || m.roleKey || m.role_key || '';
        return String(role || '').toLowerCase() === 'leader';
      });
    }

    leaderCandidates.forEach(function (leader) {
      var leaderId = leader.id || leader.user_id;
      if (!leaderId) {
        return;
      }
      var fullName = ((leader.first_name || '') + ' ' + (leader.last_name || '')).trim().replace(/\s+/g, ' ');
      if (!fullName && leader.name) {
        fullName = String(leader.name).trim();
      }
      var isActive = (typeof leader.is_active === 'boolean')
        ? leader.is_active
        : (leader.status ? String(leader.status).toLowerCase() === 'active'
          : (typeof leader.active === 'boolean' ? leader.active : false));
      rows.push([teamId, teamName, leaderId, fullName, isActive ? 'active' : 'inactive']);
    });
  });

  return rows;
}

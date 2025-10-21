// venmo import into donorperfect

function getVenmoConfig() {
  var fund = scriptProperties.getProperty('DP_VENMO_FUND') || 'GENERAL';
  var campaign = scriptProperties.getProperty('DP_VENMO_CAMPAIGN') || 'ANNUAL';
  var solicitation = scriptProperties.getProperty('DP_VENMO_SOLICITATION') || 'OUTRIGHT DONATIONS';
  var glCode = scriptProperties.getProperty('DP_VENMO_GL_CODE') || 'GENERAL';
  var fileMatch = scriptProperties.getProperty('VENMO_FILE_MATCH') || 'VenmoStatement_MONTH_2025';
  return { folderId: scriptProperties.getProperty('VENMO_FOLDER_ID') || '', fund: fund, campaign: campaign, solicitation: solicitation, glCode: glCode, fileMatch: fileMatch };
}

function findLatestXlsxInFolder(folderId) {
  if (!folderId) throw new Error('set VENMO_FOLDER_ID in script properties');
  Logger.log({ label: 'findLatestXlsxInFolder:start', folderIdPreview: folderId ? String(folderId).slice(0, 6) : 'missing' });
  var folder = DriveApp.getFolderById(folderId);
  var files = folder.getFiles();
  var latest = null;
  while (files.hasNext()) {
    var f = files.next();
    var mime = f.getMimeType();
    if (mime === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet') {
      if (!latest || f.getLastUpdated().getTime() > latest.getLastUpdated().getTime()) {
        latest = f;
      }
    }
  }
  var resultId = latest ? latest.getId() : null;
  Logger.log({ label: 'findLatestXlsxInFolder:done', found: !!resultId, resultIdPreview: resultId ? resultId.slice(0, 6) : '' });
  return resultId;
}

function ensureGoogleSheetCopy(fileId) {
  Logger.log({ label: 'ensureGoogleSheetCopy:start', fileIdPreview: fileId ? String(fileId).slice(0, 6) : 'missing' });
  var file = DriveApp.getFileById(fileId);
  if (file.getMimeType() === MimeType.GOOGLE_SHEETS) {
    var existingId = file.getId();
    Logger.log({ label: 'ensureGoogleSheetCopy:skip-convert', sheetIdPreview: existingId ? existingId.slice(0, 6) : '' });
    return existingId;
  }
  if (typeof Drive === 'undefined' || !Drive || !Drive.Files) {
    throw new Error('Enable Advanced Drive Service to convert Venmo .xlsx to Google Sheets');
  }
  var parents = file.getParents();
  var parentId = parents.hasNext() ? parents.next().getId() : null;
  var resource = { mimeType: MimeType.GOOGLE_SHEETS, title: file.getName() + ' (GS)' };
  if (parentId) { resource.parents = [{ id: parentId }]; }
  Logger.log({ label: 'ensureGoogleSheetCopy:convert', parentIdPreview: parentId ? parentId.slice(0, 6) : '', title: resource.title });
  var copied = Drive.Files.copy(resource, fileId);
  Logger.log({ label: 'ensureGoogleSheetCopy:done', newSheetIdPreview: copied && copied.id ? String(copied.id).slice(0, 6) : '' });
  return copied.id;
}

function normalizeHeaderKey(value) {
  var normalized = String(value || '').trim().toLowerCase().replace(/[^a-z0-9]+/g, '_');
  normalized = normalized.replace(/_+/g, '_');
  normalized = normalized.replace(/^_+|_+$/g, '');
  return normalized;
}

function escapeRegexLiteral(text) { return String(text || '').replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&'); }

function createNameTester(pattern) {
  var raw = String(pattern || '').trim();
  if (!raw) { return { test: function () { return true; }, hasPattern: false, pattern: null }; }
  var upperRaw = raw.toUpperCase();
  var hasSpecial = /[*?]/.test(raw) || upperRaw.indexOf('MONTH') !== -1 || upperRaw.indexOf('YYYY') !== -1;
  var parts = []; var i = 0;
  while (i < raw.length) {
    var upperSlice = upperRaw.slice(i);
    if (upperSlice.indexOf('MONTH') === 0) { parts.push('[A-Za-z]+'); i += 5; continue; }
    if (upperSlice.indexOf('YYYY') === 0) { parts.push('\\d{4}'); i += 4; continue; }
    var ch = raw.charAt(i);
    if (ch === '*') { parts.push('.*'); } else if (ch === '?') { parts.push('.'); } else { parts.push(escapeRegexLiteral(ch)); }
    i += 1;
  }
  var regexBody = parts.join('');
  if (!hasSpecial) { regexBody = '.*' + regexBody + '.*'; }
  var regex = new RegExp('^' + regexBody + '$', 'i');
  return { test: function (name) { if (name === null || name === undefined) return false; return regex.test(String(name)); }, hasPattern: true, pattern: regex.toString() };
}

function loadMappingSheet(spreadsheet) {
  var sheet = resolveOrCreateSheet(spreadsheet, 'venmo_mapping', ['payer_label', 'donor_id', 'email', 'notes']);
  var map = {}; var values = sheet.getDataRange().getValues();
  for (var i = 1; i < values.length; i++) {
    var row = values[i]; var payer = String(row[0] || '').trim().toUpperCase(); var donorId = String(row[1] || '').trim(); var email = String(row[2] || '').trim();
    if (payer && donorId) map[payer] = { donor_id: donorId, email: email };
  }
  return map;
}

function loadImportedKeys(spreadsheet) {
  var sheet = resolveOrCreateSheet(spreadsheet, 'venmo_imported', ['unique_key', 'donor_id', 'amount', 'date', 'transaction_id', 'payer_label']);
  var set = new Set(); var values = sheet.getDataRange().getValues();
  for (var i = 1; i < values.length; i++) { var key = String(values[i][0] || '').trim(); if (key) set.add(key); }
  return { sheet: sheet, keys: set };
}

function extractEmail(text) {
  var s = String(text || '');
  var m = s.match(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i);
  return m ? m[0] : '';
}

function dpGiftExistsByReference(donorId, reference, config) {
  if (!reference) return false;
  var sql = "SELECT TOP 1 gift_id FROM dpgift WHERE donor_id=" + Number(donorId) + " AND reference='" + escapeSql(reference) + "'";
  var rows = callDonorPerfect(sql, config);
  return rows && rows.length > 0;
}

function dpSaveGift(donorId, giftDate, amount, reference, fund, campaign, solicit, config) {
  var params = {
    '@donor_id': Number(donorId),
    '@gift_date': giftDate instanceof Date ? giftDate : new Date(giftDate),
    '@amount': Number(amount),
    '@record_type': 'G',
    '@gift_type': 'VENMO',
    '@fund': fund || null,
    '@campaign': campaign || null,
    '@solicit_code': solicit || null,
    '@gl_code': (typeof getVenmoConfig === 'function' ? (getVenmoConfig().glCode || null) : null),
    '@reference': reference || null,
    '@user_id': config.apiUserId || 'DP_API_KEY'
  };
  var url = config.apiUrl + '?apikey=' + encodeURIComponent(config.apiKey) + '&action=' + encodeURIComponent('dp_savegift_xml') + '&params=' + encodeURIComponent(buildParamsValue(params));
  var res = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
  var status = res.getResponseCode();
  var body = res.getContentText();
  var trimmed = String(body || '').trim();
  var preview = trimmed.length > 500 ? trimmed.slice(0, 500) : trimmed;
  if (status !== 200) {
    var unauthorized = (status === 401 || status === 403) || /user not authorized/i.test(preview);
    var message = unauthorized ? 'user not authorized for this api call' : ('HTTP ' + status + ' ' + preview);
    Logger.log({ label: unauthorized ? 'dpSaveGift:auth-error' : 'dpSaveGift:error-status', status: status, bodyPreview: preview });
    return { ok: false, status: 'failed', errorMessage: message, requiresAuthFix: unauthorized };
  }
  if (trimmed && /user not authorized/i.test(trimmed)) {
    Logger.log({ label: 'dpSaveGift:auth-error-body', bodyPreview: preview });
    return { ok: false, status: 'failed', errorMessage: 'user not authorized for this api call', requiresAuthFix: true };
  }
  if (trimmed && trimmed.indexOf('<result') !== -1) return { ok: true, status: 'inserted' };
  var lower = trimmed.toLowerCase();
  if (lower.indexOf('duplicate') !== -1) return { ok: true, status: 'duplicate' };
  if (trimmed) { Logger.log({ label: 'dpSaveGift:unexpected-body', bodyPreview: preview }); }
  return { ok: false, status: 'failed', errorMessage: preview };
}

function dpSaveDonor(record, config) {
  var safe = function (v) { return v === undefined ? null : v; };
  var params = {
    '@donor_id': record && record.hasOwnProperty('@donor_id') ? record['@donor_id'] : 0,
    '@first_name': safe(record && record['@first_name']),
    '@last_name': safe(record && record['@last_name']),
    '@middle_name': safe(record && record['@middle_name']),
    '@suffix': safe(record && record['@suffix']),
    '@title': safe(record && record['@title']),
    '@salutation': safe(record && record['@salutation']),
    '@prof_title': safe(record && record['@prof_title']),
    '@opt_line': safe(record && record['@opt_line']),
    '@address': safe(record && record['@address']),
    '@address2': safe(record && record['@address2']),
    '@city': safe(record && record['@city']),
    '@state': safe(record && record['@state']),
    '@zip': safe(record && record['@zip']),
    '@country': safe(record && record['@country']),
    '@address_type': safe(record && record['@address_type']),
    '@home_phone': safe(record && record['@home_phone']),
    '@business_phone': safe(record && record['@business_phone']),
    '@fax_phone': safe(record && record['@fax_phone']),
    '@mobile_phone': safe(record && record['@mobile_phone']),
    '@email': safe(record && record['@email']),
    '@org_rec': (record && record['@org_rec']) ? record['@org_rec'] : 'N',
    '@donor_type': (record && record['@donor_type']) ? record['@donor_type'] : 'IN',
    '@nomail': (record && record['@nomail']) ? record['@nomail'] : 'N',
    '@nomail_reason': safe(record && record['@nomail_reason']),
    '@narrative': safe(record && record['@narrative']),
    '@donor_rcpt_type': (record && record['@donor_rcpt_type']) ? record['@donor_rcpt_type'] : 'C',
    '@user_id': (config && config.apiUserId) ? config.apiUserId : ((record && record['@user_id']) ? record['@user_id'] : 'DP_API_KEY')
  };
  var url = config.apiUrl + '?apikey=' + encodeURIComponent(config.apiKey) + '&action=' + encodeURIComponent('dp_savedonor') + '&params=' + encodeURIComponent(buildParamsValue(params));
  var res = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
  var status = res.getResponseCode();
  var body = res.getContentText();
  var trimmedBody = String(body || '').trim();
  var preview = trimmedBody.length > 500 ? trimmedBody.slice(0, 500) : trimmedBody;
  if (status !== 200) {
    var unauthorized = (status === 401 || status === 403) || /user not authorized/i.test(preview);
    var message = unauthorized ? 'user not authorized for this api call' : ('HTTP ' + status + ' ' + preview);
    Logger.log({ label: unauthorized ? 'dpSaveDonor:auth-error' : 'dpSaveDonor:error-status', status: status, bodyPreview: preview });
    return { ok: false, status: 'failed', errorMessage: message, requiresAuthFix: unauthorized };
  }
  if (trimmedBody && /user not authorized/i.test(trimmedBody)) {
    Logger.log({ label: 'dpSaveDonor:auth-error-body', bodyPreview: preview });
    return { ok: false, status: 'failed', errorMessage: 'user not authorized for this api call', requiresAuthFix: true };
  }
  if (trimmedBody && trimmedBody.indexOf('<result') !== -1) {
    var records;
    try { records = parseRecords(trimmedBody); } catch (err) {
      Logger.log({ label: 'dpSaveDonor:parse-error', message: err && err.message, bodyPreview: preview });
      return { ok: false, status: 'failed', errorMessage: err && err.message ? err.message : 'parse-result-error' };
    }
    if (records && records.length) {
      var firstRecord = records[0];
      if (firstRecord.hasOwnProperty('donor_id')) {
        var donorIdValue = firstRecord.donor_id;
        if (donorIdValue) { return { ok: true, status: 'inserted', donor_id: donorIdValue }; }
      }
      var missingIdMessage = 'missing donor_id in response';
      Logger.log({ label: 'dpSaveDonor:missing-donor-id', bodyPreview: preview, records: records });
      return { ok: false, status: 'failed', errorMessage: missingIdMessage + ' ' + preview };
    }
    Logger.log({ label: 'dpSaveDonor:empty-result-records', bodyPreview: preview });
    return { ok: false, status: 'failed', errorMessage: 'empty result records ' + preview };
  }
  var lower = trimmedBody.toLowerCase();
  if (lower.indexOf('duplicate') !== -1) { return { ok: true, status: 'duplicate' }; }
  var errorMessage = '';
  if (trimmedBody && trimmedBody.indexOf('<error') !== -1) {
    try {
      var doc = XmlService.parse(trimmedBody);
      var root = doc.getRootElement();
      if (root && root.getName && String(root.getName()).toLowerCase() === 'error') { errorMessage = root.getText(); }
    } catch (parseErr) { Logger.log({ label: 'dpSaveDonor:error-xml-parse', message: parseErr && parseErr.message, bodyPreview: preview }); }
  }
  if (!errorMessage) { errorMessage = trimmedBody ? preview : 'empty response body'; }
  Logger.log({ label: 'dpSaveDonor:unexpected-body', bodyPreview: preview, errorMessage: errorMessage });
  return { ok: false, status: 'failed', errorMessage: errorMessage };
}

function collectMatchingVenmoFiles(folderId, nameFilter) {
  if (!folderId) throw new Error('set VENMO_FOLDER_ID in script properties');
  var rawFilter = String(nameFilter || '').trim();
  var matcher = createNameTester(rawFilter);
  Logger.log({ label: 'collectMatchingVenmoFiles:start', folderIdPreview: folderId ? String(folderId).slice(0, 6) : 'missing', nameFilter: rawFilter, patternApplied: matcher.pattern });
  var matches = [];
  function considerFile(file) {
    var name = file.getName();
    if (matcher.hasPattern && !matcher.test(name)) { return; }
    var updated = file.getLastUpdated().getTime();
    var mime = file.getMimeType();
    if (mime === MimeType.GOOGLE_SHEETS || mime === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet') {
      matches.push({ id: file.getId(), name: name, mime: mime, updated: updated });
    }
  }
  function walk(folder) { var files = folder.getFiles(); while (files.hasNext()) { considerFile(files.next()); } var subs = folder.getFolders(); while (subs.hasNext()) { walk(subs.next()); } }
  var root = DriveApp.getFolderById(folderId); walk(root);
  matches.sort(function (a, b) { return a.updated - b.updated; });
  Logger.log({ label: 'collectMatchingVenmoFiles:done', matchCount: matches.length, filterPattern: matcher.pattern, previews: matches.slice(0, 5).map(function (item) { return { id: item.id ? item.id.slice(0, 6) : '', name: item.name, updated: item.updated }; }) });
  return matches;
}

function importVenmoTransactions() {
  var config = getConfig();
  var venmo = getVenmoConfig();
  var spreadsheet = config.reportSpreadsheetId ? SpreadsheetApp.openById(config.reportSpreadsheetId) : SpreadsheetApp.getActiveSpreadsheet();
  if (!spreadsheet) throw new Error('unable to resolve spreadsheet destination');
  var timezone = Session.getScriptTimeZone();
  Logger.log({ label: 'importVenmoTransactions:start', reportSpreadsheetId: (spreadsheet && spreadsheet.getId ? spreadsheet.getId() : 'active'), venmoFolderIdSet: !!venmo.folderId, venmoFileMatch: venmo.fileMatch });
  var unmatchedSheet = resolveOrCreateSheet(spreadsheet, 'venmo_unmatched', ['unique_key', 'reason', 'payer_label', 'transaction_id', 'date', 'amount', 'note', 'donor_error']);
  var updatesSheet = resolveOrCreateSheet(spreadsheet, 'venmo_updates', ['unique_key', 'status', 'donor_id', 'transaction_id', 'date', 'amount', 'payer_label']);
  var newDonorsSheet = resolveOrCreateSheet(spreadsheet, 'venmo_new_donors', ['donor_id', 'payer_label', 'email', 'status']);
  var mapping = loadMappingSheet(spreadsheet);
  var imported = loadImportedKeys(spreadsheet);
  var importedKeys = imported.keys;
  var importedSheet = imported.sheet;
  var matches = collectMatchingVenmoFiles(venmo.folderId, venmo.fileMatch);
  Logger.log({ label: 'importVenmoTransactions:matches-resolved', matchCount: matches.length });
  if (!matches.length) { Logger.log({ label: 'importVenmoTransactions:no-matches-found' }); return { imported: 0, skipped: 0 }; }
  var totalImported = 0; var totalUnmatched = 0;
  matches.forEach(function (match, index) {
    var fileId = match.id; if (!fileId) { return; }
    var fileName = match.name || '';
    Logger.log({ label: 'importVenmoTransactions:file-start', index: index, fileIdPreview: fileId.slice(0, 6), name: fileName, mime: match.mime });
    var sheetId = ensureGoogleSheetCopy(fileId);
    Logger.log({ label: 'importVenmoTransactions:sheet-ready', sheetIdPreview: sheetId ? sheetId.slice(0, 6) : '' });
    var ss = SpreadsheetApp.openById(sheetId);
    var sheet = ss.getSheets()[0];
    var values = sheet.getDataRange().getValues();
    Logger.log({ label: 'importVenmoTransactions:rows-loaded', rowCount: values.length, fileName: fileName });
    if (!values.length) { Logger.log({ label: 'importVenmoTransactions:no-data-rows', fileName: fileName }); return; }
    var headerRowIndex = -1; var header = null;
    for (var rHeader = 0; rHeader < values.length; rHeader++) {
      var normalized = values[rHeader].map(normalizeHeaderKey);
      var hasId = normalized.indexOf('id') !== -1;
      var hasAmount = normalized.indexOf('amount_total') !== -1 || normalized.indexOf('amount') !== -1;
      var hasDate = normalized.indexOf('datetime') !== -1 || normalized.indexOf('date') !== -1;
      if ((hasId && hasAmount) || (hasId && hasDate)) { headerRowIndex = rHeader; header = normalized; break; }
    }
    if (headerRowIndex === -1) { Logger.log({ label: 'importVenmoTransactions:no-header-detected', previewRows: values.slice(0, Math.min(3, values.length)), fileName: fileName }); return; }
    Logger.log({ label: 'importVenmoTransactions:header-found', headerRowIndex: headerRowIndex, headerPreview: values[headerRowIndex], fileName: fileName });
    Logger.log({ label: 'importVenmoTransactions:header-normalized', headerNormalized: header, fileName: fileName });
    var dataStartRow = headerRowIndex + 1; if (dataStartRow >= values.length) { Logger.log({ label: 'importVenmoTransactions:no-data-after-header', headerRowIndex: headerRowIndex, fileName: fileName }); return; }
    var idx = function (keyCandidates) { for (var i = 0; i < keyCandidates.length; i++) { var k = keyCandidates[i]; var j = header.indexOf(k); if (j !== -1) return j; } return -1; };
    var idxDate = idx(['date', 'datetime', 'completed_date', 'time']); if (idxDate === -1) idxDate = idx(['transaction_date']);
    var idxAmount = idx(['amount', 'amount_total', 'amount__total', 'net_amount', 'total']); if (idxAmount === -1) idxAmount = idx(['amount_total']); if (idxAmount === -1) idxAmount = idx(['gross_amount', 'amount_gross']);
    var idxNote = idx(['note', 'description', 'memo']);
    var idxFrom = idx(['from', 'payer', 'name', 'username', 'from__name']); if (idxFrom === -1) idxFrom = idx(['customer_name', 'payer_name']);
    var idxTxn = idx(['id', 'transaction_id', 'txn_id', 'transfer_id']);
    var idxType = idx(['type', 'transaction_type']);
    var idxStatus = idx(['status']);
    var missingColumns = []; if (idxDate === -1) missingColumns.push('date'); if (idxAmount === -1) missingColumns.push('amount'); if (idxFrom === -1) missingColumns.push('payer'); if (idxTxn === -1) missingColumns.push('transaction id');
    if (missingColumns.length) { Logger.log({ label: 'importVenmoTransactions:missing-required-columns', missing: missingColumns, fileName: fileName }); return; }
    var dryRunProp = String(scriptProperties.getProperty('DRY_RUN') || '0').trim(); var dryRun = dryRunProp === '1' || dryRunProp.toLowerCase() === 'true';
    Logger.log({ label: 'importVenmoTransactions:indices', idxDate: idxDate, idxAmount: idxAmount, idxNote: idxNote, idxFrom: idxFrom, idxTxn: idxTxn, idxType: idxType, idxStatus: idxStatus, dryRun: dryRun, fileName: fileName });
    var rowsImported = []; var rowsUnmatched = []; var rowsImportedLog = []; var rowsNewDonors = [];
    for (var r = dataStartRow; r < values.length; r++) {
      var row = values[r];
      var typeRaw = idxType !== -1 ? row[idxType] : '';
      var statusRaw = idxStatus !== -1 ? row[idxStatus] : '';
      var dateRaw = idxDate !== -1 ? row[idxDate] : '';
      var amountRaw = idxAmount !== -1 ? row[idxAmount] : '';
      var noteRaw = idxNote !== -1 ? sanitizeAscii(row[idxNote]) : '';
      var payerRaw = idxFrom !== -1 ? sanitizeAscii(row[idxFrom]) : '';
      var txnId = idxTxn !== -1 ? String(row[idxTxn] || '').trim() : '';
      var payerLabel = sanitizeAscii(String(payerRaw || '')).trim();
      var amount = parseAmount(amountRaw);
      var giftDate;
      if (dateRaw instanceof Date) { giftDate = dateRaw; } else if (dateRaw && typeof dateRaw === 'string') { var parsedDate = new Date(dateRaw); giftDate = isNaN(parsedDate.getTime()) ? null : parsedDate; } else { giftDate = null; }
      var giftDateLabel = (giftDate instanceof Date && !isNaN(giftDate.getTime())) ? Utilities.formatDate(giftDate, timezone, 'yyyy-MM-dd') : String(dateRaw || '');
      var hasRequiredFields = payerLabel && giftDate && !isNaN(amount) && amount !== 0;
      if (!hasRequiredFields) { Logger.log({ label: 'importVenmoTransactions:skipped-row', reason: 'missing-required-fields', fileName: fileName, index: r, txnId: txnId, payer: payerLabel, amountRaw: amountRaw, parsedAmount: amount, dateRaw: dateRaw, giftDate: giftDateLabel }); continue; }
      if (isRefundRow(typeRaw, amount)) { Logger.log({ label: 'importVenmoTransactions:skipped-row', reason: 'refund-row', fileName: fileName, index: r, txnId: txnId, payer: payerLabel, amount: amount, note: noteRaw }); continue; }
      if (isTransferRow(typeRaw, statusRaw, payerLabel, noteRaw)) { Logger.log({ label: 'importVenmoTransactions:skipped-row', reason: 'transfer-row', fileName: fileName, index: r, txnId: txnId, payer: payerLabel, amount: amount, note: noteRaw }); continue; }
      var uniqueKey = txnId ? txnId : [Utilities.formatDate(giftDate, timezone, 'yyyy-MM-dd'), amount.toFixed(2), payerLabel, String(noteRaw || '')].join('|');
      if (importedKeys.has(uniqueKey)) { rowsImportedLog.push([uniqueKey, 'already-recorded', '', txnId, giftDate, amount, payerLabel]); continue; }
      var donorId = '';
      var email = extractEmail(noteRaw) || '';
      var mappingKey = payerLabel.toUpperCase();
      var donorCreated = false;
      var matchResult = resolveVenmoDonorMatch(payerLabel, email, config);
      if (matchResult.donorId) { donorId = matchResult.donorId; } else if (mapping[mappingKey] && mapping[mappingKey].donor_id) { donorId = String(mapping[mappingKey].donor_id); }
      if (!donorId) {
        if (matchResult.status === 'ambiguous-name') { Logger.log({ label: 'importVenmoTransactions:unmatched', reason: 'ambiguous-donor-match', fileName: fileName, uniqueKey: uniqueKey, txnId: txnId, payer: payerLabel, amount: amount, giftDate: giftDateLabel, note: noteRaw }); rowsUnmatched.push([uniqueKey, 'ambiguous-donor-match', payerLabel, txnId, giftDate, amount, String(noteRaw || ''), '']); continue; }
        var nameParts = matchResult.firstName !== undefined ? { first: matchResult.firstName, last: matchResult.lastName } : splitNameFromLabel(payerLabel);
        var donorPayload = { '@donor_id': 0, '@first_name': nameParts.first || null, '@last_name': nameParts.last || (nameParts.first ? nameParts.first : 'VENMO DONOR'), '@email': email || null, '@user_id': config.apiUserId || 'DP_API_KEY', '@donor_type': 'IN', '@org_rec': 'N' };
        var donorResult = dpSaveDonor(donorPayload, config);
        if (donorResult && donorResult.ok && donorResult.donor_id) { donorId = String(donorResult.donor_id); donorCreated = true; rowsNewDonors.push([donorId, payerLabel, email, donorResult.status || 'inserted']); }
        else { var donorCreateMessage = donorResult && donorResult.errorMessage ? donorResult.errorMessage : ''; Logger.log({ label: 'importVenmoTransactions:unmatched', reason: 'donor-create-failed', fileName: fileName, uniqueKey: uniqueKey, txnId: txnId, payer: payerLabel, amount: amount, giftDate: giftDateLabel, note: noteRaw, donorCreateError: donorCreateMessage }); var donorReason = (donorResult && donorResult.requiresAuthFix) ? 'donor-create-failed-auth' : 'donor-create-failed'; if (!donorCreateMessage && donorReason === 'donor-create-failed-auth') { donorCreateMessage = 'user not authorized for this api call'; } rowsUnmatched.push([uniqueKey, donorReason, payerLabel, txnId, giftDate, amount, String(noteRaw || ''), donorCreateMessage]); continue; }
      }
      var reference = txnId ? 'VENMO:' + txnId : 'VENMO:' + uniqueKey;
      if (dpGiftExistsByReference(donorId, reference, config)) { rowsImportedLog.push([uniqueKey, 'exists-by-reference', donorId, txnId, giftDate, amount, payerLabel]); continue; }
      var statusText = 'dry-run'; var ok = true;
      if (!dryRun) {
        var result = dpSaveGift(donorId, giftDate, amount, reference, venmo.fund, venmo.campaign, venmo.solicitation, config);
        ok = result.ok; statusText = result.status;
        if (!ok && result && result.requiresAuthFix) { Logger.log({ label: 'importVenmoTransactions:unmatched', reason: 'gift-save-auth', fileName: fileName, uniqueKey: uniqueKey, txnId: txnId, payer: payerLabel, amount: amount, giftDate: giftDateLabel, note: noteRaw, donorCreateError: result.errorMessage }); rowsUnmatched.push([uniqueKey, 'gift-save-auth', payerLabel, txnId, giftDate, amount, String(noteRaw || ''), result.errorMessage || 'user not authorized for this api call']); }
        else if (!ok && result && result.errorMessage) { Logger.log({ label: 'importVenmoTransactions:unmatched', reason: 'gift-save-failed', fileName: fileName, uniqueKey: uniqueKey, txnId: txnId, payer: payerLabel, amount: amount, giftDate: giftDateLabel, note: noteRaw, donorCreateError: result.errorMessage }); rowsUnmatched.push([uniqueKey, 'gift-save-failed', payerLabel, txnId, giftDate, amount, String(noteRaw || ''), result.errorMessage]); }
      }
      if (ok) {
        importedKeys.add(uniqueKey);
        rowsImported.push([uniqueKey, donorId, amount, giftDate, txnId, payerLabel]);
        var statusDetail = statusText; if (donorCreated) { statusDetail = statusText + '|new-donor'; }
        rowsImportedLog.push([uniqueKey, statusDetail, donorId, txnId, giftDate, amount, payerLabel]);
      } else {
        if (dryRun) { Logger.log({ label: 'importVenmoTransactions:unmatched', reason: 'insert-failed', fileName: fileName, uniqueKey: uniqueKey, txnId: txnId, payer: payerLabel, amount: amount, giftDate: giftDateLabel, note: noteRaw }); rowsUnmatched.push([uniqueKey, 'insert-failed', payerLabel, txnId, giftDate, amount, String(noteRaw || ''), 'dry-run']); }
      }
      Utilities.sleep(200);
    }
    if (rowsImported.length) importedSheet.getRange(importedSheet.getLastRow() + 1, 1, rowsImported.length, rowsImported[0].length).setValues(rowsImported);
    if (rowsUnmatched.length) {
      var expectedCols = unmatchedSheet.getRange(1, 1, 1, unmatchedSheet.getLastColumn()).getValues()[0]; expectedCols = expectedCols && expectedCols.length ? expectedCols.length : rowsUnmatched[0].length;
      if (unmatchedSheet.getLastColumn() < expectedCols) { unmatchedSheet.insertColumnsAfter(unmatchedSheet.getLastColumn(), expectedCols - unmatchedSheet.getLastColumn()); }
      rowsUnmatched = rowsUnmatched.map(function (row) { var adjusted = row.slice(); while (adjusted.length < expectedCols) { adjusted.push(''); } if (adjusted.length > expectedCols) { adjusted = adjusted.slice(0, expectedCols); } return adjusted; });
      unmatchedSheet.getRange(unmatchedSheet.getLastRow() + 1, 1, rowsUnmatched.length, expectedCols).setValues(rowsUnmatched);
    }
    if (rowsImportedLog.length) updatesSheet.getRange(updatesSheet.getLastRow() + 1, 1, rowsImportedLog.length, rowsImportedLog[0].length).setValues(rowsImportedLog);
    if (rowsNewDonors.length) newDonorsSheet.getRange(newDonorsSheet.getLastRow() + 1, 1, rowsNewDonors.length, rowsNewDonors[0].length).setValues(rowsNewDonors);
    totalImported += rowsImported.length; totalUnmatched += rowsUnmatched.length;
  });
  Logger.log({ label: 'importVenmoTransactions:done', imported: totalImported, unmatched: totalUnmatched });
  return { imported: totalImported, unmatched: totalUnmatched };
}



/**
 * Приёмник для чек-листа «Оценка компетенций студента».
 *
 * Куда вставлять: откройте Google-таблицу → Расширения → Apps Script,
 * замените содержимое файла Code.gs на этот текст, сохраните.
 *
 * Как опубликовать: Развернуть → Новое развёртывание → тип «Веб-приложение»,
 * «Выполнять от имени: я», «Есть доступ: у всех» → Развернуть.
 * Скопируйте адрес вида https://script.google.com/macros/s/…/exec
 * и вставьте его в приложении: ☰ → «Адрес веб-приложения Apps Script».
 *
 * Строка на каждого стажёра одна: повторная отправка обновляет её,
 * новые стажёры дописываются снизу.
 */

var SHEET_NAME = 'компетенции';   // имя листа внутри таблицы — поменяйте, если переименуете

var HEAD = [
  'Обновлено', 'Стажёр', 'Куратор', 'Начало практики',
  'Отмечено «видели» и «делали»', 'Всего «видели» и «делали»',
  'Отмечено кнопок', 'Всего кнопок', 'Освоено навыков', 'Всего навыков',
  'Видео', 'Видели на сессии', 'Делали на чужой сессии',
  'Самостоятельно: куратор', 'Самостоятельно: на сессии'
];

function sheet_() {
  var ss = SpreadsheetApp.getActive();
  var sh = ss.getSheetByName(SHEET_NAME) || ss.insertSheet(SHEET_NAME);
  if (sh.getLastRow() === 0) {
    sh.appendRow(HEAD);
    sh.getRange(1, 1, 1, HEAD.length).setFontWeight('bold');
    sh.setFrozenRows(1);
  } else {
    // шапка изменилась после обновления скрипта — переписываем
    var cur = sh.getRange(1, 1, 1, HEAD.length).getValues()[0].join('\u0000');
    if (cur !== HEAD.join('\u0000')) {
      sh.getRange(1, 1, 1, HEAD.length).setValues([HEAD]).setFontWeight('bold');
    }
  }
  return sh;
}

function doPost(e) {
  try {
    var d = JSON.parse(e.postData.contents);
    var name = String(d.name || '').trim();
    if (!name) return out_({ ok: false, error: 'пустое имя' });

    var sh = sheet_();
    var row = [
      new Date(), name, d.curator || '', d.start || '',
      Number(d.pair) || 0, Number(d.pairTotal) || 0,
      Number(d.marked) || 0, Number(d.total) || 0,
      Number(d.skills) || 0, Number(d.skillsTotal) || 0,
      Number(d.video) || 0, Number(d.seen) || 0, Number(d.did) || 0,
      Number(d.fk) || 0, Number(d.fs) || 0
    ];

    // ищем стажёра во втором столбце, сравнивая без учёта регистра и лишних пробелов
    var last = sh.getLastRow();
    var found = 0;
    if (last > 1) {
      var names = sh.getRange(2, 2, last - 1, 1).getValues();
      var key = name.toLowerCase();
      for (var i = 0; i < names.length; i++) {
        if (String(names[i][0]).trim().toLowerCase() === key) { found = i + 2; break; }
      }
    }

    if (found) sh.getRange(found, 1, 1, row.length).setValues([row]);
    else sh.appendRow(row);

    return out_({ ok: true, row: found || sh.getLastRow() });
  } catch (err) {
    return out_({ ok: false, error: String(err) });
  }
}

/** Открыть адрес в браузере, чтобы проверить, что развёртывание живо. */
function doGet() {
  return out_({ ok: true, sheet: SHEET_NAME, rows: Math.max(sheet_().getLastRow() - 1, 0) });
}

function out_(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

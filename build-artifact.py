#!/usr/bin/env python3
"""index.html (PWA) -> artifact.html (одностраничная версия для Artifacts).

Отличия артефакта от PWA:
  * нет service worker и манифеста — значит нет офлайна и установки;
  * песочница артефакта блокирует обычное скачивание файлов,
    поэтому экспорт идёт через capability `downloads`;
  * window.print() в песочнице может не сработать, поэтому отчёт
    сначала показывается на экране, а печать — уже кнопкой.
"""
import re, sys, pathlib

src = pathlib.Path(__file__).with_name("index.html").read_text(encoding="utf-8")
out = pathlib.Path(__file__).with_name("artifact.html")


def cut(text, old, new, count=1):
    if text.count(old) < 1:
        sys.exit("не найден фрагмент:\n" + old[:160])
    return text.replace(old, new, count)


# ---------- 1. снимаем обёртку документа ----------
head_start = src.index("<title>")
style_end = src.index("</style>") + len("</style>")
head = src[head_start:style_end]

# манифеста и иконок на хосте артефакта нет — ссылки убираем
head = "\n".join(
    l for l in head.split("\n")
    if not re.search(r'rel="(manifest|icon|apple-touch-icon)"', l)
)

body = src[src.index("<body>") + len("<body>"):src.index("</body>")].strip()

# ---------- 2. CSS: оверлей отчёта, вставляем ДО @media print ----------
REPORT_CSS = """
/* ---------- отчёт на экране (в артефакте печать может быть заблокирована) ---------- */
#report{position:fixed;inset:0;z-index:70;background:var(--bg);display:none;overflow:auto;overscroll-behavior:contain}
#report.on{display:block}
.rep-bar{
  position:sticky;top:0;z-index:2;display:flex;gap:8px;align-items:center;
  padding:calc(env(safe-area-inset-top,0px) + 10px) 14px 10px;
  background:var(--card);border-bottom:1px solid var(--line-2)
}
.rep-bar .ttl{flex:1;font-weight:650;font-size:15px;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rep-btn{padding:8px 12px;border-radius:10px;background:var(--line-2);color:var(--ink);font-size:13px;font-weight:600;flex:none}
.rep-btn.pri{background:var(--accent);color:#fff}
.rep-wrap{padding:14px 14px calc(28px + var(--safe-b));max-width:920px;margin:0 auto}
#printarea{
  display:block;background:var(--card);border-radius:var(--r);padding:16px;
  box-shadow:var(--shadow);overflow-x:auto
}
#printarea h1{font-size:17px;margin:0 0 4px;color:var(--accent)}
#printarea .ph{font-size:12.5px;color:var(--ink-2);margin:0 0 12px;line-height:1.5}
#printarea table{width:100%;border-collapse:collapse;font-size:12px;min-width:560px}
#printarea th,#printarea td{border:1px solid var(--line);padding:5px 7px;vertical-align:top;text-align:left}
#printarea th{background:var(--blue-soft);font-size:11px;text-align:center;font-weight:650}
#printarea td.t{width:38%}
#printarea td.d{text-align:center;white-space:nowrap;font-size:11px;font-variant-numeric:tabular-nums}
#printarea tr.band td{background:var(--band);color:var(--band-ink);font-weight:700;text-align:center}
#printarea .fin{font-size:10.5px;line-height:1.35;color:var(--ink-2)}

"""
head = cut(head, "@media print{", REPORT_CSS + "@media print{")

# в печати оверлей раскрываем, панель прячем
head = cut(
    head,
    "  .top,.searchwrap,main,.fab,.scrim,.sheet,.toast{display:none!important}",
    "  .top,.searchwrap,main,.fab,.scrim,.sheet,.toast,.rep-bar{display:none!important}\n"
    "  #report{display:block!important;position:static;overflow:visible;background:#fff}\n"
    "  .rep-wrap{padding:0;max-width:none}\n"
    "  #printarea{box-shadow:none;border-radius:0;background:#fff}",
)

# ---------- 3. разметка: оверлей вокруг #printarea ----------
body = cut(
    body,
    '<div id="printarea"></div>',
    """<div id="report">
  <div class="rep-bar">
    <button class="rep-btn" id="repClose">Закрыть</button>
    <span class="ttl">Отчёт</span>
    <button class="rep-btn" id="repDl" hidden>Скачать</button>
    <button class="rep-btn pri" id="repPrint">Печать</button>
  </div>
  <div class="rep-wrap"><div id="printarea"></div></div>
</div>""",
)

# ---------- 4. скрипт ----------
script = body[body.index("<script>") + len("<script>"):body.rindex("</script>")]
body = body[:body.index("<script>")].rstrip()

# отчёт: показываем на экране вместо немедленной печати
script = cut(
    script,
    """  document.getElementById("printarea").innerHTML=h;
  closeSheets();
  setTimeout(()=>window.print(),150);""",
    """  document.getElementById("printarea").innerHTML=h;
  closeSheets();
  document.getElementById("report").classList.add("on");
  document.body.style.overflow="hidden";
  document.getElementById("report").scrollTop=0;""",
)

# скачивание через capability downloads
script = cut(
    script,
    """function dl(name,text,type){
  const b=new Blob([text],{type:type+";charset=utf-8"});
  const u=URL.createObjectURL(b), a=document.createElement("a");
  a.href=u; a.download=name; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(()=>URL.revokeObjectURL(u),1500);
  toast("Файл сохранён");
}""",
    """/* В песочнице артефакта страница не может скачать файл сама — просим об этом
   платформу. Вне песочницы (сохранённая копия) остаётся обычная ссылка. */
const DLP = (window.claude && window.claude.use)
  ? window.claude.use("downloads").catch(()=>null)
  : Promise.resolve(null);

async function dl(name,text,type){
  const D=await DLP;
  if(D){
    try{
      const r=await D.save({filename:name, data:text});
      if(r.status==="saved") toast("Файл сохранён");
    }catch(e){
      const c=e&&e.code;
      toast(c==="declined" ? "Сохранение отменено"
          : c==="rate_limited" ? "Уже открыт другой запрос на сохранение"
          : "Не удалось сохранить файл");
    }
    return;
  }
  if(window.claude){ toast("Скачивание здесь недоступно"); return; }
  const b=new Blob([text],{type:type+";charset=utf-8"});
  const u=URL.createObjectURL(b), a=document.createElement("a");
  a.href=u; a.download=name; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(()=>URL.revokeObjectURL(u),1500);
  toast("Файл сохранён");
}""",
)

# вместо регистрации service worker — кнопки отчёта и проверка downloads
script = cut(
    script,
    """if("serviceWorker" in navigator && location.protocol.startsWith("http")){
  window.addEventListener("load",()=>navigator.serviceWorker.register("sw.js").catch(()=>{}));
}""",
    """/* ---------- отчёт ---------- */
function closeReport(){
  document.getElementById("report").classList.remove("on");
  document.body.style.overflow="";
}
document.getElementById("repClose").onclick=closeReport;
document.getElementById("repPrint").onclick=()=>window.print();
document.getElementById("repDl").onclick=async()=>{
  const css=[...document.querySelectorAll("style")].map(x=>x.textContent).join("\\n");
  const doc="<!doctype html><html lang=\\"ru\\"><head><meta charset=\\"utf-8\\">"+
    "<title>Компетенции — "+esc(db.profile.name||"стажёр")+"</title><style>"+css+
    "\\n#printarea{display:block}body{margin:24px;font:14px/1.45 -apple-system,BlinkMacSystemFont,\\"Segoe UI\\",Roboto,Arial,sans-serif;background:#fff;color:#111}</style>"+
    "</head><body><div id=\\"printarea\\">"+document.getElementById("printarea").innerHTML+
    "</div></body></html>";
  dl("otchet-"+fileName()+".html", doc, "text/html");
};
document.addEventListener("keydown",e=>{
  if(e.key==="Escape"){ closeReport(); closeSheets(); }
});
DLP.then(D=>{ if(D) document.getElementById("repDl").hidden=false; });""",
)

# пояснение про веб-версию в меню
script_note = """  <p class="hint" style="text-align:center">Данные не уходят в сеть — всё лежит в этом браузере. Делайте экспорт JSON перед сменой устройства.</p>"""
body = cut(
    body,
    script_note,
    """  <p class="hint" style="text-align:center">Веб-версия: отметки хранятся в вашем браузере и видны только вам. Офлайн-режим и установка на домашний экран есть в версии, размещённой на своём хостинге.</p>""",
)

# ---------- 5. сборка ----------
head = head.replace("<title>Оценка компетенций студента</title>",
                    "<title>Оценка компетенций студента</title>")
out.write_text(head + "\n\n" + body + "\n\n<script>\n" + script.strip() + "\n</script>\n",
               encoding="utf-8")
print("artifact.html:", out.stat().st_size, "байт")

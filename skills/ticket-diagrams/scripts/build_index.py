#!/usr/bin/env python3
"""Build the tabbed index.html for a ticket diagram pack.

Usage: build_index.py <pack-dir>/manifest.json [--mode tabs|bundle|auto] [--default-era ID]

manifest.json:
{
  "title": "Order cancel · PROJ-123",             # header + <title>
  "lang": "en",                                    # optional <html lang>, default "en"
  "note": "Checked against origin/main (...). Not a statement about production.",
  "eras": [{"id": "before", "label": "Before"}, {"id": "after", "label": "After"}],  # optional
  "default_era": "after",                          # optional, defaults to the last era
  "tabs": [
    {"label": "1 · App", "file": "app-cancel.html"},                       # same in every era
    {"label": "Servers", "files": {"before": "servers-before.html",
                                   "after": "servers-after.html"}}         # varies by era
  ],
  "mode": "auto",                                  # optional; CLI flag wins
  "url": "https://host/published/index"           # optional; bundle Copy link points here
}

tabs   = small index, iframe src -> sibling files. Opens from disk, needs the folder.
bundle = every page inlined via srcdoc into one sandboxed file. Send as one file.
auto   = bundle when there are eras or more than 4 distinct pages, else tabs.
"""
import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

CSS = """*{box-sizing:border-box}
:root{--bg:#0b1220;--fg:#e8effb;--muted:#b4c4d9;--line:#2c3c54;--btn:#18273a;--acc:#65d4f0;--ok:#7ce1b8}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.4 system-ui,-apple-system,"Segoe UI",sans-serif;height:100vh;display:flex;flex-direction:column}
header{padding:6px 16px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
h1{font-size:17px;margin:0}
nav{display:flex;gap:6px;flex-wrap:wrap}
button{background:var(--btn);color:var(--fg);border:1px solid var(--line);padding:5px 10px;border-radius:8px;cursor:pointer;font:inherit}
button[aria-selected=true]{border-color:var(--acc);box-shadow:inset 0 0 0 1px var(--acc)}
button:disabled{opacity:.4;cursor:default}
button:focus-visible{outline:2px solid var(--acc);outline-offset:2px}
/* One line by default so diagrams keep the height they were checked at; click to read in full. */
p{margin:0;padding:3px 16px 5px;font-size:12px;color:var(--muted);border-bottom:1px solid var(--line);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;cursor:pointer}
p[aria-expanded=true]{white-space:normal}
iframe{flex:1;min-height:0;width:100%;border:0;display:block;background:var(--bg)}"""

CSP = ("<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; "
       "script-src 'unsafe-inline'; style-src 'unsafe-inline'; frame-src 'self' about:; "
       # srcdoc pages inherit this policy: Archify inlines woff2 fonts and rasterises exports via blob: URLs.
       "font-src data:; img-src data: blob:;\">")

JS = r"""const tabs=TABS,eras=ERAS,docs=DOCS,words=WORDS,base=(PUBLIC_URL||location.href).replace(/#.*/,'');let era=DEFAULT_ERA,tab=0;
// Archify keeps viewer prefs (theme, motion, rail) in localStorage, which sandboxed pages lack: the index keeps them.
const prefs=Object.create(null);
try{const p=JSON.parse(localStorage.getItem('ticket-diagrams-prefs'));if(p&&typeof p==='object')for(const k in p)if(typeof p[k]==='string'&&k.length<=100&&p[k].length<=1000&&Object.keys(prefs).length<50)prefs[k]=p[k]}catch(_){}
// A link copied inside a page reopens it: #tab=<i>&era=<id>&reader=<the page's own hash>.
const h=new URLSearchParams(location.hash.slice(1)),ht=Number(h.get('tab')),he=h.get('era');let reader=h.get('reader');
if(Number.isInteger(ht)&&ht>=0&&ht<tabs.length)tab=ht;
if(eras.some(e=>e.id===he))era=he;
function pick(t){return t.file||t.files[era]}
const attr=s=>s.replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;');
// srcdoc pages have no address of their own, so Archify's Copy link gives about:srcdoc unless told the index's.
function page(f){const tpl=base+'#tab='+tab+(eras.length?'&era='+encodeURIComponent(era):'')+'&reader={state}';
let d=docs[f].replace(/<html(?=[\s>])/i,m=>m+' data-reading-link-template="'+attr(tpl)+'"');
const lit=v=>JSON.stringify(v).replace(/</g,'\\u003c');let head='<script>('+shimStorage+')('+lit(prefs)+')<\/script>';
if(reader){head+='<script>location.hash='+lit(reader)+'<\/script>';reader=null}
if(words){const t=tabs[tab],e=eras.find(x=>x.id===era);
head+='<script>('+captionCopy+')('+lit(base)+','+lit(words.tab+' «'+t.label+'»'+(t.files&&e?', '+words.era+' «'+e.label+'»':''))+','+lit(words)+')<\/script>'}
return d.replace(/<head(?=[\s>])[^>]*>/i,m=>m+head)}
// Runs inside the page (serialized), before Archify reads its prefs; if it can't install, prefs just don't carry over.
function shimStorage(P){const m=Object.assign(Object.create(null),P),post=(k,v)=>parent.postMessage({tdPref:[String(k),v]},'*');
try{Object.defineProperty(window,'localStorage',{configurable:true,value:{getItem:k=>k in m?m[k]:null,
setItem:(k,v)=>{m[k]=String(v);post(k,m[k])},removeItem:k=>{delete m[k];post(k,null)}}})}catch(_){}}
// Runs inside the page (serialized): the host drops the link's #, so the copy says in words where to go.
function captionCopy(B,C,W){B=new URL(B).href;
const lab=id=>{const n=[...document.querySelectorAll('[data-node-id]')].find(e=>e.dataset.nodeId===id);return(n&&n.dataset.nodeLabel||id).replace(/\s+/g,' ').trim()};
const fix=t=>{if(typeof t!=='string'||t.indexOf(B+'#')!==0)return t;
const s=new URLSearchParams(new URLSearchParams(t.slice(B.length+1)).get('reader')||''),f=s.get('focus'),r=(s.get('route')||'').split('~'),l=s.get('lens'),rel=s.get('relation'),rc=/^(up|down)stream$/.test(s.get('reach'))&&W[s.get('reach')];
return B+' — '+C+(f?', '+W.node+' «'+lab(f)+'»'+(rc?' ('+rc+')':''):r.length===2?', '+W.route+' «'+lab(r[0])+'» → «'+lab(r[1])+'»':l?', '+W.lens+' '+l:rel?', '+W.relation+' «'+rel+'»':'')};
const c=navigator.clipboard;if(c&&c.writeText){const w=c.writeText.bind(c);c.writeText=t=>w(fix(t))}
// Archify's fallback copies a selected textarea; setting .value drops the selection, so reselect.
const x=document.execCommand.bind(document);document.execCommand=function(n){const a=document.activeElement;
if(n==='copy'&&a&&a.tagName==='TEXTAREA'){a.value=fix(a.value);a.select()}return x.apply(null,arguments)}}
function show(){const t=tabs[tab],f=pick(t),v=document.getElementById('v');
if(docs)v.srcdoc=page(f);else v.src=f;
document.querySelectorAll('[data-tab]').forEach(b=>b.setAttribute('aria-selected',+b.dataset.tab===tab));
document.querySelectorAll('[data-era]').forEach(b=>{b.setAttribute('aria-selected',b.dataset.era===era);b.disabled=!!t.file});}
document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{tab=+b.dataset.tab;show()});
document.querySelectorAll('[data-era]').forEach(b=>b.onclick=()=>{era=b.dataset.era;show()});
const n=document.querySelector('p[role=button]');
if(n){const t=()=>n.setAttribute('aria-expanded',n.getAttribute('aria-expanded')!=='true');
n.onclick=t;n.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();t()}}}
if(docs)addEventListener('message',e=>{const p=e.data&&typeof e.data==='object'&&e.data.tdPref;
if(e.source!==document.getElementById('v').contentWindow||!Array.isArray(p)||p.length!==2)return;const[k,val]=p;
if(typeof k!=='string'||k.length>100||!(val===null||typeof val==='string'&&val.length<=1000))return;
if(val===null)delete prefs[k];else if(k in prefs||Object.keys(prefs).length<50)prefs[k]=val;
try{localStorage.setItem('ticket-diagrams-prefs',JSON.stringify(prefs))}catch(_){}});
show();"""

WORDS_EN = {"tab": "tab", "era": "era", "node": "node", "route": "route", "lens": "lens", "relation": "relation",
            "upstream": "upstream", "downstream": "downstream"}
WORDS_RU = {"tab": "вкладка", "era": "эпоха", "node": "узел", "route": "маршрут", "lens": "линза", "relation": "связь",
            "upstream": "вверх по потоку", "downstream": "вниз по потоку"}


def js_literal(value):
    # `<` escaped so an inlined page can never close our <script> early.
    return json.dumps(value, ensure_ascii=False).replace("<", "\\u003c")


def build(manifest_path, mode=None, default_era=None):
    try:
        return _build(manifest_path, mode, default_era)
    except (KeyError, TypeError, AttributeError, ValueError, OSError) as e:  # JSONDecodeError is a ValueError
        sys.exit(f"manifest {manifest_path}: {type(e).__name__}: {e}")


def _build(manifest_path, mode, default_era):
    manifest_path = Path(manifest_path)
    pack = manifest_path.parent
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    eras = m.get("eras") or []
    tabs = m.get("tabs") or sys.exit("manifest needs at least one tab")
    if not isinstance(eras, list) or not isinstance(tabs, list):
        sys.exit("manifest: 'eras' and 'tabs' must be lists")
    era_ids = [e["id"] for e in eras]
    if len(set(era_ids)) != len(era_ids):
        sys.exit(f"duplicate era ids: {era_ids}")

    files = []
    for t in tabs:
        if ("file" in t) == ("files" in t):
            sys.exit(f"tab {t.get('label')!r}: give exactly one of 'file' or 'files'")
        if "files" in t:
            if not eras or set(t["files"]) != set(era_ids):
                sys.exit(f"tab {t['label']!r}: 'files' keys must be exactly the era ids {era_ids}")
            files += t["files"].values()
        else:
            files.append(t["file"])
    files = list(dict.fromkeys(files))
    for f in files:
        if Path(f).is_absolute() or ".." in Path(f).parts:
            sys.exit(f"page must be a path inside the pack: {f}")
        if Path(f) == Path("index.html"):
            sys.exit(f"index.html is the output, not a page: {f}")
        if not (pack / f).is_file():
            sys.exit(f"missing page: {pack / f}")
        # A symlink must not pull a file from outside the pack into a shared bundle.
        if pack.resolve() not in (pack / f).resolve().parents:
            sys.exit(f"page resolves outside the pack: {f}")

    url = m.get("url")
    if url is not None and not (isinstance(url, str) and len(url) < 3900 and "#" not in url and "{state}" not in url
                                and urlsplit(url).scheme in ("http", "https", "file")
                                and not (urlsplit(url).username or urlsplit(url).password)):
        sys.exit(f"manifest 'url' must be an http(s) or file address without credentials, '#' or '{{state}}': {url!r}")

    mode = mode or m.get("mode", "auto")
    if mode == "auto":
        mode = "bundle" if eras or len(files) > 4 else "tabs"
    if mode not in ("tabs", "bundle"):
        sys.exit(f"unknown mode: {mode}")

    docs = None
    if mode == "bundle":
        docs = {}
        for f in files:
            try:
                docs[f] = (pack / f).read_text(encoding="utf-8")
            except UnicodeDecodeError:
                sys.exit(f"page is not UTF-8: {f}")
    if (default_era or m.get("default_era")) and not eras:
        sys.exit("default era given, but the manifest has no eras")
    default_era = default_era or m.get("default_era") or (era_ids[-1] if era_ids else None)
    if eras and default_era not in era_ids:
        sys.exit(f"default_era {default_era!r} is not one of {era_ids}")

    esc = html.escape
    era_nav = "".join(f'<button data-era="{esc(e["id"])}">{esc(e["label"])}</button>' for e in eras)
    tab_nav = "".join(f'<button role="tab" data-tab="{i}">{esc(t["label"])}</button>' for i, t in enumerate(tabs))
    # ponytail: claude.ai is the one host known to drop # and ? before the artifact frame; add others as found.
    words = None
    if url and urlsplit(url).hostname == "claude.ai":
        words = WORDS_RU if m.get("lang", "en").lower().startswith("ru") else WORDS_EN
    # One pass: a label containing "DOCS" must not be rewritten by a later substitution.
    subs = {"TABS": tabs, "ERAS": eras, "DEFAULT_ERA": default_era, "DOCS": docs, "PUBLIC_URL": url, "WORDS": words}
    script = re.sub(r"\b(TABS|ERAS|DEFAULT_ERA|DOCS|PUBLIC_URL|WORDS)\b", lambda x: js_literal(subs[x.group()]), JS)
    sandbox = ' sandbox="allow-scripts allow-downloads"' if docs else ""
    out = (
        f'<!doctype html><html lang="{esc(m.get("lang", "en"))}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        + (CSP if docs else "")
        + f"<title>{esc(m['title'])}</title><style>{CSS}</style></head><body>"
        f"<header><h1>{esc(m['title'])}</h1>"
        + (f"<nav>{era_nav}</nav>" if eras else "")
        + f"<nav role=\"tablist\">{tab_nav}</nav></header>"
        + (f'<p tabindex="0" role="button" aria-expanded="false" title="{esc(m["note"])}">{esc(m["note"])}</p>'
           if m.get("note") else "")
        + f'<iframe id="v" title="{esc(m["title"])}"{sandbox}></iframe>'
        f"<script>{script}</script></body></html>"
    )
    target = pack / "index.html"
    target.write_text(out, encoding="utf-8")
    return target, mode, len(files), target.stat().st_size


def _selfcheck():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        for n in ("a.html", "b1.html", "b2.html"):
            (d / n).write_text(f"<html><script>x='</script>'</script>{n}</html>")
        man = {"title": "T <x>", "note": "n", "tabs": [{"label": "A", "file": "a.html"}]}
        (d / "manifest.json").write_text(json.dumps(man))
        _, mode, n, _ = build(d / "manifest.json")
        assert (mode, n) == ("tabs", 1)
        assert "srcdoc" not in (d / "index.html").read_text().split("<script>")[0]
        man["eras"] = [{"id": "b", "label": "До"}, {"id": "a", "label": "После"}]
        man["tabs"].append({"label": "DOCS TABS", "files": {"b": "b1.html", "a": "b2.html"}})
        (d / "manifest.json").write_text(json.dumps(man))
        _, mode, n, _ = build(d / "manifest.json")
        out = (d / "index.html").read_text()
        assert (mode, n) == ("bundle", 3)
        assert out.count("</script>") == 1, "inlined page leaked a </script>"
        assert "T &lt;x&gt;" in out and "font-src data:" in out
        assert '"label": "DOCS TABS"' in out, "placeholder substituted inside a label"
        assert "base=(null||location.href)" in out, "copy-link base not substituted"
        for url in ("https://example.test/a?x=1&y=$1", "file:///tmp/p/index.html"):
            man["url"] = url
            (d / "manifest.json").write_text(json.dumps(man))
            build(d / "manifest.json")
            assert f'base=("{url}"||' in (d / "index.html").read_text()
            assert "words=null" in (d / "index.html").read_text(), "caption outside claude.ai"
        man["url"] = "https://claude.ai/artifact/X"
        (d / "manifest.json").write_text(json.dumps(man))
        build(d / "manifest.json")
        assert 'words={"tab": "tab"' in (d / "index.html").read_text(), "no caption on claude.ai"
        man["lang"] = "ru"
        (d / "manifest.json").write_text(json.dumps(man))
        build(d / "manifest.json")
        assert 'words={"tab": "вкладка"' in (d / "index.html").read_text()
        assert JS.index("'+shimStorage+'") < JS.index("'+captionCopy+'"), "storage shim must run first in a page"
        shim = JS[JS.index("function shimStorage"):JS.index("function captionCopy")]
        assert "<" not in shim, "shimStorage is injected verbatim into pages: no '<' allowed"
        cap = JS[JS.index("function captionCopy"):JS.index("function show")]
        assert "<" not in cap, "captionCopy is injected verbatim into pages: no '<' allowed"

        def rejects(manifest, needle, **kw):
            (d / "manifest.json").write_text(manifest if isinstance(manifest, str) else json.dumps(manifest))
            try:
                build(d / "manifest.json", **kw)
            except SystemExit as e:
                assert needle in str(e), (needle, str(e))
                return
            raise AssertionError(f"accepted: {needle}")

        (d / "latin1.html").write_bytes("caf\xe9".encode("latin-1"))
        one = lambda f: {"title": "T", "tabs": [{"label": "A", "file": f}]}
        with tempfile.TemporaryDirectory() as outside:
            (Path(outside) / "secret.html").write_text("secret")
            try:
                (d / "leak.html").symlink_to(Path(outside) / "secret.html")
                rejects(one("leak.html"), "outside the pack")
            except OSError:  # Windows without symlink rights
                print("symlink case skipped")
        rejects(one("index.html"), "index.html")
        rejects(one("latin1.html"), "not UTF-8", mode="bundle")
        rejects("{not json", "manifest")
        rejects({"tabs": [{"label": "A", "file": "a.html"}]}, "title")
        rejects({"title": "T", "tabs": [{"file": "a.html"}]}, "label")
        rejects({"title": "T", "eras": "x", "tabs": [{"label": "A", "file": "a.html"}]}, "must be lists")
        rejects(one("a.html"), "no eras", default_era="b")
        rejects({**one("a.html"), "default_era": "b"}, "no eras")
        for bad in ("javascript:alert(1)", "https://a.test/{state}", "https://u:p@a.test/", "https://a.test/#x", 5,
                    "https://a.test/" + "x" * 3900):
            rejects({**one("a.html"), "url": bad}, "url")
        try:
            build(d / "nope.json")
            raise AssertionError("accepted a missing manifest")
        except SystemExit as e:
            assert "nope.json" in str(e)
    print("selfcheck ok")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("manifest", nargs="?")
    ap.add_argument("--mode", choices=["tabs", "bundle", "auto"])
    ap.add_argument("--default-era")
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()
    if a.selfcheck:
        _selfcheck()
        sys.exit()
    if not a.manifest:
        ap.error("manifest is required")
    path, mode, n, size = build(a.manifest, a.mode, a.default_era)
    print(json.dumps({"index": str(path), "mode": mode, "pages": n, "bytes": size}, ensure_ascii=False))

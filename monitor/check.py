#!/usr/bin/env python3
"""Synthetic check for one site, driven by monitor.yaml.

Checks the main URL (and any `pages`): HTTP status (default 200), no 5xx,
<title> regex, required strings (`contains`), required sections
(`selectors`: #id, .class, tag, tag#id, tag.class) and required links
(`links`, present in the HTML; same-host links must also answer < 400 unless
`check_links: false`). Retries `attempts` times (15 s apart) before declaring
the site down. Exit 0 = up, 1 = down. Writes result.json.
"""
import json, re, sys, time, urllib.request, urllib.error, urllib.parse
from html.parser import HTMLParser
import yaml

UA = "ojardila-site-monitor/1.0 (+https://github.com/ojardila/site-monitor)"

class Doc(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title, self._t = "", False
        self.ids, self.classes, self.tags, self.links = set(), set(), set(), set()
        self.tag_id, self.tag_class = set(), set()
    def handle_starttag(self, tag, attrs):
        a = dict(attrs); self.tags.add(tag)
        if a.get("id"):
            self.ids.add(a["id"]); self.tag_id.add(f"{tag}#{a['id']}")
        for c in (a.get("class") or "").split():
            self.classes.add(c); self.tag_class.add(f"{tag}.{c}")
        if tag == "a" and a.get("href"):
            self.links.add(a["href"])
        if tag == "title":
            self._t = True
    def handle_endtag(self, tag):
        if tag == "title":
            self._t = False
    def handle_data(self, d):
        if self._t:
            self.title += d

def has_selector(doc, sel):
    sel = sel.strip()
    if sel.startswith("#"): return sel[1:] in doc.ids
    if sel.startswith("."): return sel[1:] in doc.classes
    if "#" in sel: return sel in doc.tag_id
    if "." in sel: return sel in doc.tag_class
    return sel in doc.tags

def fetch(url, timeout):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(5_000_000).decode("utf-8", "replace"), r.geturl()
    except urllib.error.HTTPError as e:
        return e.code, "", url
    except Exception as e:  # DNS, TLS, timeout, refused
        return 0, f"{type(e).__name__}: {e}", url

def check_page(page, timeout, base):
    url = urllib.parse.urljoin(base, page["url"])
    status, body, final = fetch(url, timeout)
    want = page.get("status", 200)
    if status == 0:
        return [f"{url}: sin respuesta ({body[:120]})"]
    if status >= 500:
        return [f"{url}: error del servidor HTTP {status}"]
    if status != want:
        return [f"{url}: HTTP {status} (esperado {want})"]
    errs = []
    doc = Doc(); doc.feed(body)
    t = page.get("title")
    if t and not re.search(t, doc.title.strip(), re.I):
        errs.append(f"{url}: título '{doc.title.strip()[:80]}' no coincide con /{t}/")
    for s in page.get("contains") or []:
        if s not in body:
            errs.append(f"{url}: falta el texto '{s}'")
    for s in page.get("selectors") or []:
        if not has_selector(doc, s):
            errs.append(f"{url}: falta la sección '{s}'")
    absolute = {urllib.parse.urljoin(final, h) for h in doc.links}
    for l in page.get("links") or []:
        target = urllib.parse.urljoin(final, l)
        if l not in doc.links and target not in absolute:
            errs.append(f"{url}: falta el enlace '{l}'"); continue
        if page.get("check_links", True) and target.startswith("http") and \
           urllib.parse.urlparse(target).netloc == urllib.parse.urlparse(final).netloc:
            st, _, _ = fetch(target, timeout)
            if st == 0 or st >= 400:
                errs.append(f"{url}: el enlace '{l}' responde {st or 'sin respuesta'}")
    return errs

def main(path):
    cfg = yaml.safe_load(open(path))
    timeout, attempts = cfg.get("timeout", 20), cfg.get("attempts", 3)
    main_page = {k: v for k, v in cfg.items() if k != "pages"}
    pages = [main_page] + (cfg.get("pages") or [])
    errs = []
    for i in range(attempts):
        errs = [e for p in pages for e in check_page(p, timeout, cfg["url"])]
        if not errs:
            break
        if i < attempts - 1:
            time.sleep(15)
    res = {"name": cfg["name"], "url": cfg["url"], "ok": not errs, "errors": errs}
    json.dump(res, open("result.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0 if not errs else 1

if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "monitor.yaml"))

from __future__ import annotations
import re, requests

API="https://commons.wikimedia.org/w/api.php"
def _plain(value): return re.sub(r"<[^>]+>","",value or "").strip()
def search_commons(query:str,limit:int=6,transport=None):
    get=transport or requests.get
    search=get(API,params={"action":"query","generator":"search","gsrsearch":f"{query} automobile","gsrnamespace":6,"gsrlimit":limit,"prop":"imageinfo","iiprop":"url|extmetadata","iiurlwidth":900,"format":"json","origin":"*"},headers={"User-Agent":"DriveScope-CourseProject/1.0"},timeout=12)
    data=search.json(); items=[]
    for page in data.get("query",{}).get("pages",{}).values():
        ii=(page.get("imageinfo") or [{}])[0]; meta=ii.get("extmetadata",{})
        license_name=_plain(meta.get("LicenseShortName",{}).get("value")); source=ii.get("descriptionurl")
        if not license_name or not source: continue
        items.append({"url":ii.get("url"),"thumbnail_url":ii.get("thumburl",ii.get("url")),"source_kind":"wikimedia","view_hint":"未标注视角","author":_plain(meta.get("Artist",{}).get("value")) or "未知作者","license_name":license_name,"license_url":_plain(meta.get("LicenseUrl",{}).get("value")),"source_page":source,"modified":False})
    return items

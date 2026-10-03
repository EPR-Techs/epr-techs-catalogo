from pathlib import Path
import json, re, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
URLS=ROOT/'data/product_urls.json'
CACHE=ROOT/'data/image_cache.json'
HEADERS={'User-Agent':'Mozilla/5.0 (compatible; EPRTechsCatalog/1.0)'}
TIMEOUT=12


def extract_image(url):
    try:
        r=requests.get(url,headers=HEADERS,timeout=TIMEOUT)
        if r.status_code>=400: return None
        soup=BeautifulSoup(r.text,'html.parser')
        # Solo la ficha indicada; no realiza búsquedas ni consultas a motores de imágenes.
        for attrs in [
            {'property':'og:image'}, {'name':'twitter:image'}, {'itemprop':'image'}
        ]:
            tag=soup.find('meta',attrs=attrs)
            if tag and tag.get('content'):
                return urljoin(r.url,tag['content'])
        # JSON-LD de producto
        for s in soup.find_all('script',type='application/ld+json'):
            try:
                obj=json.loads(s.string or s.get_text())
                objs=obj if isinstance(obj,list) else [obj]
                for o in objs:
                    if isinstance(o,dict) and o.get('image'):
                        im=o['image'][0] if isinstance(o['image'],list) else o['image']
                        if isinstance(im,str): return urljoin(r.url,im)
            except Exception: pass
        # Fallback: imágenes de la propia ficha que parezcan de producto.
        for img in soup.find_all('img'):
            src=img.get('src') or img.get('data-src') or img.get('data-lazy-src')
            if not src: continue
            alt=(img.get('alt') or '').lower()
            if any(x in alt for x in ['logo','icon','facebook','instagram','whatsapp']): continue
            full=urljoin(r.url,src)
            if full.startswith('http'): return full
    except Exception:
        return None
    return None


def main():
    urls=json.loads(URLS.read_text(encoding='utf8')) if URLS.exists() else {}
    cache=json.loads(CACHE.read_text(encoding='utf8')) if CACHE.exists() else {}
    todo=[(k,u) for k,u in urls.items() if u and k not in cache]
    print(f'Fichas pendientes de imagen: {len(todo)}')
    if not todo: return
    with ThreadPoolExecutor(max_workers=12) as ex:
        futs={ex.submit(extract_image,u):(k,u) for k,u in todo}
        done=0
        for fut in as_completed(futs):
            k,u=futs[fut]
            im=fut.result()
            if im: cache[k]=im
            done+=1
            if done%100==0: print(done)
    CACHE.write_text(json.dumps(cache,ensure_ascii=False,indent=2),encoding='utf8')
    print(f'Imágenes encontradas/acumuladas: {len(cache)}')

if __name__=='__main__': main()

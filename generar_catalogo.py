from pathlib import Path
import json, math, re, shutil, time
import pandas as pd

ROOT = Path(__file__).resolve().parent
MASTER = ROOT / 'data' / 'catalogo_maestro.xls'
MASTER_XLSX = ROOT / 'data' / 'catalogo_maestro.xlsx'
URLS_FILE = ROOT / 'data' / 'product_urls.json'
IMAGE_CACHE = ROOT / 'data' / 'image_cache.json'
TEMPLATE = ROOT / 'index.template.html'
OUTPUT = ROOT / 'index.html'

# Tipo de cambio editable. Para el catálogo actual se toma 18.3688 MXN/USD,
# referencia publicada por Banco de México para 03/10/2026.
USD_MXN = 18.3688
IVA = 0.16

# Markup sobre costo antes de IVA. Se usa una estructura por nivel de costo para
# generar un PVP inicial comercial; el precio final se muestra ya con IVA.
def markup(cost_mxn: float) -> float:
    if cost_mxn < 500: return 0.30
    if cost_mxn < 1500: return 0.25
    if cost_mxn < 5000: return 0.22
    if cost_mxn < 10000: return 0.18
    if cost_mxn < 25000: return 0.15
    if cost_mxn < 50000: return 0.12
    return 0.10

def round_pvp(value: float) -> float:
    if value < 1000: step = 50
    elif value < 5000: step = 100
    elif value < 20000: step = 250
    elif value < 50000: step = 500
    else: step = 1000
    return float(int(value / step + 0.5) * step)

def clean(v):
    if pd.isna(v): return None
    if isinstance(v, float) and v.is_integer(): return int(v)
    return v

def norm_key(v):
    return str(v).strip().upper() if v is not None else ''

def load_json(path, default):
    if path.exists():
        try: return json.loads(path.read_text(encoding='utf-8'))
        except Exception: pass
    return default

def main():
    if not MASTER.exists():
        raise SystemExit(f'No existe {MASTER}')

    source = MASTER if MASTER.exists() else MASTER_XLSX
    try:
        df = pd.read_excel(source, sheet_name=0, header=1, dtype=object)
    except ImportError:
        # Entornos sin xlrd: si hay LibreOffice disponible, convierte el XLS temporalmente.
        import subprocess, tempfile
        if source.suffix.lower() == '.xls':
            tmp = Path(tempfile.mkdtemp())
            subprocess.run(['libreoffice','--headless','--convert-to','xlsx','--outdir',str(tmp),str(source)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            converted = tmp / (source.stem + '.xlsx')
            df = pd.read_excel(converted, sheet_name=0, header=1, dtype=object)
        else:
            raise
    df.columns = [str(c).strip() for c in df.columns]

    # Solo filas reales de producto. El XLS contiene después de los productos
    # una sección de políticas de garantía sin marca/código/precio.
    required = ['Clave', 'Codigo de Fabricante', 'Marca', 'Grupo', 'Descripcion del articulo', 'Precio', 'Moneda']
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise SystemExit('Faltan columnas: ' + ', '.join(missing))

    url_map = load_json(URLS_FILE, {})
    image_map = load_json(IMAGE_CACHE, {})

    products=[]
    for _, r in df.iterrows():
        clave = clean(r.get('Clave'))
        fab = clean(r.get('Codigo de Fabricante'))
        marca = clean(r.get('Marca'))
        grupo = clean(r.get('Grupo'))
        desc = clean(r.get('Descripcion del articulo'))
        precio = clean(r.get('Precio'))
        moneda = clean(r.get('Moneda'))
        if not all([clave, fab, marca, grupo, desc]) or precio is None or moneda is None:
            continue
        try: precio=float(precio)
        except: continue
        moneda_s=str(moneda).strip()
        costo_mxn = precio * USD_MXN if 'dolar' in moneda_s.lower() else precio
        pvp = round_pvp(costo_mxn * (1 + markup(costo_mxn)) * (1 + IVA))
        k=norm_key(clave)
        image = image_map.get(k)
        products.append({
            'clave': str(clave), 'fabricante': str(fab), 'marca': str(marca), 'grupo': str(grupo),
            'descripcion': str(desc), 'precio': precio, 'moneda': moneda_s,
            'costoMxn': round(costo_mxn,2), 'pvpIva': pvp,
            'markup': markup(costo_mxn), 'iva': IVA,
            'promos': clean(r.get('Promos')), 'diasGtia': clean(r.get('Dias de Gtia')),
            'mesesGtia': clean(r.get('Meses de Gtia')), 'aniosGtia': clean(r.get('Anios de Gtia')),
            'disp': clean(r.get('Disp')) or 0, 'dispCD': clean(r.get('Disp CD')) or 0,
            'upc': clean(r.get('UPC')), 'url': url_map.get(k), 'image': image
        })

    groups=sorted({p['grupo'] for p in products if p['grupo']})
    brands=sorted({p['marca'] for p in products if p['marca']})
    catalog={'products':products,'groups':groups,'brands':brands,
             'meta':{'generatedAt':time.strftime('%Y-%m-%d %H:%M:%S'), 'usdMxn':USD_MXN, 'iva':IVA}}

    html=TEMPLATE.read_text(encoding='utf-8')
    start=html.index('const CATALOG=') + len('const CATALOG=')
    end=html.index('\n', start)
    new_json=json.dumps(catalog, ensure_ascii=False, separators=(',',':'))
    html=html[:start] + new_json + ';' + html[end:]
    # El template trae funciones de búsqueda web; se sustituyen por una versión local.
    js_start=html.index("let DATA=[],cache={};")
    js_end=html.index('</script>', js_start)
    local_js=r'''let DATA=[],cache={};
const $=x=>document.getElementById(x);
const money=(v,c)=>v==null?'—':new Intl.NumberFormat('es-MX',{minimumFractionDigits:2,maximumFractionDigits:2}).format(v)+' '+(c||'');
const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;"}[m]));
function box(p){return p.image?`<img src="${esc(p.image)}" alt="${esc(p.descripcion)}" onerror="this.parentElement.innerHTML='<div class=ph>▧</div>'">`:'<div class="ph">▧</div>'}
function card(p,i){return `<article class="card"><div class="pic">${p.grupo?`<span class=tag>${esc(p.grupo)}</span>`:''}${box(p)}</div><div class=body><div class=group>${esc(p.marca||'')}</div><div class=title>${esc(p.descripcion||'')}</div><div class=code>${esc(p.clave||'')} · Fab. ${esc(p.fabricante||'')}</div><div class=desc>${esc(p.descripcion||'')}</div><div class="cost">Costo: ${money(p.costoMxn,'MXN')} + IVA</div><div class="price">PVP sugerido: ${money(p.pvpIva,'MXN')} <small>IVA incluido</small></div><div class=stock>Disponible: ${Number(p.disp||0)} · CEDIS: ${Number(p.dispCD||0)}</div><div class=actions><button class="btn primary" onclick="openDetail(${i})">Ver producto</button>${p.url?`<a class=btn href="${esc(p.url)}" target=_blank rel=noopener>Ficha ↗</a>`:''}</div></div></article>`}
function render(){let q=$('q').value.toLowerCase().trim(),g=$('group').value,b=$('brand').value,s=$('stock').value;let list=DATA.map((p,i)=>({p,i})).filter(x=>{let p=x.p,hay=[p.clave,p.fabricante,p.marca,p.grupo,p.descripcion].join(' ').toLowerCase();return(!q||hay.includes(q))&&(!g||p.grupo===g)&&(!b||p.marca===b)&&(!s||(s==='yes'?((p.disp||0)+(p.dispCD||0)>0):((p.disp||0)+(p.dispCD||0)<=0)))});$('count').textContent=list.length;$('grid').innerHTML=list.length?list.map(x=>card(x.p,x.i)).join(''):'<div class=empty>No hay productos que coincidan con los filtros.</div>'}
function openDetail(i){let p=DATA[i];$('dimg').innerHTML=box(p);$('dbody').innerHTML=`<div class=group>${esc(p.grupo)}</div><h2>${esc(p.descripcion)}</h2><div class=kv><b>Clave</b><span>${esc(p.clave)}</span></div><div class=kv><b>Fabricante</b><span>${esc(p.fabricante)}</span></div><div class=kv><b>Marca</b><span>${esc(p.marca)}</span></div><div class=kv><b>Costo</b><span>${money(p.costoMxn,'MXN')} + IVA</span></div><div class=kv><b>PVP sugerido</b><span><strong>${money(p.pvpIva,'MXN')} IVA incluido</strong></span></div><div class=kv><b>Existencia</b><span>${Number(p.disp||0)} · CEDIS ${Number(p.dispCD||0)}</span></div><div class=kv><b>Garantía</b><span>${[p.diasGtia&&p.diasGtia+' días',p.mesesGtia&&p.mesesGtia+' meses',p.aniosGtia&&p.aniosGtia+' años'].filter(Boolean).join(' / ')||'No indicada'}</span></div>${p.url?`<p><a class="btn primary" href="${esc(p.url)}" target=_blank rel=noopener>Abrir ficha completa ↗</a></p>`:''}<div class="note">PVP sugerido para venta al público. Se calcula a partir del costo del archivo maestro, conversión USD/MXN configurada y una estructura de margen comercial; debe revisarse frente a competencia y promociones antes de publicar una cotización.</div>`;$('modal').classList.add('open')}
$('close').onclick=()=>$('modal').classList.remove('open');$('modal').onclick=e=>{if(e.target===$('modal'))$('modal').classList.remove('open')};
['q','group','brand','stock'].forEach(id=>$(id).addEventListener(id==='q'?'input':'change',render));$('clear').onclick=()=>{$('q').value='';$('group').value='';$('brand').value='';$('stock').value='';render()};
const d=CATALOG; DATA=d.products; $('groups').textContent=d.groups.length; $('brands').textContent=d.brands.length; $('links').textContent=DATA.filter(x=>x.url).length; d.groups.forEach(x=>{let o=document.createElement('option');o.value=o.textContent=x;$('group').appendChild(o)}); d.brands.forEach(x=>{let o=document.createElement('option');o.value=o.textContent=x;$('brand').appendChild(o)}); render();
'''
    html=html[:js_start]+local_js+html[js_end:]
    OUTPUT.write_text(html,encoding='utf-8')

    # Persist URLs already known; this file is the stable URL registry for future XLS updates.
    URLS_FILE.write_text(json.dumps({k:v for k,v in url_map.items() if v},ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Catálogo generado: {len(products)} productos, {len(groups)} grupos, {len(brands)} marcas.')
    print(f'Con ficha web: {sum(bool(p["url"]) for p in products)}')
    print(f'Con imagen cacheada: {sum(bool(p["image"]) for p in products)}')

if __name__=='__main__': main()

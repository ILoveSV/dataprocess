from pathlib import Path
import json, re
import pypdfium2 as pdfium
from PIL import Image, ImageDraw
import pdfplumber
ROOT=Path(__file__).resolve().parent
out=ROOT/'qa';out.mkdir(exist_ok=True)
pdf=pdfium.PdfDocument(str(ROOT/'book.pdf'))
imgs=[]
for i,page in enumerate(pdf):
    im=page.render(scale=100/72).to_pil().convert('RGB');im.save(out/f'page-{i+1:02}.png');imgs.append(im)
for start in range(0,len(imgs),4):
    sheet=Image.new('RGB',(1700,2420),'#dddddd');draw=ImageDraw.Draw(sheet)
    for j,im in enumerate(imgs[start:start+4]):
        x=(j%2)*850;y=(j//2)*1210
        sheet.paste(im,(x,y+30));draw.text((x+15,y+8),f'Page {start+j+1}',fill='black')
    sheet.save(out/f'sheet-{start//4+1:02}.png')
report=[]
with pdfplumber.open(ROOT/'book.pdf') as p:
    for i,page in enumerate(p.pages):
        text=page.extract_text() or ''
        chars=page.chars
        outside=[c for c in chars if c['x0']<42 or c['x1']>page.width-40 or c['top']<12 or c['bottom']>page.height-12]
        report.append({'page':i+1,'chars':len(text),'outside':len(outside),'start':text[:100],'end':text[-150:]})
    (ROOT/'pdf_text.txt').write_text('\n\n'.join((x.extract_text() or '') for x in p.pages),encoding='utf-8')
(ROOT/'qa_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'pages':len(pdf),'edge_issues':[r for r in report if r['outside']],'short_pages':[(r['page'],r['chars']) for r in report if r['chars']<350]},ensure_ascii=False))


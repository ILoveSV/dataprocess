"""Render the review report with the project's restrained Chinese document style."""
from pathlib import Path
import re,json
from docx import Document
from docx.shared import Inches,Pt,RGBColor
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
ROOT=Path(__file__).resolve().parents[1]
src=ROOT/'results/thesis_followup_20260915/研究进展与间隙检出分析报告_20260918.md'
out=ROOT/'output/documents/研究进展与间隙检出分析报告_20260918.docx'
doc=Document();sec=doc.sections[0]
sec.page_width=Inches(8.5);sec.page_height=Inches(11)
sec.top_margin=Inches(.67);sec.bottom_margin=Inches(.67);sec.left_margin=Inches(.75);sec.right_margin=Inches(.75)
sec.header_distance=Inches(.28);sec.footer_distance=Inches(.28)
for name,size in [('Normal',11),('Title',21),('Heading 1',16),('Heading 2',13),('Caption',9)]:
 s=doc.styles[name];s.font.name='Calibri';s.font.size=Pt(size);s.font.color.rgb=RGBColor(0,0,0)
 s.element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'宋体' if name in ['Normal','Caption'] else '黑体')
 s.paragraph_format.line_spacing=1.15;s.paragraph_format.space_after=Pt(7)
 s.paragraph_format.widow_control=True
for style in doc.styles:
 for border in list(style.element.iter(qn('w:pBdr'))):border.getparent().remove(border)
doc.styles['Heading 1'].paragraph_format.space_before=Pt(0)
hp=sec.header.paragraphs[0];hp.text='毕业论文研究进展    数值核验与既有数据复核';hp.style='Caption'
fp=sec.footer.paragraphs[0];fp.alignment=2;fp.add_run('2026年9月18日    第 ')
fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE');fp._p.append(fld);fp.add_run(' 页')
for r in fp.runs:r.font.size=Pt(9)
def rich(p,text):
 for part in re.split(r'(\*\*.*?\*\*|\[.*?\]\(.*?\))',text):
  if part.startswith('**'):p.add_run(part[2:-2]).bold=True
  elif part.startswith('[') and '](' in part:
   m=re.fullmatch(r'\[(.*?)\]\((.*?)\)',part)
   if not m:p.add_run(part);continue
   target=m[2]
   if not target.startswith('http'):target=(src.parent/target).resolve().as_uri()
   rel=p.part.relate_to(target,'http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink',is_external=True)
   h=OxmlElement('w:hyperlink');h.set(qn('r:id'),rel);r=OxmlElement('w:r');rp=OxmlElement('w:rPr');col=OxmlElement('w:color');col.set(qn('w:val'),'175A8A');rp.append(col);r.append(rp);t=OxmlElement('w:t');t.text=m[1];r.append(t);h.append(r);p._p.append(h)
  else:p.add_run(part.replace('`',''))
lines=src.read_text(encoding='utf8').splitlines();i=0;tables=0
while i<len(lines):
 line=lines[i].strip();i+=1
 if not line:continue
 if line=='<!-- PAGE -->':doc.add_page_break();continue
 if line.startswith('# '):rich(doc.add_paragraph(style='Title'),line[2:]);continue
 if line.startswith('## '):rich(doc.add_paragraph(style='Heading 1'),line[3:]);continue
 if line.startswith('### '):rich(doc.add_paragraph(style='Heading 2'),line[4:]);continue
 if line.startswith('|'):
  rows=[line]
  while i<len(lines) and lines[i].strip().startswith('|'):rows.append(lines[i].strip());i+=1
  rows=[r for r in rows if not re.fullmatch(r'[| :\-]+',r)]
  vals=[[x.strip() for x in r.strip('|').split('|')] for r in rows];n=len(vals[0]);assert all(len(v)==n for v in vals)
  widths={3:[1.8,2.6,2.6],4:[1.45,1.85,1.85,1.85],5:[1.0,1.5,1.5,1.5,1.5],6:[.70,.8,1.45,1.45,1.30,1.30]}.get(n,[7/n]*n)
  t=doc.add_table(rows=len(vals),cols=n);t.autofit=False
  for col,w in zip(t.columns,widths):col.width=Inches(w)
  for rr,row in enumerate(vals):
   tr=t.rows[rr]._tr.get_or_add_trPr();tr.append(OxmlElement('w:cantSplit'))
   if rr==0:tr.append(OxmlElement('w:tblHeader'))
   for cc,txt in enumerate(row):
    cell=t.cell(rr,cc);cell.width=Inches(widths[cc]);cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
    pr=cell._tc.get_or_add_tcPr();b=OxmlElement('w:tcBorders')
    for side in ['top','left','bottom','right']:
     v=OxmlElement('w:'+side);v.set(qn('w:val'),'single');v.set(qn('w:sz'),'4');v.set(qn('w:color'),'D9D9D9');b.append(v)
    pr.append(b);mar=OxmlElement('w:tcMar')
    for side in ['top','left','bottom','right']:
     v=OxmlElement('w:'+side);v.set(qn('w:w'),'85');v.set(qn('w:type'),'dxa');mar.append(v)
    pr.append(mar)
    if rr==0:
     sh=OxmlElement('w:shd');sh.set(qn('w:fill'),'EAEFF3');pr.append(sh)
    p=cell.paragraphs[0];rich(p,txt);p.alignment=0 if cc==0 else 1
    p.paragraph_format.space_after=Pt(2);p.paragraph_format.space_before=Pt(2);p.paragraph_format.line_spacing=1.06
    for r in p.runs:r.font.size=Pt(10);r.bold=rr==0
  doc.add_paragraph().paragraph_format.space_after=Pt(0);tables+=1;continue
 if line.startswith('!['):
  m=re.fullmatch(r'!\[(.*?)\]\((.*?)\)',line);p=doc.add_paragraph();p.alignment=1;p.paragraph_format.keep_with_next=True
  shape=p.add_run().add_picture(str((src.parent/m[2]).resolve()),width=Inches(6.85))
  shape._inline.docPr.set('descr',m[1]);shape._inline.docPr.set('title',m[1])
  cap=doc.add_paragraph(m[1],'Caption');cap.alignment=1;continue
 if line.startswith('- '):rich(doc.add_paragraph(style='List Bullet'),line[2:]);continue
 rich(doc.add_paragraph(),line)
out.parent.mkdir(parents=True,exist_ok=True);doc.save(out)
qa=ROOT/'tmp/thesis_followup_20260916';qa.mkdir(exist_ok=True,parents=True)
(qa/'build.json').write_text(json.dumps({'source':str(src),'output':str(out),'tables':tables,'images':len(doc.inline_shapes),'paragraphs':len(doc.paragraphs)},ensure_ascii=False,indent=2),encoding='utf8')
print(out)

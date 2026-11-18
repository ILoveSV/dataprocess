from pathlib import Path
import re,sys,copy,json
ROOT=Path(__file__).resolve().parent; WORK=ROOT.parent.parent
sys.path.insert(0,str(ROOT.parent/'algorithm_textbook_20260907/python_deps'))
from latex2mathml.converter import convert
from lxml import etree
from docx import Document
from docx.shared import Cm,Pt,RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH,WD_LINE_SPACING,WD_TAB_ALIGNMENT
from docx.enum.table import WD_TABLE_ALIGNMENT,WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
OUT=WORK/'output/documents/论文第四五章_复核修订稿_v2.docx'
doc=Document()
for x in list(doc.styles.element.iter(qn('w:pBdr'))):x.getparent().remove(x)
sec=doc.sections[0];sec.page_width=Cm(21);sec.page_height=Cm(29.7)
sec.top_margin=Cm(3.5);sec.bottom_margin=Cm(4);sec.left_margin=Cm(3);sec.right_margin=Cm(2.5)
sec.header_distance=Cm(1.8);sec.footer_distance=Cm(2)
def font(st,size=12,east='宋体',bold=False):
    st.font.name='Times New Roman';st.font.size=Pt(size);st.font.bold=bold;st.font.color.rgb=RGBColor(0,0,0)
    st.element.get_or_add_rPr().get_or_add_rFonts().set(qn('w:eastAsia'),east)
font(doc.styles['Normal'])
p=doc.styles['Normal'].paragraph_format;p.first_line_indent=Pt(24);p.line_spacing=Pt(20);p.line_spacing_rule=WD_LINE_SPACING.AT_LEAST
p.alignment=WD_ALIGN_PARAGRAPH.JUSTIFY;p.space_after=Pt(0);p.widow_control=True
font(doc.styles['Title'],22,'宋体',True)
doc.styles['Title'].paragraph_format.first_line_indent=Pt(0)
doc.styles['Title'].paragraph_format.alignment=WD_ALIGN_PARAGRAPH.CENTER
doc.styles['Title'].paragraph_format.space_after=Pt(24)
for name,size,before,after in [('Heading 1',16,24,18),('Heading 2',14,24,6),('Heading 3',12,12,6)]:
    font(doc.styles[name],size,'黑体',True);p=doc.styles[name].paragraph_format
    p.first_line_indent=Pt(0);p.space_before=Pt(before);p.space_after=Pt(after);p.keep_with_next=True;p.keep_together=True
    p.line_spacing=Pt(20);p.line_spacing_rule=WD_LINE_SPACING.AT_LEAST
    p.alignment=WD_ALIGN_PARAGRAPH.CENTER if name=='Heading 1' else WD_ALIGN_PARAGRAPH.LEFT
    if name=='Heading 1':p.page_break_before=True
for name in ['Caption','Header','Footer','TOC Heading']:
    font(doc.styles[name],10.5);p=doc.styles[name].paragraph_format;p.first_line_indent=Pt(0);p.line_spacing=1.1
for i in range(1,4):
    name=f'TOC {i}'
    if name not in doc.styles:doc.styles.add_style(name,1)
    font(doc.styles[name],12,bold=i==1);p=doc.styles[name].paragraph_format
    p.first_line_indent=Pt(0);p.left_indent=Pt((i-1)*24);p.space_before=Pt(6 if i==1 else 0);p.space_after=Pt(0)
    p.line_spacing=Pt(20);p.line_spacing_rule=WD_LINE_SPACING.AT_LEAST;p.keep_with_next=False
for name,size in [('Source Note',10),('Reference Text',10.5)]:
    if name not in doc.styles:doc.styles.add_style(name,1)
    font(doc.styles[name],size);p=doc.styles[name].paragraph_format;p.first_line_indent=Pt(0);p.line_spacing=Pt(16);p.line_spacing_rule=WD_LINE_SPACING.AT_LEAST;p.space_after=Pt(4)
doc.styles['Caption'].paragraph_format.space_after=Pt(8)
doc.styles['Caption'].paragraph_format.keep_with_next=False
def field(p,code):
    r=OxmlElement('w:r');x=OxmlElement('w:fldChar');x.set(qn('w:fldCharType'),'begin');r.append(x);p._p.append(r)
    r=OxmlElement('w:r');x=OxmlElement('w:instrText');x.set(qn('xml:space'),'preserve');x.text=code;r.append(x);p._p.append(r)
    r=OxmlElement('w:r');x=OxmlElement('w:fldChar');x.set(qn('w:fldCharType'),'end');r.append(x);p._p.append(r)
sec.header.paragraphs[0].text='硕士学位论文第四章与第五章  复核修订稿 v2'
footer=sec.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
field(footer,' PAGE ')
doc.core_properties.title='论文第四章与第五章正文初稿'
doc.core_properties.subject='实验平台与多通道数据分析方法 水泵实验中的背景特征与运行状态辨识'
doc.core_properties.author='研究论文初稿'
x=OxmlElement('w:updateFields');x.set(qn('w:val'),'true');doc.settings.element.append(x)
transform=etree.XSLT(etree.parse('C:/Program Files/Microsoft Office/root/Office16/MML2OMML.XSL'))
equations=[];figures=[];tables=[]
def equation(number,tex):
    tree=etree.fromstring(convert(tex,display='block').encode())
    assert '\\' not in ''.join(tree.itertext()),tex
    for n in tree.findall('.//{http://www.w3.org/1998/Math/MathML}mover'):
        if len(n)>1 and ''.join(n[-1].itertext()) in ['^','ˆ','̂']:
            n.set('accent','true')
    for n in tree.findall('.//{http://www.w3.org/1998/Math/MathML}mspace'):
        width=n.get('width','')
        if width in ['1em','2em']:
            n.tag='{http://www.w3.org/1998/Math/MathML}mtext';n.attrib.clear();n.text='\u2003'*(2 if width=='2em' else 1)
    el=copy.deepcopy(transform(tree).getroot())
    p=doc.add_paragraph();f=p.paragraph_format;f.first_line_indent=Pt(0);f.alignment=WD_ALIGN_PARAGRAPH.LEFT
    f.line_spacing=1.15;f.space_before=Pt(7);f.space_after=Pt(7);f.keep_together=True
    f.tab_stops.add_tab_stop(Cm(7.2),WD_TAB_ALIGNMENT.CENTER);f.tab_stops.add_tab_stop(Cm(15.45),WD_TAB_ALIGNMENT.RIGHT)
    p.add_run('\t');p._p.append(el);p.add_run('\t（'+number+'）').font.size=Pt(10.5)
    for r in p._p.findall('.//'+qn('m:r')):
        txt=''.join(r.itertext())
        if txt in ['median','PLV','BA','TP','TN','FP','FN']:
            mpr=r.find(qn('m:rPr'))
            if mpr is None:mpr=OxmlElement('m:rPr');r.insert(0,mpr)
            sty=OxmlElement('m:sty');sty.set(qn('m:val'),'p');mpr.append(sty)
        pr=OxmlElement('w:rPr');rf=OxmlElement('w:rFonts');rf.set(qn('w:ascii'),'Cambria Math');rf.set(qn('w:hAnsi'),'Cambria Math');pr.append(rf)
        sz=OxmlElement('w:sz');sz.set(qn('w:val'),'24');pr.append(sz);r.insert(0,pr)
    equations.append(number)
def table(lines):
    rows=[[v.strip() for v in l.strip('|').split('|')] for l in lines]
    n=len(rows[0]);compact=rows[0][0]=='特征集合';widths={3:[3.2,3.5,8.8],4:[7.4,2.1,3.0,3.0],5:[6.1,2.1,2.5,2.4,2.4],6:[3.5,3.3,2.3,2.3,2.1,2.0]}[n]
    if n==5 and any('分层中位差' in v for v in rows[0]):widths=[5.0,3.2,1.8,3.0,2.5]
    t=doc.add_table(rows=0,cols=n);t.alignment=WD_TABLE_ALIGNMENT.CENTER;t.autofit=False
    for col,w in zip(t.columns,widths):col.width=Cm(w)
    bd=OxmlElement('w:tblBorders')
    for edge in ['top','bottom','left','right','insideH','insideV']:
        x=OxmlElement('w:'+edge);x.set(qn('w:val'),'single');x.set(qn('w:sz'),'4');x.set(qn('w:color'),'D9D9D9');bd.append(x)
    t._tbl.tblPr.append(bd)
    for ri,vals in enumerate(rows):
        row=t.add_row();pr=row._tr.get_or_add_trPr();pr.append(OxmlElement('w:cantSplit'))
        if ri==0:pr.append(OxmlElement('w:tblHeader'))
        for ci,(cell,txt) in enumerate(zip(row.cells,vals)):
            cell.width=Cm(widths[ci]);cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            pr=cell._tc.get_or_add_tcPr();mar=OxmlElement('w:tcMar')
            for edge in ['top','bottom','left','right']:
                x=OxmlElement('w:'+edge);x.set(qn('w:w'),'40' if compact else '80');x.set(qn('w:type'),'dxa');mar.append(x)
            pr.append(mar)
            if ri==0:
                x=OxmlElement('w:shd');x.set(qn('w:fill'),'EFEFEF');pr.append(x)
            p=cell.paragraphs[0];f=p.paragraph_format;f.first_line_indent=Pt(0);f.line_spacing=1.1;f.space_after=Pt(0)
            f.alignment=WD_ALIGN_PARAGRAPH.LEFT if ci==0 or n==3 and ci==2 else WD_ALIGN_PARAGRAPH.CENTER
            if ri==0:f.keep_with_next=True
            if compact:f.line_spacing=1.0
            r=p.add_run(txt);r.font.size=Pt(10 if compact else 10.5);r.bold=ri==0
    p=doc.add_paragraph();p.paragraph_format.line_spacing=Pt(3);p.paragraph_format.space_after=Pt(0);p.paragraph_format.first_line_indent=Pt(0)
    tables.append(len(rows)-1)
source=(ROOT/'chapter4.md').read_text(encoding='utf-8-sig')+'\n'+(ROOT/'chapter5.md').read_text(encoding='utf-8-sig')
lines=source.splitlines();i=0;first=True;refs=False;appendix=False
while i<len(lines):
    l=lines[i].strip();i+=1
    if not l:continue
    if l.startswith('$$'):
        number,tex=l[2:-2].split('|',1);equation(number,tex);continue
    if l=='@TOC':
        doc.add_page_break();p=doc.add_paragraph('目录',style='TOC Heading');p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        p=doc.add_paragraph();p.paragraph_format.first_line_indent=Pt(0);field(p,' TOC \\o "1-3" \\h \\z \\u ');continue
    if l.startswith('@FIG '):
        fn,cap=l[5:].split('|',1);p=doc.add_paragraph();f=p.paragraph_format;f.first_line_indent=Pt(0);f.alignment=WD_ALIGN_PARAGRAPH.CENTER;f.keep_with_next=True;f.space_before=Pt(8);f.line_spacing=1
        p.add_run().add_picture(str(ROOT/'figures'/fn),width=Cm(15.35))
        p=doc.add_paragraph(cap,style='Caption');p.alignment=WD_ALIGN_PARAGRAPH.CENTER;figures.append(fn);continue
    if l.startswith('@TABLE '):
        p=doc.add_paragraph(l[7:],style='Caption');p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.keep_with_next=True
        for r in p.runs:r.bold=True
        continue
    if l.startswith('@NOTE '):doc.add_paragraph(l[6:],style='Source Note');continue
    if l.startswith('|'):
        ls=[l]
        while i<len(lines) and lines[i].strip().startswith('|'):ls.append(lines[i].strip());i+=1
        table(ls);continue
    if l.startswith('# '):
        title=l[2:]
        if first:doc.add_paragraph(title,style='Title');first=False
        else:doc.add_paragraph(title,style='Heading 1')
        refs=title=='参考文献';appendix=title.startswith('附录');continue
    if l.startswith('## '):doc.add_paragraph(l[3:],style='Heading 2');continue
    if l.startswith('### '):doc.add_paragraph(l[4:],style='Heading 3');continue
    # Zero-width optional breaks in long provenance paths; preserve readable words.
    if refs or appendix:l=l.replace('/','/\u200b').replace('_','_\u200b')
    p=doc.add_paragraph(l,style='Reference Text' if refs else None)
OUT.parent.mkdir(parents=True,exist_ok=True);doc.save(OUT)
stats={'docx':str(OUT),'characters':len(source),'chinese_characters':len(re.findall(r'[\u4e00-\u9fff]',source)),'equations':len(equations),'figures':len(figures),'tables':len(tables)}
(ROOT/'build_stats.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(stats,ensure_ascii=False))

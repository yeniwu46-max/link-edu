"""Validate OOXML structure and render with an isolated hidden Microsoft Word instance."""
from pathlib import Path
import json, zipfile
from lxml import etree
import win32com.client

root=Path(__file__).resolve().parents[1]
folder=root/'output/competition-delivery-20260914'
word=win32com.client.DispatchEx('Word.Application')
word.Visible=False
word.DisplayAlerts=0
records=[]
try:
    for path in sorted(folder.rglob('*.docx')):
        with zipfile.ZipFile(path) as z:
            assert z.testzip() is None
            for name in z.namelist():
                if name.endswith('.xml'): etree.fromstring(z.read(name))
        document=word.Documents.Open(str(path),ReadOnly=True,AddToRecentFiles=False)
        try:
            document.Repaginate()
            pages=document.ComputeStatistics(2)
            document.ExportAsFixedFormat(str(path.with_suffix('.pdf')),17)
            records.append({'file':str(path.relative_to(folder)),'pages':pages,'xml':'valid','render':'Microsoft Word PDF'})
        finally: document.Close(False)
finally: word.Quit()
(root/'artifacts/private/doc-validation.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(records,ensure_ascii=True))

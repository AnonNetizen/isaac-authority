"""Freeze actual font metrics and declared animation data; no image/font bytes exported."""
import argparse, hashlib, json, re, struct, xml.etree.ElementTree as ET
from pathlib import Path
from start_slice3_ui import digest

def font_metrics(data):
    chars={};kern={};line=None
    if data.startswith(b'BMF\x03'):
        blocks={};offset=4
        while offset<len(data):
            kind,size=struct.unpack_from('<BI',data,offset);offset+=5
            if kind in blocks or offset+size>len(data): raise ValueError('Invalid BMFont block')
            blocks[kind]=data[offset:offset+size];offset+=size
        line=struct.unpack_from('<H',blocks[2])[0]
        if len(blocks[4])%20:raise ValueError('Invalid glyph block')
        for i in range(0,len(blocks[4]),20):
            record=struct.unpack_from('<IHHHHhhhBB',blocks[4],i);chars[str(record[0])]=record[7]
        for i in range(0,len(blocks.get(5,b'')),10):
            a,b,value=struct.unpack_from('<IIh',blocks[5],i);kern[str(a)+':'+str(b)]=value
    elif data.lstrip().startswith(b'<'):
        root=ET.fromstring(data);line=int(root.find('common').attrib['lineHeight'])
        chars={x.attrib['id']:int(x.attrib['xadvance']) for x in root.findall('./chars/char')}
        kern={x.attrib['first']+':'+x.attrib['second']:int(x.attrib['amount']) for x in root.findall('./kernings/kerning')}
    else:
        text=data.decode('utf-8');line=int(re.search(r'lineHeight=(\d+)',text)[1])
        for row in text.splitlines():
            pairs=dict(re.findall(r'(\w+)=(-?\d+)',row))
            if row.startswith('char '):chars[pairs['id']]=int(pairs['xadvance'])
            if row.startswith('kerning '):kern[pairs['first']+':'+pairs['second']]=int(pairs['amount'])
    if not chars or line is None:raise ValueError('Missing metrics')
    return {'advances':chars,'kerning':kern,'line_height':line,'metric_source':'actual_frozen_font'}

def freeze(root,game):
    inputs=json.loads((root/'research/slice3_ui_inputs.json').read_text());records=[];verified={}
    for item in inputs['resource_catalog']['resources']:
        for f in item['files']:
            p=game/f['path']
            if f['path'] not in verified:verified[f['path']]=digest(p)
            if verified[f['path']]!=f['sha256']:raise ValueError('Resource hash changed: '+f['path'])
        entry=dict(item)
        if item['kind']=='font':entry['metrics']=font_metrics((game/item['path']).read_bytes())
        records.append(entry)
    out=root/'research/slice3_ui_resources.json'
    if out.exists():raise ValueError('Refusing to replace frozen metrics')
    out.write_text(json.dumps({'schema':'slice3-ui-resources-1','inputs_sha256':digest(root/'research/slice3_ui_inputs.json'),
        'resources':records,'files_verified':verified,'native_measurement_equivalence_passed':False,
        'pixel_rendering_tested':False},indent=2)+'\n')
    return {'resources':len(records),'font_metrics':sum('metrics' in x for x in records),'files':len(verified),'sha256':digest(out)}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--game',type=Path,required=True);a=p.parse_args()
    print(json.dumps(freeze(Path(__file__).resolve().parents[1],a.game),indent=2))

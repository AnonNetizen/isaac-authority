"""Keep one current handoff report; compress history and remove owned objects."""
import gzip,json,struct,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_boundary_handoff as e
ROOT=e.ROOT;REPORT=ROOT/'reports'
def main():
    current=REPORT/'boundary-handoff-v3/result.json';r=json.loads(current.read_text(encoding='utf-8'))
    assert r['passed'] and len(r['cases'])==18 and r['protected_files_unchanged'] and r['save_files_unchanged']
    assert not r['automatic_mixed_projection_passed'] and not r['precise_write_versions_implemented']
    assert r['exe_sha256']==e.digest(e.EXE) and r['manifest_sha256']==e.digest(e.MANIFEST) and r['driver_sha256']==e.digest(ROOT/'tools/run_boundary_handoff.py')
    for case in r['cases']:
        assert case['passed']
        if case['kind']=='process-rejection':continue
        ref,first,second=case['reports'];assert e.canonical(ref)==e.canonical(first)==e.canonical(second)
        assert first['steps']==second['steps'] and first['metadata']==second['metadata']
        assert not first['personal_draws_publishable'] and not first['automatic_projection_implemented']
    before=e.protected();binaries={p.name:e.digest(p) for p in (ROOT/'build-boundary/Release').iterdir() if p.suffix in ['.exe','.lib']}
    raw=e.EXE.read_bytes();pe=struct.unpack_from('<I',raw,0x3c)[0];assert raw[pe:pe+4]==b'PE\0\0' and struct.unpack_from('<H',raw,pe+4)[0]==0x14c
    history=[]
    for name in ['boundary-handoff-v1','boundary-handoff-v2']:
        p=REPORT/name/'result.json';data=p.read_bytes();packed=gzip.compress(data,mtime=0);target=p.with_suffix('.json.gz')
        assert not target.exists() and not p.is_symlink() and p.resolve().parent==(REPORT/name).resolve()
        target.write_bytes(packed);assert gzip.decompress(target.read_bytes())==data
        history.append({'path':target.relative_to(ROOT).as_posix(),'original_bytes':len(data),'original_sha256':e.digest(p),'bytes':len(packed),'sha256':e.digest(target),'reason':'lossless verified historical result; v1 incorrect expected API enumeration, v2 pre-prototype-reclamation candidate'})
        p.unlink()
    cleanup=[];build=(ROOT/'build-boundary').resolve();assert build==Path('D:/Coding/ISAAC/authority/build-boundary').resolve()
    for p in build.rglob('*'):
        if p.is_file() and p.suffix in ['.obj','.pch','.ipch','.tlog','.ilk']:
            assert not p.is_symlink() and p.resolve().is_relative_to(build)
            cleanup.append({'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':e.digest(p),'basis':'regenerable objects in this candidate only; stock source and preserved legacy ABI objects excluded'})
    for row in cleanup:
        p=ROOT/row['path'];assert e.digest(p)==row['sha256'];p.unlink()
    assert before==e.protected()
    assert binaries=={p.name:e.digest(p) for p in (ROOT/'build-boundary/Release').iterdir() if p.suffix in ['.exe','.lib']}
    assert not list((REPORT/'boundary-handoff-v3').rglob('*.audit'))
    large=[]
    for c in r['cases']:
        if not c['id'].startswith('opaque-table-'):continue
        ref,first,second=c['reports'];large.append({'id':c['id'],'reference_mean_seconds':ref['seconds'],'boundary_mean_seconds':(first['seconds']+second['seconds'])/2,'charged_work':first['budget']['used'],'personal_metadata':first['metadata'][1],'private_commit_bytes':first['private_commit_bytes']})
    assert all(v['personal_metadata']['observed_fields']==2 and v['personal_metadata']['field_reads']==2 for v in large)
    assert len({tuple((k,v['personal_metadata'][k]) for k in ['active_callbacks','observed_cells','observed_fields','prototype_entries']) for v in large})==1
    summary={'schema':'boundary-handoff-final-1','handoff_gate_passed':True,'functional_handoff_cases':sum(c['kind']=='handoff' for c in r['cases']),'boundary_or_budget_rejection_cases':sum(c['kind'] in ['boundary-rejection','process-rejection'] for c in r['cases']),'known_limit_cases':sum(c['kind']=='known-limitation' for c in r['cases']),'mixed_compatibility_not_implemented_cases':sum(c['kind']=='compatibility-not-implemented' for c in r['cases']),'complete_automatic_compatibility_passed':False,'exact_write_versions_implemented':False,'work_limit':10000000,'case_timeout_seconds':5,'same_budget_unit_as_full_trace':False,'large_table_cases':large,'binary_sha256':binaries,'formal_files_and_saves_unchanged':True,'game_started':False,'normal_audit_bytes':0,'cleanup_bytes':sum(c['bytes'] for c in cleanup),'cleanup':cleanup,'historical_results':history,'scope':'ordinary Lua initialization-to-callback continuity with bounded observed roots; no mixed callback projection or real MCM/EID validation'}
    inputs=[ROOT/'tools/run_boundary_handoff.py',ROOT/'tools/finalize_boundary_handoff.py',e.MANIFEST,current,ROOT/'third_party/lua533/SOURCE.json',ROOT/'docs/BOUNDARY_ARCHITECTURE_PLAN.md']
    inputs+=list((ROOT/'boundary_runtime').glob('*'))+list((ROOT/'research/boundary_handoff').glob('*.lua'))
    summary['inputs']={p.relative_to(ROOT).as_posix():e.digest(p) for p in inputs if p.is_file()}
    doc=['# API 边界第一步：初始化到回调的衔接','',
         '本轮第一步门槛通过；完整自动隔离尚未通过。新原型采用固定官方 Lua 5.3.3 源码，Windows x86 静态链接，不加载或修改全量追踪 DLL。旧全量追踪器及其结果保留为离线诊断工具。','',
         '## 已证明的行为','',
         '- 同一私有 Lua 状态延续到回调。初始化产生的配置表、别名、工厂返回闭包、共享 upvalue、缓存的原生方法保持原 Lua 行为。注册根保持真实 registry 引用；活跃根持有期间，实际共享单元身份稳定。最后一个登记所有者移除后，辅助身份退休，不把后来出现的同一地址当作原单元。',
         '- 主机/个人状态独立；保存采用私有内存中的原 JSON 字符串，重载恢复个人配置。缓存世界写入和随机 API 在调用时检查当前角色、阶段；pcall 吞掉错误仍使整次回调失败。',
         '- 失败丢弃本次世界/保存/绘制，重建上下文并重放已接受历史；确认私有计数、配置、世界和 RNG 恢复。旧上下文代次和移除后的回调句柄拒绝使用。',
         '- 元数据只登记根和按需读取的字段。绘制只保留当前未发布队列，世界查询只保留次数和最后值，没有全量逐值图或审计文件。',
         '- 同一 API 后端关闭/开启身份观察分别运行，普通结果与重复结果一致；false、nil 和原始字符串字节保持。官方源码按 SOURCE.json 逐文件核验。','',
         '## 验收分项','',
         f"- {summary['functional_handoff_cases']} 项状态/身份衔接检查通过。",
         f"- {summary['boundary_or_budget_rejection_cases']} 项边界或预算拒绝按预期复现，不计作混合回调兼容。",
         '- 1 项 A→B→A 反例明确展示：观察版本看不到两次观察之间的中间写入，尚不能作为精确失效或纯界面的证明。',
         '- 1 项混合用途检查保持整体发布能力关闭。这是本版本的统一能力门，不是已实现对任意回调依赖的自动识别；没有把它计为功能兼容通过。','',
         '| 无关表字段数 | 普通后端秒 | 开启元数据秒（两次均值） | 新工作单位 | 观察字段数 |','|---|---:|---:|---:|---:|']
    for v in large:doc.append(f"| {v['id'].removeprefix('opaque-table-')} | {v['reference_mean_seconds']:.6f} | {v['boundary_mean_seconds']:.6f} | {v['charged_work']} | {v['personal_metadata']['observed_fields']} |")
    doc+=['','时间为原生程序内的小样本，不含进程启动，不作统计显著性结论，也不能与全量追踪真实 EID 的时间直接对比。普通 Lua 大表自身仍占时间和内存；固定的是本例新增的根/字段元数据数量。','',
          '## 保留的限制','',
          '- 1000 万上限、每个子进程 5 秒不变。新计数分项为每 64 条 Lua 指令保守预付、API、实际观察及源码/配置/绘制编码；与旧全量追踪单位不同，不以工作量下降证明架构性能。标准库 C 函数的全部内部成本尚未逐项登记，另由进程 1 GiB 与外部 5 秒保护。',
          '- 本轮是模型最小 API 后端，输入按钮使用模型字符串键，JSON 配置仅支持登记的标量/对象；不是完整 J460/MCM/EID API 契约验收。没有加载真实 MCM/EID、接入渲染或通信。',
          '- 还没有精确字段/upvalue 写屏障，也没有普通值经过算术、字符串及分支后的最小依赖投影。不能用根身份、API 顺序或最终数值替代这些证明。',
          '- 本原型仅接受 --handoff-suite，所有个人绘制都不可发布；不能用它代替已完成的联机模式。','',
          '## 下一步','',
          '先做已登记根的精确写集合：Lua 普通写入、rawset、闭包写入及表库写入必须统一更新字段/upvalue 版本；覆盖 A→B→A、兄弟字段不失效、删除重建、共享闭包和 GC。观察不到的原生写入口拒绝。通过后才建立消费端读取集合与最小表达式，不重新开启全量逐值图。','',
          '配置来源在 LoadData/JSON 解码边界登记；保留初始化闭包中的实际对象和字段身份。嵌套闭包的实际返回已验证，但跨这些函数的依赖摘要仍待实现。主机贡献对应、菜单/HUD 用途规则和原混合反例继续是后续功能门槛。','',
          '## 入口与清理','',
          '`python -B authority/tools/run_boundary_handoff.py run --output <新的空结果目录>`。源码在 authority/boundary_runtime，唯一构建目录 authority/build-boundary，冻结清单 authority/research/boundary_handoff_v1.json。',
          f"清理本轮编译中间文件 {summary['cleanup_bytes']} 字节；旧两份本轮报告经完整字节校验后无损压缩，当前只保留一份完整明文结果。保留 EXE、静态库、源码和失败记录，没有 ZIP、模组/资源副本或游戏操作。"]
    p=ROOT/'docs/BOUNDARY_HANDOFF_RESULTS.md';p.write_text('\n'.join(doc)+'\n',encoding='utf-8');summary['inputs'][p.relative_to(ROOT).as_posix()]=e.digest(p)
    e.save(REPORT/'boundary-handoff-final.json',summary)
    print(json.dumps({'handoff_gate':True,'functional_cases':summary['functional_handoff_cases'],'rejection_cases':summary['boundary_or_budget_rejection_cases'],'mixed_projection_passed':False,'cleanup_bytes':summary['cleanup_bytes'],'normal_audit_bytes':0}))
if __name__=='__main__':main()

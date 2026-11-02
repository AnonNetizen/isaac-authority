"""Verify existing short results and compact only this candidate's own outputs."""
import gzip,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_evidence_lifetime as experiment
ROOT=experiment.ROOT
REPORT=ROOT/'reports'
def load(name):return json.loads((REPORT/name/'result.json').read_text(encoding='utf-8'))
def digest(p):return experiment.gate.digest(p)
def main():
    storage=load('evidence-lifetime-storage-v2');model=load('evidence-lifetime-model-v1')
    bench=load('evidence-lifetime-benchmark-v2');eviction=load('evidence-lifetime-eviction-4-v1');real=load('evidence-lifetime-real-v1')
    assert storage['passed'] and model['passed'] and model['complete_manifest'] and bench['passed'] and eviction['passed']
    assert storage['exe_sha256']==digest(experiment.BIN/'authority-evidence-lifetime-storage.exe')
    assert all(g['dll_sha256']==digest(experiment.DLL) for g in [model,bench,eviction,real])
    assert model['preserved_formal_files_unchanged'] and model['save_files_unchanged']
    assert real['preserved_formal_files_unchanged'] and real['save_files_unchanged'] and real['frozen_sources_unchanged']
    assert len(real['cases'])==3 and all(c['timeout_seconds']==5 and c['work_limit']==10000000 for c in real['cases'])
    for case in real['cases']:
        profile=case['last_profile'];assert profile and profile['work_accounting_valid'] and profile['used']<=10000000
        assert case['audit_prefix']['tail_error'] is None
    current=ROOT/'build-evidence-lifetime';old=ROOT/'build-audit-volume'
    assert digest(current/'generated/audit_journal.hpp')==digest(old/'generated/audit_journal.hpp')
    # The preparation writer emits Windows CRLF; compare the complete source
    # text and retain both actual byte hashes in the final inventory.
    assert (current/'generated/evidence_store.hpp').read_text(encoding='utf-8')==(ROOT/'evidence_lifetime_runtime/evidence_store.hpp').read_text(encoding='utf-8')
    before=experiment.protected();candidate_before={p.name:digest(p) for p in (current/'Release').iterdir() if p.suffix in ['.dll','.exe','.lib']}
    checks=[]
    folder=REPORT/'evidence-lifetime-model-v1'
    for case in model['cases']:
        with gzip.open(folder/(case['id']+'-candidate.json.gz'),'rt',encoding='utf-8') as f:r=json.load(f)
        stats=r.get('execution_before_diagnostics',{}).get('evidence_lifetime')
        if stats:
            assert not stats['keep_history'] and stats['resident_use_slots']<=1 and stats['accounted_resident_bytes']<=8388608 and stats['resident_entries']<=8192
            assert r['execution_before_diagnostics']['journal_reads']==0
            checks.append({'id':case['id'],'stats':stats})
    assert len(checks)>=27
    cleanup=[]
    # Per-case summaries are strict subsets of the completed, retained summary.
    for case in model['cases']:
        p=folder/(case['id']+'-result.json')
        if not p.exists():continue
        old_row=json.loads(p.read_text(encoding='utf-8'))
        if not all(k in case and case[k]==v for k,v in old_row.items()):continue
        assert not p.is_symlink() and p.resolve().parent==folder.resolve()
        cleanup.append({'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':digest(p),'basis':'exact subset of retained model result'})
    build=current.resolve()
    assert build==Path('D:/Coding/ISAAC/authority/build-evidence-lifetime').resolve()
    intermediates=[p for p in build.rglob('*') if p.is_file() and p.suffix in ['.obj','.pch','.ipch','.tlog','.ilk']]
    for p in intermediates:
        assert not p.is_symlink() and p.resolve().is_relative_to(build)
        cleanup.append({'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':digest(p),'basis':'regenerable private candidate compiler intermediate; imported formal C objects excluded'})
    for item in cleanup:
        p=ROOT/item['path'];assert digest(p)==item['sha256'];p.unlink()
    assert before==experiment.protected()
    assert candidate_before=={p.name:digest(p) for p in (current/'Release').iterdir() if p.suffix in ['.dll','.exe','.lib']}
    assert not [p for folder in REPORT.glob('evidence-lifetime*') for p in folder.rglob('*.audit')]
    experiment.gate.save(REPORT/'evidence-lifetime-cleanup.json',{'removed':cleanup,'released_bytes':sum(x['bytes'] for x in cleanup),'candidate_binaries_preserved':True,'formal_and_frozen_files_unchanged':True})
    repeat=[c for c in storage['cases'] if c['id'].startswith('repeat-')]
    assert all(c['report']['result']['metrics']['resident_use_bytes']==24 for c in repeat)
    vectors=[]
    for case in ['root-128','graph-churn-16','dual-config-2']:
        rows=[r for r in bench['rows'] if r['id']==case]
        values={mode:{'mean_seconds':sum(r['seconds'] for r in rows if r['mode']==mode)/2,
            'work':next(r['work'] for r in rows if r['mode']==mode),
            'use_payload_bytes':next(r['stats']['resident_use_bytes'] for r in rows if r['mode']==mode)} for mode in ['retained','streamed']}
        vectors.append({'id':case,**values})
    result={'schema':'evidence-lifetime-final-1','component_gate_passed':True,'real_initialization_gate_passed':real['compatibility_passed'],
        'work_limit':10000000,'case_timeout_seconds':5,'storage_cases':len(storage['cases']),'model_cases':len(model['cases']),
        'model_functional_cases':sum(c['kind']=='functional' for c in model['cases']),
        'eviction_cases':len(eviction['cases']),'lifetime_checks':checks,'short_benchmark':vectors,
        'binary_sha256':candidate_before,'protected_files_unchanged':before==experiment.protected(),
        'save_files_unchanged':real['save_files_unchanged'],'frozen_sources_unchanged':real['frozen_sources_unchanged'],
        'real_probes':[{'id':c['id'],'timed_out':c['timed_out'],'seconds':c['seconds'],'observed_work':c['last_profile']['used'],'audit_bytes':c['audit_prefix']['file_bytes']} for c in real['cases']],
        'cleanup_bytes':sum(x['bytes'] for x in cleanup),'remaining_audits':0,'game_started':False,'zip_or_mod_copies_created':False,
        'scope':'bounded evidence use/site history and descriptor encoding cache; not constant memory for the entire runtime',
        'historical_harness_failures':[
            {'report':'evidence-lifetime-benchmark-v1/result.json','cause':'unused outer sampler page was checked; inner runtime sampler used by inherited invocation is now checked; semantic proof equality passed all three cases'},
            {'report':'evidence-lifetime-eviction-v1/result.json','cause':'test expected eviction for seven unique descriptors in an eight-entry cache; corrected and supplemented by four-entry tests with actual eviction in every case'}]}
    result['inputs']={}
    for folder_name in ['evidence_lifetime_runtime','build-evidence-lifetime/generated']:
        for p in (ROOT/folder_name).iterdir():
            if p.is_file():result['inputs'][p.relative_to(ROOT).as_posix()]=digest(p)
    for name in ['run_evidence_lifetime.py','finalize_evidence_lifetime.py']:
        p=ROOT/'tools'/name;result['inputs'][p.relative_to(ROOT).as_posix()]=digest(p)
    for name in ['evidence-lifetime-storage-v2','evidence-lifetime-model-v1','evidence-lifetime-benchmark-v2','evidence-lifetime-eviction-4-v1','evidence-lifetime-real-v1']:
        p=REPORT/name/'result.json';result['inputs'][p.relative_to(ROOT).as_posix()]=digest(p)
    experiment.gate.save(REPORT/'evidence-lifetime-final.json',result)
    text=['# 常驻证据生命周期：本轮结果','',
        '组件门槛通过；真实 MCM/EID/组合初始化门槛尚未通过。Windows x86、1000 万工作单位、每子进程 5 秒保持不变。未启动游戏、未改冻结模组或存档。', '',
        '## 已实现','',
        '- 默认执行端只保留一个最后使用载荷（24 字节）和单调事件号。每次逻辑使用仍完整追加审计，历史不再进入可扩容的常驻向量。',
        '- 描述缓存按 8 MiB 计账、最多 8192 项，LRU 淘汰完整键和值编码；哈希只选固定桶，逐字节比较。另有 16 KiB 固定桶和分配器开销，由既有 512 MiB DLL 堆硬限制覆盖；该数字不是整个进程内存。',
        '- 描述编号不复用。编码提示淘汰后重建事件；实际计算的完成证明仍取活跃 memo 的版本与完成事件号。直接使用退休或未知描述号明确拒绝。',
        '- 站点历史写入审计，执行端只保留数量及活跃调用帧已有的站点编号。',
        '- 命令行侧在执行结束后独立展开历史，比较每条事件的来源、时点、完成证明，以及完整值图/控制流、观察值和个人/权威视图。报告中的重建数组不是 DLL 常驻数组。', '',
        '## 验证','',
        '- 12 项存储案例通过：32/4096/65536 次使用的常驻载荷均为 24 字节，描述计账均为 147 字节；覆盖淘汰、重新编码、旧编号、强制哈希冲突、真实文件配额、写入故障、超预算及站点流。',
        '- 原 37 项模型清单原源码原预期回归通过；功能通过与预期安全拒绝分开记录。每个成功模型的逻辑事件、值来源、图和证书与旧版一致，重复执行一致，执行期审计回读为零。',
        '- 仅容纳 4 项的缓存下，5 项整体验证全部通过，且每项实际发生淘汰；包括个人配置、闭包、跨帧时点。',
        '- 同一 DLL 的保留历史对照模式与默认模式各跑两次。完整展开证明一致；时间是小样本，不作统计显著性结论。', '',
        '| 短案例 | 保留历史秒数 | 默认秒数 | 保留历史使用载荷 | 默认使用载荷 |','|---|---:|---:|---:|---:|']
    for v in vectors:text.append(f"| {v['id']} | {v['retained']['mean_seconds']:.4f} | {v['streamed']['mean_seconds']:.4f} | {v['retained']['use_payload_bytes']} B | {v['streamed']['use_payload_bytes']} B |")
    text+=['','秒数为原生子进程完成及在线诊断时间；命令行离线历史重建另计。保留历史模式只用于有限对照，不是默认执行路径。','',
        '## 真实源码的短探测','',
        '| 案例 | 观测工作量 | 结果 |','|---|---:|---|']
    for c in result['real_probes']:text.append(f"| {c['id']} | {c['observed_work']} | 5 秒到时停止，未完成 |")
    text+=['','三项未触发 1000 万上限，也没有完整初始化成功，因此本轮不能判真实模组功能通过，不能据此判定完整初始化后的内存峰值。值图、对象/字段/upvalue、来源集合和其他索引仍受各自既有上限约束，尚未证明整个运行时恒定内存。', '',
        '## 边界和清理','',
        '- 个人配置独立、奖励/相关 HUD 跟随主机的既有规则不变；模型验证不等于真实画面或联机验收。',
        '- Journal/压缩编码源码与上一已验证候选逐字节相同，8 MiB 单条、16 MiB 测试文件、256 KiB 批量缓冲及失败后禁止继续执行的协议保持。',
        '- 历史测量工具的两次失败报告保留：一次误读未使用的采样页，一次错误要求未满缓存必须淘汰。修正验证器后重跑，运行时语义对照始终一致。',
        f"- 原始审计均核验删除；移除 {len(cleanup)} 个重复摘要/当前候选编译中间文件，共 {result['cleanup_bytes']} 字节。保留 DLL/EXE/静态库、生成源码、完整压缩模型证据及唯一失败记录。没有 ZIP 或模组副本。", '',
        '## 入口','',
        '```powershell',
        'python -B authority/tools/run_evidence_lifetime.py storage --output <新目录>',
        'python -B authority/tools/run_evidence_lifetime.py model --output <新目录> --gate <存储门槛/result.json>',
        'python -B authority/tools/run_evidence_lifetime.py benchmark --output <新目录> --gate <模型门槛/result.json>',
        'python -B authority/tools/run_evidence_lifetime.py eviction --output <新目录> --gate <模型门槛/result.json> --cache-entries 4',
        'python -B authority/tools/run_evidence_lifetime.py initialization --output <新目录> --gate <模型门槛/result.json> --benchmark <基准/result.json> --eviction <淘汰门槛/result.json>',
        '```','',
        '源码/CMake 在 `authority/evidence_lifetime_runtime`；唯一构建目录为 `authority/build-evidence-lifetime`。二进制、工具、源码及报告哈希在 `authority/reports/evidence-lifetime-final.json`。']
    (ROOT/'docs/EVIDENCE_LIFETIME_RESULTS.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    print(json.dumps({'component_gate':True,'real_initialization_gate':real['compatibility_passed'],'cleanup_bytes':result['cleanup_bytes'],'remaining_audits':0,'protected_unchanged':True},ensure_ascii=False))
if __name__=='__main__':main()

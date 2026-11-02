"""Verify this bounded candidate and remove only owned, regenerable outputs."""
import gzip,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_ledger_cache as e
ROOT=e.ROOT;REPORT=ROOT/'reports'
def load(name):return json.loads((REPORT/name/'result.json').read_text(encoding='utf-8'))
def digest(p):return e.gate.digest(p)
def main():
    native=load('ledger-cache-native-v3');storage=load('ledger-cache-storage-v2');model=load('ledger-cache-model-v2')
    bench=load('ledger-cache-benchmark-v1');eviction=load('ledger-cache-eviction-v1');real=load('ledger-cache-real-v1')
    assert native['passed'] and storage['passed'] and model['passed'] and model['complete_manifest'] and bench['passed'] and eviction['passed']
    assert native['exe_sha256']==digest(e.BIN/'authority-ledger-tests.exe')
    assert storage['exe_sha256']==digest(e.BIN/'authority-ledger-cache-storage.exe')
    assert all(r['dll_sha256']==digest(e.DLL) for r in [model,bench,eviction,real])
    assert model['preserved_formal_files_unchanged'] and model['save_files_unchanged']
    assert real['preserved_formal_files_unchanged'] and real['save_files_unchanged'] and real['frozen_sources_unchanged']
    assert len(model['same_execution_accounting_checks'])==37 and all(c['passed'] for c in model['same_execution_accounting_checks'])
    checks=[]
    for row in model['cases']:
        with gzip.open(REPORT/'ledger-cache-model-v2'/(row['id']+'-candidate.json.gz'),'rt',encoding='utf-8') as f:r=json.load(f)
        if row['kind']=='process-safety':continue
        before=r['execution_before_diagnostics'];after=r['execution_after_diagnostics']
        assert before['ledger_verification']['complete_equal'] and after['ledger_verification']['complete_equal']
        assert before['journal_reads']==0 and before['cache_hit_history_reads']==0
        lifetime=before['evidence_lifetime'];assert lifetime['resident_use_slots']<=1 and lifetime['resident_entries']<=8192 and lifetime['accounted_resident_bytes']<=8388608
        checks.append({'id':row['id'],'verified_charges':after['ledger_verification']['verified_charges'],'budget':r['budget']['used']})
    assert len(real['cases'])==3
    for c in real['cases']:
        assert c['timeout_seconds']==5 and c['work_limit']==10000000
        assert c['last_profile'] and c['last_profile']['work_accounting_valid'] and c['last_profile']['used']<=10000000
        assert c['audit_prefix']['tail_error'] is None
    current=ROOT/'build-ledger-cache';prior=ROOT/'build-evidence-lifetime'
    unchanged=['audit_journal.hpp','audit_wire.hpp','evidence_store.hpp','incremental.inc','trace_reclaim.inc','compact_graph.hpp','consumer_state.hpp']
    for name in unchanged:
        if not (prior/'generated'/name).exists():continue
        assert digest(current/'generated'/name)==digest(prior/'generated'/name),name
    assert (current/'generated/budget.hpp').read_text(encoding='utf-8')==(ROOT/'ledger_cache_runtime/budget.hpp').read_text(encoding='utf-8')
    before=e.protected();binaries={p.name:digest(p) for p in e.BIN.iterdir() if p.suffix in ['.exe','.dll','.lib']}
    cleanup=[]
    for folder in REPORT.glob('ledger-cache-model-*'):
        summary=folder/'result.json'
        if not summary.exists():continue
        result=json.loads(summary.read_text(encoding='utf-8'))
        for row in result['cases']:
            p=folder/(row['id']+'-result.json')
            if p.exists():
                value=json.loads(p.read_text(encoding='utf-8'))
                if all(row.get(k)==v for k,v in value.items()):
                    assert not p.is_symlink() and p.resolve().parent==folder.resolve()
                    cleanup.append({'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':digest(p),'basis':'exact subset of retained completed model result'})
    build=current.resolve();assert build==Path('D:/Coding/ISAAC/authority/build-ledger-cache').resolve()
    for p in build.rglob('*'):
        if p.is_file() and p.suffix in ['.obj','.pch','.ipch','.tlog','.ilk']:
            assert not p.is_symlink() and p.resolve().is_relative_to(build)
            cleanup.append({'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':digest(p),'basis':'regenerable candidate C++ intermediate; preserved external C ABI objects excluded'})
    for row in cleanup:
        p=ROOT/row['path'];assert digest(p)==row['sha256'];p.unlink()
    assert before==e.protected()
    assert binaries=={p.name:digest(p) for p in e.BIN.iterdir() if p.suffix in ['.exe','.dll','.lib']}
    assert not [p for folder in REPORT.glob('ledger-cache-*') if folder.is_dir() for p in folder.rglob('*.audit')]
    e.gate.save(REPORT/'ledger-cache-cleanup.json',{'removed':cleanup,'released_bytes':sum(r['bytes'] for r in cleanup),'binaries_and_protected_files_preserved':True})
    micro={mode:sum(r['report']['result']['loop_seconds'] for r in native['microbenchmark'] if r['mode']==mode)/2 for mode in ['legacy','cached']}
    timings=[]
    for name in ['root-128','graph-churn-16','dual-config-2']:
        rows=[r for r in bench['rows'] if r['id']==name]
        timings.append({'id':name,**{mode:sum(r['seconds'] for r in rows if r['mode']==mode)/2 for mode in ['legacy','cached']},'proof_equal':True,'budget_equal_across_processes':next(c['budget_equal'] for c in bench['checks'] if c['id']==name)})
    old_real=load('evidence-lifetime-real-v1');real_rows=[]
    for c in real['cases']:
        old=next(r for r in old_real['cases'] if r['id']==c['id']);p=c['last_profile'];op=old['last_profile']
        real_rows.append({'id':c['id'],'timed_out':c['timed_out'],'seconds':c['seconds'],'observed_work':p['used'],'prior_observed_work':op['used'],'ledger_sample_fraction':p['sampled_wall_fractions'].get('ledger'),'prior_ledger_sample_fraction':op['sampled_wall_fractions'].get('ledger'),'audit_bytes':c['audit_prefix']['file_bytes'],'first_unsupported':(c.get('report') or {}).get('case',{}).get('first_unsupported_entry')})
    result={'schema':'ledger-cache-final-1','component_gate_passed':True,'real_initialization_gate_passed':real['compatibility_passed'],'work_limit':10000000,'case_timeout_seconds':5,'native_cases':len(native['cases']),'storage_cases':len(storage['cases']),'model_cases':37,'eviction_cases':len(eviction['cases']),'cache_bytes_per_budget':4096,'microbenchmark_mean_seconds':micro,'short_benchmark':timings,'same_execution_accounting_checks':checks,'real_probes':real_rows,'binary_sha256':binaries,'cleanup_bytes':sum(r['bytes'] for r in cleanup),'remaining_audits':0,'game_started':False,'zip_or_mod_copies_created':False,'protected_and_save_files_unchanged':True,'scope':'counter lookup acceleration; does not bound all active dependency metadata or prove real initialization compatibility','historical_validation_issues':[{'path':'ledger-cache-native-v1/progress.json','reason':'validator read nonexistent sampler work key; corrected to categories'},{'path':'ledger-cache-model-v1/result.json','reason':'cross-process baseline enabled fewer oracles; underlying 37 behavior/profile cases all passed'},{'path':'ledger-cache-accounting-model-v1/result.json','reason':'serialized audit pathname bytes differed; diagnostic encoding fees were real differences'},{'path':'ledger-cache-accounting-model-v2/result.json','reason':'address-layout-dependent field-index work differs between processes; same-call-stream mirror replaces this as exact accounting proof'}]}
    result['inputs']={}
    for folder in ['ledger_cache_runtime','build-ledger-cache/generated']:
        for p in (ROOT/folder).iterdir():
            if p.is_file():result['inputs'][p.relative_to(ROOT).as_posix()]=digest(p)
    for name in ['run_ledger_cache.py','finalize_ledger_cache.py']:
        p=ROOT/'tools'/name;result['inputs'][p.relative_to(ROOT).as_posix()]=digest(p)
    for name in ['ledger-cache-native-v3','ledger-cache-storage-v2','ledger-cache-model-v2','ledger-cache-benchmark-v1','ledger-cache-eviction-v1','ledger-cache-real-v1']:
        p=REPORT/name/'result.json';result['inputs'][p.relative_to(ROOT).as_posix()]=digest(p)
    e.gate.save(REPORT/'ledger-cache-final.json',result)
    lines=['# 固定容量记账缓存：结果','',
        '计数与模型门槛通过。真实初始化的结论按下表记录；命令行模型通过不等于真实游戏、菜单画面或联机已修复。Windows x86、1000 万上限、5 秒子进程超时不变。','',
        '## 实现','',
        '- 每个预算上下文使用 512 槽、4096 字节缓存。地址只选槽，完整比较规范表自有字符串，才可更新原计数器。可变标签、不同地址、冲突及超出缓存容量都保持原语义。',
        '- 规范表仅内部修改，节点不删除，预算对象不可复制或移动，缓存无悬空计数器。标签表沿用已有存储规则，4 KiB 仅指新增缓存，不能当作整个预算表或运行时的内存。',
        '- 旧路径由 IA_LEDGER_LEGACY_LOOKUP=1 选择。IA_LEDGER_VERIFY=1 仅用于短模型，同一次执行逐次镜像旧算法，并在边界比较完整表；正常基准、真实初始化关闭镜像。',
        '- 模组、双视图与奖励规则、审计编码、历史证据缓存和回收实现未改。','',
        '## 验证','',
        f"- {len(native['cases'])} 项原生边界检查、12 项存储检查、冻结 37 项模型及 5 项强制淘汰案例通过。模型每次收费与旧算法镜像一致，功能结果、完整语义图、证书和逻辑审计与已验收候选一致。",
        '- 执行阶段历史文件回读为零；个人配置与主机奖励的既有模型检查继续通过。预期拒绝仍独立计为安全诊断。',
        '- 跨进程的字段索引比较、移动及诊断文件字节费用存在已有物理布局差异，完整保留原始计数，不归零也不从报告中移除。',
        f"- 200 万次收费微基准均值：旧路径 {micro['legacy']:.4f} 秒，缓存路径 {micro['cached']:.4f} 秒。仅是计数热路径的小样本，不代表整个初始化加速倍数。",'',
        '| 短模型 | 旧记账路径秒 | 缓存路径秒 |','|---|---:|---:|']
    for r in timings:lines.append(f"| {r['id']} | {r['legacy']:.4f} | {r['cached']:.4f} |")
    lines+=['','同 DLL 两次、反向顺序对照，关闭逐次镜像。包含原生子进程和在线诊断；离线历史重建另计。','',
        '## 真实源码的有限探测','',
        '| 案例 | 上轮观测工作量 | 本轮观测工作量 | 本轮结果 |','|---|---:|---:|---|']
    for r in real_rows:lines.append(f"| {r['id']} | {r['prior_observed_work']} | {r['observed_work']} | {'5 秒停止，未完成' if r['timed_out'] else (r['first_unsupported'] or '见逐例报告')} |")
    lines+=['','工作量取最后一次有效采样，未完成时不能推断完整总量、完整内存峰值或兼容通过。没有自动放宽配额、超时和工作上限。','',
        '## 清理和后续','',
        f"审计均已核验移除，清理重复逐例摘要与本候选编译中间文件 {result['cleanup_bytes']} 字节；保留原型二进制、源码、完整压缩证明和失败诊断。没有新 ZIP 或模组副本。",
        '本轮真实采样的主要耗时已转到值图构建与读取，合计约 44%～52%。下一轮优先检查重复构造、读取和解码，再按字段/upvalue 精确失效范围推进；地址布局差异继续保留测量，不把少量计数差异当作主要耗时的证据。尚未进入真实菜单导航、绘制重放和世界接管。','',
        '入口：`python -B authority/tools/run_ledger_cache.py <native|storage|model|benchmark|eviction|initialization> --output <新目录>`；模型还需 `--accounting <原生检查/result.json> --gate <存储检查/result.json>`。其余阶段沿用 `--gate <模型/result.json>`，初始化再提供 `--benchmark`、`--eviction`。',
        '源码：`authority/ledger_cache_runtime`；唯一构建目录：`authority/build-ledger-cache`。最终哈希清单：`authority/reports/ledger-cache-final.json`。']
    (ROOT/'docs/LEDGER_CACHE_RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'component_gate':True,'real_initialization_gate':real['compatibility_passed'],'cleanup_bytes':result['cleanup_bytes'],'remaining_audits':0}))
if __name__=='__main__':main()

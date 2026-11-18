"""Summarize existing output-OFF timing tests; never controls hardware."""

from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis/dps150_timing_uniformity_20261105"


def main():
    evidence = []
    for path in sorted((ROOT/"local/logs").glob("dps150_uniform_off_20261105_*/summary.json")):
        data=json.loads(path.read_text(encoding="utf-8"))
        evidence.append(dict(path=str(path.relative_to(ROOT)),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(), **data))
    qualified=[]
    for rate in (200,100,50,40,30,25,20):
        passed=[]
        for item in evidence:
            if item.get('ack_every_point') or item.get('quiet_session') or not item.get('rtscts',True):
                continue
            passed.extend(row for row in item["results"]
                if row["rate_per_s"]==rate and row.get("pass_all")
                and row.get("os_completed_writes")==row["actual_count"])
        durations={row["duration_s"] for row in passed}
        if {3,10,30,60} <= durations:
            qualified.append((rate,passed))
    if not qualified:
        raise RuntimeError("No rate yet passed both staged and 60-second qualification")
    rate, passed=qualified[0]
    if not all(not item["output_enabled_by_test"] for item in evidence):
        raise ValueError("Unexpected powered test in evidence")
    OUT.mkdir(parents=True,exist_ok=True)
    worst_min=min(row["interval_min_ms"] for row in passed)
    worst_max=max(row["interval_max_ms"] for row in passed)
    latest60=[row for row in passed if row["duration_s"]==60][-1]
    certificate=dict(qualified_rate_per_s=rate,qualification_date="2026-11-05",
        qualification_kind="Output-OFF empirical host/OS-write timing; not real-time guarantee",
        per_interval_tolerance_fraction=.10,abort_on_violation=True,
        no_catchup=True,output_enabled_by_tests=False,
        all_passed_stage_interval_min_ms=worst_min,
        all_passed_stage_interval_max_ms=worst_max,
        latest_60s_result=latest60,
        device_execution_time_verified=False,
        powered_waveform_not_tested_this_turn=True,
        rtscts=True, ack_every_point=False, quiet_session=False,
        evidence=[dict(path=item["path"],sha256=item["sha256"]) for item in evidence])
    pause_path=ROOT/'analysis/dps150_pause_diagnosis_20261105/evidence.json'
    if pause_path.exists():
        pause=json.loads(pause_path.read_text(encoding='utf-8'))['summary']
        certificate.update(periodic_communication_pause_eliminated=False,
            known_write_completion_delay_max_ms=pause['long_write_max_ms'],
            diagnosis_path=str(pause_path.relative_to(ROOT)),
            qualification_does_not_establish_device_execution_uniformity=True)
    (OUT/"qualification.json").write_text(json.dumps(certificate,indent=2),encoding="utf-8")
    (OUT/"all_evidence.json").write_text(json.dumps(evidence,indent=2),encoding="utf-8")
    text=["# DPS150发送时序修正与输出关闭验证", "", "日期：2026-11-05。", "",
        "## 当前结论", "",
        f"选用{rate}次/秒作为当前已通过的主机发送档位，而非设备模拟带宽。",
        "输出全程保持关闭，未让用户开始新的示波器记录。",
        "已通过3、10、30秒分阶段测试和额外60秒复测，每个已发送指令的间隔都受10%窗口约束；",
        "这是有限测试的经验结果，不是Windows、USB或设备执行的绝对实时保证。", "",
        "## 改动", "",
        "- 预先生成完整指令字节，定时循环不做JSON序列化或磁盘日志刷新。",
        "- 非阻塞读取，末段短时间忙等，暂时请求较细Windows定时与本进程Above Normal优先级，结束恢复。",
        "- 使用Windows非阻塞写入，同时确认上一个OS写入完成，不允许多条待完成写入积压。",
        "- 超过时限、间隔不符或存在发送积压立即中止；不追赶、不集中补发。",
        "- 正式正弦模式改用同一个发送器及本次资格文件；缺少资格文件则阻止启动。",
        "- 未达到200次/秒的均匀性资格前，阻止旧5 Hz/40点方案再次启动。", "",
        "## 数字", "",
        f"60秒档位：{rate}/秒，发送{latest60['actual_count']}点；OS写入完成数相同；最终电压设定读回匹配。",
        f"60秒发送间隔最小{latest60['interval_min_ms']:.6f} ms，最大{latest60['interval_max_ms']:.6f} ms。",
        f"60秒最大主机迟到{latest60['lateness_max_ms']:.6f} ms。",
        f"同档所有通过阶段的间隔总范围{worst_min:.6f}-{worst_max:.6f} ms。", "",
        "200、100、50等较高速率曾触发OS写入未完成/阻塞；40/s在长测中触发严格迟到规则。",
        "追加的200/160/100/80/50每点SET+GET核对均未完成3秒；已发送点可读回，但有下一时隙前未完成传输/回读。",
        "关闭硬件流控未消除该现象。关闭协议会话后查询不回复，该方案不用于验收；正常会话已恢复。",
        "30/s曾通过3/10/30秒，但60秒复测在约48秒触发迟到规则，因此未选用。",
        "这些失败不等于模拟带宽上限，也未确定全部延迟来自主机、驱动、USB流控还是固件。", "",
        "## 证据边界", "",
        "OS写入完成不等于设备准确在同一时刻执行；仅最后一个设定寄存器被查询核对，不是逐点执行核对。",
        "正式输出后的实际电压/电流形状仍需示波器验证。任何新运行都可能因系统负载而中止。",
        "降低更新率会减少每周期点数：更新率不能与正弦频率混为一谈；不能保留200点/s的理论误差数字。",
        "后续是否使用更低调制频率或接受较粗阶梯，需要明示点数与带内响应，不直接复用旧理想THD。", "",
        "## 文件与复现", "",
        "共享发送器：scripts/dps150_timed_sender.py。",
        "输出关闭测试：local/workbench/dps150_uniform_off_test.py。",
        "后续输出入口：local/workbench/dps150_pipe_test.py（本轮未运行任何输出模式）。",
        "单元测试：tests/test_dps150_timed_sender.py；正常、迟到、积压、阻塞写入四项。",
        "汇总：scripts/summarize_dps150_uniformity_20261105.py。",
        "原始时序和状态保留在各local/logs/dps150_uniform_off_20261105_*目录，摘要及SHA-256见JSON。",
        "未修改研究原始数据、既有COMSOL模型或分析主流水线。"]
    if pause_path.exists():
        text.extend(['', '## 后续停顿排查的补充限制', '',
            '见analysis/dps150_pause_diagnosis_20261105/REPORT.md。',
            '分层诊断发现本次通信约每0.527秒出现一次周期性长等待，30秒复测OS写完成等待最长约39.5 ms。',
            '20/s逐点SET+GET虽完成全部200点，最长事务仍约46.5 ms；降低发送率没有证明周期性暂停消失。',
            '上文资格仅约束主机发送起点及下一点前OS写入完成，不是每个设备执行时刻的均匀性资格。',
            '固件周期任务是优先假设，尚未独立于USB栈证实；本次未测实际带电波形。'])
    (OUT/"REPORT.md").write_text("\n".join(text)+"\n",encoding="utf-8")
    print(json.dumps(certificate,indent=2))


if __name__=="__main__":
    main()

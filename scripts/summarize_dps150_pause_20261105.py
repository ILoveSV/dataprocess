"""Offline audit of DPS150 pause diagnostics; never opens a hardware port."""
import csv
import hashlib
import json
from pathlib import Path
import statistics

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'analysis/dps150_pause_diagnosis_20261105'


def load_rows(folder,name):
    with (folder/name).open(encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    evidence=[]
    for path in sorted((ROOT/'local/logs').glob('dps150_pause_20261105_*/summary.json')):
        d=json.loads(path.read_text(encoding='utf-8'))
        if d.get('output_enabled_by_test') or any(s['output_on'] for s in d['snapshots']):
            raise RuntimeError('Unexpected enabled output in evidence')
        evidence.append(dict(path=str(path.relative_to(ROOT)),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),**d))
    baseline=next(e for e in reversed(evidence) if e['arguments']['seconds']==30
                  and e['arguments']['rate']==200 and not e['arguments']['ack'])
    folder=(ROOT/baseline['path']).parent
    rows=load_rows(folder,'transactions.csv')
    frames=load_rows(folder,'frames.csv')
    origin=float(rows[0]['send_s'])
    time=[float(r['send_s'])-origin for r in rows]
    completion=[float(r['os_complete_ms']) for r in rows]
    lateness=[float(r['host_late_ms']) for r in rows]
    spikes=[(t,c) for t,c in zip(time,completion) if c>5]
    telemetry=[float(f['t_s'])-origin for f in frames if f['kind']=='195']
    telemetry=[t for t in telemetry if 0<=t<=30]
    periods=[b-a for a,b in zip(telemetry,telemetry[1:])]
    spike_periods=[b[0]-a[0] for a,b in zip(spikes,spikes[1:])]
    finish_offset=[(t+c/1000-min(telemetry,key=lambda a:abs(a-t-c/1000)))*1000 for t,c in spikes]
    physical_summary=dict(baseline=baseline['path'],long_write_count=len(spikes),
        long_write_min_ms=min(c for t,c in spikes),long_write_max_ms=max(c for t,c in spikes),
        long_write_median_ms=statistics.median(c for t,c in spikes),
        spike_period_median_s=statistics.median(spike_periods),
        telemetry_period_median_s=statistics.median(periods),
        completion_minus_nearest_telemetry_median_ms=statistics.median(finish_offset),
        host_lateness_max_ms=max(lateness),write_call_max_ms=max(float(r['write_call_ms']) for r in rows),
        inferred_cause='Periodic device/USB communication-service unavailability; firmware task is a leading hypothesis, not proven independently of USB stack',
        actual_analog_output_measured=False,periodic_pause_eliminated=False)
    (OUT/'evidence.json').write_text(json.dumps(dict(summary=physical_summary,runs=evidence),indent=2),encoding='utf-8')
    fields=['folder','rate','seconds','kind','ack','explicit_baud','no_rtscts','closed_session','read_only','reader_thread','transactions','skipped_slots','max_os_write_ms','max_transaction_ms','last_setting_matches']
    with (OUT/'comparison.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields)
        w.writeheader()
        for e in evidence:
            lat=e['latencies']
            w.writerow(dict(folder=str(Path(e['path']).parent),**{k:e['arguments'].get(k,False) for k in fields[1:10]},
                transactions=e['transactions'],skipped_slots=e['skipped_slots'],
                max_os_write_ms=(lat['os_complete_ms'] or {}).get('max'),
                max_transaction_ms=(lat['transaction_ms'] or {}).get('max'),
                last_setting_matches=e.get('last_setting_matches')))
    fig,ax=plt.subplots(3,1,figsize=(12,8),gridspec_kw={'height_ratios':[1,1,1.3]},layout='constrained')
    ax[0].plot(time,lateness,color='#007f8b',lw=.65)
    ax[0].set(ylabel='Host lateness (ms)',xlim=(0,30),title='OUTPUT OFF: 200 requested setpoints/s, missed slots skipped (no catch-up)')
    ax[1].plot(time,completion,color='#bd352b',lw=.65)
    ax[1].set(ylabel='OS write completion\nobservation delay (ms)',xlim=(0,30))
    center=spikes[len(spikes)//2][0]
    lo,hi=center-.15,center+1.05
    for t,c in spikes:
        if lo<t<hi:
            ax[2].axvspan(t,t+c/1000,color='#bd352b',alpha=.22)
    ax[2].plot(time,completion,color='#bd352b',marker='.',ms=3,lw=.7,label='Write completion delay')
    for k,t in enumerate(v for v in telemetry if lo<v<hi):
        ax[2].axvline(t,color='#188754',lw=1.3,ls='--',label='Automatic telemetry received' if k==0 else None)
    ax[2].set(xlim=(lo,hi),ylim=(-1,45),ylabel='Delay (ms)',xlabel='Elapsed time from first test command (s)',
              title='Zoom: periodic long writes occur next to the telemetry cycle')
    ax[2].legend(loc='upper right',fontsize=9)
    for a in ax:
        a.grid(alpha=.2)
    fig.savefig(OUT/'pause_layers.png',dpi=170)
    plt.close(fig)
    text=f'''# DPS150 周期性停顿分层排查

日期：2026-11-05。本轮所有实机测试输出均关闭；电压设定不超过3 V，电流限值不超过5 mA。未改固件、驱动、注册表或系统电源策略。

## 结果

**已定位主要停顿形态，但尚未消除。** 停顿主要体现为周期性通信服务等待，不能再仅用Python发送循环不均匀解释。电源固件的周期任务是优先假设，但没有底层USB追踪，不能排除USB栈/设备交互，也不能命名为已证实的某个ADC或屏幕刷新函数。

200次/秒、30秒关闭输出复测：共实际提交{baseline['transactions']}个设定，跳过{baseline['skipped_slots']}个过期时隙，不集中补发；{len(spikes)}次OS写完成观测延迟超过5 ms，长延迟范围{physical_summary['long_write_min_ms']:.3f}–{physical_summary['long_write_max_ms']:.3f} ms。

长延迟起点间隔中位数{physical_summary['spike_period_median_s']:.6f} s；自动遥测195帧的间隔中位数{physical_summary['telemetry_period_median_s']:.6f} s。写完成观测时刻与相邻遥测接收时刻之差中位数{physical_summary['completion_minus_nearest_telemetry_median_ms']:.3f} ms。这是时间关联，不单独证明遥测发送本身引起阻塞。

同一30秒测试中，write()调用最长{physical_summary['write_call_max_ms']:.3f} ms；主机迟到最大{physical_summary['host_lateness_max_ms']:.3f} ms，说明Windows调度也存在少量离群值，但不等同于反复出现的近40 ms写完成延迟。

## 对照检查

- 200/s逐点SET电压+GET：正常往返约2.3 ms，周期性最长约49.7 ms；电压SET本身的OS完成也可能很快，而后续GET卡住。OS接收首个数据包不代表设备已执行该设定。
- 改为SET电流+GET：同类周期性停顿仍在，排除仅由电压设定这一种操作引起的解释。
- 只读GET，不改变运行设定：仍有约39 ms写完成长等待，不能归因于负载、输出控制环路或正弦计算。
- 不做逐点GET，只发SET：仍有周期性写完成长等待，查询不是该现象存在的必要条件。
- 明确补发115200波特率初始化：未消除。
- 关闭RTS/CTS流控、改用持续接收线程：未消除。未把未知寄存器当作遥测关闭开关。
- 关闭C1会话：遥测/回包停止，设定值也未被接受，不能作为安静波形控制模式；仍观察到周期性OS完成长等待，说明不能把原因简单限定为遥测帧的传输字节量。
- 本机为Microsoft usbser.sys，版本10.0.22621.3672；设备直接挂在USB根集线器，路径PCIROOT(0)#PCI(1400)#USBROOT(0)#USB(9)，无外接Hub。设备注册表没有IdleUsbSelectiveSuspendPolicy项。没有直接关闭系统USB省电功能。

## 20次/秒结论需要加的限制

20/s、10秒逐点SET+GET共200点，无跳步、最终设定读回匹配，但完整事务仍有最长约46.5 ms等待。先前20/s、60秒均匀发送通过，只是主机发送节拍资格，不是设备执行节拍或模拟输出均匀性资格。降低更新率可以避免积压或容纳等待，不能证明内部停顿被消除。

不能把任何一次OS写完成时刻或GET返回时刻直接当成DAC更新时间。此次输出关闭，因此没有新测得的模拟电压或电流波形。

## 已落实的软件处理

既有共享发送器已采用预计算、内存日志、非阻塞串口、临时细定时与进程优先级、超时中止及禁止追赶补发。本轮新增分层诊断，分别保存主机迟到、write调用耗时、OS写完成观测等待、GET回包等待，以及遥测帧时间；原始CSV未覆盖。

发送器的积压报错现在区分Windows异步写未完成与SET/GET回包等待。未声称这些保护能修复设备/USB链路本身的周期性暂停。

## 下一步边界

1. 在另一台电脑/另一USB控制器上重复同一个输出关闭诊断，检验周期及延迟是否跟随电源。单纯换同一根集线器的插口不保证切换控制器。
2. 使用管理员USB ETW追踪进一步比较提交和完成的底层时间；当前进程不是管理员，没有擅自提权或启动系统追踪。
3. 将本报告、时间图和固件V1.2信息提供厂商，询问周期性通信服务空档及是否存在有保证的硬件定时波形/关闭周期任务接口。未找到厂商公开的高速均匀设定保证，不直接升级固件试错。
4. 软件侧诊断不能替代示波器测量。确认实际波形时应保存电阻负载电压的原始CSV，评估实际阶梯保持间隔、相位、幅度和失真；电化学负载还需测实际电流。

## 复现与证据

- 诊断入口：local/workbench/dps150_pause_diagnostic.py。默认只发输出关闭的电压设定；--ack逐点读回，--kind 194改为电流设定，--read-only只查询，--reader-thread使用持续接收线程。
- 本报告离线复算：scripts/summarize_dps150_pause_20261105.py。
- evidence.json含每轮摘要、状态、来源路径与摘要SHA-256；comparison.csv比较全部对照；pause_layers.png是分层时间图。
- 原始transactions.csv/frames.csv/slow_calls.csv位于各local/logs/dps150_pause_20261105_*目录。原始日志为本机文件，不应假定已上传Git。
- 未修改研究原始数据、COMSOL模型或研究处理主流水线。

## 查询资料

- FNIRSI官方软件说明：https://www.fnirsi.com/pages/software-downloads 。公开扫描延时范围1–86400秒，不是200/s任意波形保证。
- Microsoft usbser.sys说明：https://learn.microsoft.com/en-us/windows-hardware/drivers/usbcon/usb-driver-installation-based-on-compatible-ids 。空闲挂起配置及默认行为，不据此盲目改注册表。
- Microsoft USB ETW说明：https://learn.microsoft.com/en-us/windows-hardware/drivers/usbcon/how-to-capture-a-usb-event-trace 。采集需要管理员命令窗口。
- 协议实现者源码：https://github.com/cho45/fnirsi-dps-150/blob/master/dps-150.js 。初始化与协议交叉核对，不能把其50ms软件休眠当作硬件性能证据。
'''
    (OUT/'REPORT.md').write_text(text,encoding='utf-8')
    print(json.dumps(physical_summary,indent=2))


if __name__=='__main__':
    main()

"""Host-timed bounded packet sender; timestamps are not USB execution times."""

from contextlib import contextmanager
import ctypes
import os
import time


class TimingViolation(RuntimeError):
    pass


class SerialAsyncWriter:
    """Keep at most one Windows overlapped write outstanding, without waiting.

    This uses the installed pySerial Windows backend's existing handle/event.
    Completion means OS write completion, not verified device execution.
    Precomputed packet storage must remain alive until drain() finishes.
    """
    def __init__(self, port):
        if os.name != "nt" or port.write_timeout != 0:
            raise ValueError("Windows nonblocking serial port required")
        from serial import win32
        self.win32 = win32
        self.port = port
        self.pending_bytes = None
        self.completed_writes = 0

    @property
    def out_waiting(self):
        if self.pending_bytes is not None:
            count = self.win32.DWORD()
            completed = self.win32.GetOverlappedResult(
                self.port._port_handle, self.port._overlapped_write,
                ctypes.byref(count), False)
            if not completed:
                code = self.win32.GetLastError()
                if code == 996:  # ERROR_IO_INCOMPLETE.
                    return max(1, self.port.out_waiting)
                raise OSError(code, "Serial write completion error")
            if count.value != self.pending_bytes:
                raise RuntimeError("Incomplete asynchronous serial write")
            self.completed_writes += 1
            self.pending_bytes = None
        return self.port.out_waiting

    def write(self, packet):
        if self.pending_bytes is not None:
            raise RuntimeError("Previous asynchronous write still pending")
        count = self.port.write(packet)
        self.pending_bytes = len(packet)
        return count

    def drain(self, timeout=.5):
        deadline = time.perf_counter()+timeout
        while self.out_waiting:
            if time.perf_counter()>deadline:
                raise TimingViolation("Transmit completion timeout")
            time.sleep(.0005)

    @property
    def backlog_reason(self):
        if self.pending_bytes is not None:
            return "Windows overlapped write not completed (not a device execution timestamp)"
        return "Driver transmit queue not empty"


@contextmanager
def timing_context():
    """Temporarily request finer Windows timing for this process only."""
    kernel = None
    process = None
    priority = None
    timer_enabled = False
    if os.name == "nt":
        kernel = ctypes.windll.kernel32
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        kernel.GetPriorityClass.argtypes = [ctypes.c_void_p]
        kernel.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        process = kernel.GetCurrentProcess()
        priority = kernel.GetPriorityClass(process)
        if priority:
            kernel.SetPriorityClass(process, 0x8000)  # ABOVE_NORMAL, never REALTIME.
        timer_enabled = ctypes.windll.winmm.timeBeginPeriod(1) == 0
    try:
        yield
    finally:
        if timer_enabled:
            ctypes.windll.winmm.timeEndPeriod(1)
        if kernel is not None and priority:
            kernel.SetPriorityClass(process, priority)


def send_uniform(port, packets, rate, rows, poll, *, tolerance=.10,
                 clock=time.perf_counter, sleep=time.sleep):
    """Abort on >10% slot timing deviation; never replay missed deadlines.

    ``poll`` must be nonblocking. ``rows`` retains partial evidence on failure.
    The caller owns output limits and shutdown; this function never enables power.
    """
    if not 1 <= rate <= 200 or not 0 < tolerance <= .25:
        raise ValueError("Unsupported rate or tolerance")
    interval = 1/rate
    beginning = clock()+.05
    previous = None
    for index, packet in enumerate(packets):
        target = beginning+index*interval
        while True:
            remaining = target-clock()
            if remaining <= 0:
                break
            if remaining > .0015:
                poll()
                remaining = target-clock()
                if remaining > .0015:
                    sleep(min(.001, remaining-.001))
            # Spin only in the final millisecond to avoid a coarse serial sleep.
        if port.out_waiting:
            detail = getattr(port, 'backlog_reason', 'Unclassified pending transport')
            raise TimingViolation(f"Serial transmit backlog at slot {index}: {detail}")
        sent = clock()
        if sent-target > tolerance*interval:
            raise TimingViolation(f"Missed slot {index}: late {(sent-target)*1000:.3f} ms")
        if previous is not None and abs(sent-previous-interval) > tolerance*interval:
            raise TimingViolation(f"Uneven send interval at slot {index}")
        count = port.write(packet)
        ended = clock()
        rows.append(dict(index=index, target_s=target, send_start_s=sent,
                         send_end_s=ended, bytes_written=count))
        if count != len(packet):
            raise RuntimeError("Incomplete serial write")
        if ended-sent > interval*.5:
            raise TimingViolation(f"Blocking write at slot {index}")
        previous = sent
        if clock() < target+interval-.0015:
            poll()


def summarize(rows, rate, expected_count):
    intervals = [(b["send_start_s"]-a["send_start_s"])*1000
                 for a, b in zip(rows, rows[1:])]
    lateness = [(row["send_start_s"]-row["target_s"])*1000 for row in rows]
    elapsed = ((rows[-1]["send_start_s"]-rows[0]["send_start_s"])
               if len(rows)>1 else 0)
    return dict(rate_per_s=rate, expected_count=expected_count, actual_count=len(rows),
        complete=len(rows)==expected_count, duration_between_first_last_s=elapsed,
        interval_min_ms=min(intervals) if intervals else None,
        interval_max_ms=max(intervals) if intervals else None,
        lateness_max_ms=max(lateness) if lateness else None,
        write_duration_max_ms=max((r["send_end_s"]-r["send_start_s"])*1000
                                  for r in rows) if rows else None)

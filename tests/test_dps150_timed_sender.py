import pytest

from scripts.dps150_timed_sender import send_uniform, summarize, TimingViolation


class Clock:
    def __init__(self):
        self.value = 0.

    def now(self):
        self.value += .00001
        return self.value

    def sleep(self, seconds):
        self.value += seconds


class Port:
    out_waiting = 0

    def __init__(self, clock):
        self.clock = clock
        self.packets = []

    def write(self, packet):
        self.packets.append(packet)
        self.clock.value += .00002
        return len(packet)


def test_regular_slots_are_sent_without_catchup():
    clock = Clock()
    port = Port(clock)
    rows = []
    send_uniform(port, [b"test"]*100, 200, rows, lambda: None,
                 clock=clock.now, sleep=clock.sleep)
    metrics = summarize(rows, 200, 100)
    assert metrics["complete"]
    assert 4.5 <= metrics["interval_min_ms"] <= metrics["interval_max_ms"] <= 5.5


def test_late_slot_aborts_instead_of_replaying_packets():
    clock = Clock()
    port = Port(clock)
    rows = []

    def delayed_poll():
        if len(rows)>=2:
            clock.value += .015

    with pytest.raises(TimingViolation):
        send_uniform(port, [b"test"]*100, 200, rows, delayed_poll,
                     clock=clock.now, sleep=clock.sleep)
    assert len(port.packets) == 2


def test_tx_backlog_prevents_a_new_write():
    clock = Clock()
    port = Port(clock)
    port.out_waiting = 1
    rows = []
    with pytest.raises(TimingViolation, match="backlog"):
        send_uniform(port, [b"test"], 200, rows, lambda: None,
                     clock=clock.now, sleep=clock.sleep)
    assert port.packets == []


def test_backlog_error_preserves_layer_information():
    clock = Clock()
    port = Port(clock)
    port.out_waiting = 1
    port.backlog_reason = 'Register reply pending, not USB write'
    with pytest.raises(TimingViolation, match='Register reply pending, not USB write'):
        send_uniform(port, [b'test'], 200, [], lambda: None,
                     clock=clock.now, sleep=clock.sleep)


def test_slow_write_aborts_before_next_packet():
    clock = Clock()
    port = Port(clock)
    original = port.write

    def slow_write(packet):
        count = original(packet)
        clock.value += .020
        return count

    port.write = slow_write
    rows = []
    with pytest.raises(TimingViolation, match="Blocking write"):
        send_uniform(port, [b"test"]*100, 200, rows, lambda: None,
                     clock=clock.now, sleep=clock.sleep)
    assert len(port.packets) == 1

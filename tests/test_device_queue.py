from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from queue import Queue
import sys
import tempfile
from threading import current_thread, Event
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lab"))
from device_queue import DeviceQueue, ENABLED


class DeviceQueueTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.queue = DeviceQueue(temporary.name, "fixture-device")
        self.queue.lease.parent.mkdir()
        self.queue.directory.mkdir()
        (self.queue.directory / ENABLED).touch()

    def append_legacy(self, workstream):
        with self.queue.queue.open("a") as stream:
            stream.write(workstream + "\n")

    def test_queued_job_waits_behind_legacy_reservation_and_leaves_later_head(self):
        queue = self.queue
        self.append_legacy("first")
        self.assertEqual(queue.grant_legacy(), "first")
        state = []

        def release_legacy(_seconds):
            self.assertFalse(queue.lease.exists())
            self.assertEqual(queue.grant.read_text(), "first\n")
            self.append_legacy("later")
            self.assertIsNone(queue.grant_legacy())
            queue.taken.touch()
            state.append("legacy-finished")

        with mock.patch("device_queue.time.sleep", side_effect=release_legacy):
            queue.wait(queue.lease.mkdir)
        self.assertEqual(state, ["legacy-finished"])
        self.assertTrue(queue.lease.is_dir())
        self.assertIsNone(queue.grant_legacy())
        queue.lease.rmdir()
        self.assertEqual(queue.grant_legacy(), "later")

    def test_two_waiters_claim_in_order_and_dispatcher_never_grants_their_tickets(self):
        queue = self.queue
        queue.lease.mkdir()
        sleeping = Queue()
        first_wake, second_wake = Event(), Event()

        def wait_for_release(_seconds):
            sleeping.put(None)
            # The first waiter wakes after the second has tried the free lease.
            gate = first_wake if current_thread().name.startswith("first") else second_wake
            if not gate.wait(5):
                raise TimeoutError("Test did not release waiter")
            gate.clear()

        with (
            mock.patch("device_queue.time.sleep", side_effect=wait_for_release),
            ThreadPoolExecutor(max_workers=1, thread_name_prefix="first") as first_pool,
            ThreadPoolExecutor(max_workers=1, thread_name_prefix="second") as second_pool,
        ):
            first = first_pool.submit(queue.wait, queue.lease.mkdir)
            sleeping.get(timeout=5)
            second = second_pool.submit(queue.wait, queue.lease.mkdir)
            sleeping.get(timeout=5)
            queue.lease.rmdir()
            self.assertIsNone(queue.grant_legacy())
            second_wake.set()
            sleeping.get(timeout=5)
            self.assertFalse(queue.lease.exists())
            first_wake.set()
            first.result(timeout=5)
            self.assertTrue(queue.lease.is_dir())
            queue.lease.rmdir()
            second_wake.set()
            second.result(timeout=5)
            self.assertTrue(queue.lease.is_dir())

    def test_interrupt_withdraws_waiter_and_preserves_busy_lease(self):
        queue = self.queue
        queue.lease.mkdir()
        owner = queue.lease / "owner"
        owner.touch()
        with mock.patch("device_queue.time.sleep", side_effect=InterruptedError):
            with self.assertRaises(InterruptedError):
                queue.wait(queue.lease.mkdir)
        self.assertTrue(owner.exists())
        self.assertEqual(list(queue.tickets.iterdir()), [])
        self.append_legacy("next")
        owner.unlink()
        queue.lease.rmdir()
        self.assertEqual(queue.grant_legacy(), "next")

    def test_dead_waiter_does_not_block_legacy_grant(self):
        queue = self.queue
        queue.tickets.mkdir()
        token = "a" * 32
        (queue.tickets / token).write_text("42")
        queue.queue.write_text("@" + token + "\n")
        self.append_legacy("next")
        with mock.patch("device_queue.os.kill", side_effect=ProcessLookupError):
            self.assertEqual(queue.grant_legacy(), "next")
        self.assertEqual(list(queue.tickets.iterdir()), [])

    def test_dispatcher_must_enable_new_queue_before_submission(self):
        (self.queue.directory / ENABLED).unlink()
        with self.assertRaisesRegex(RuntimeError, "dispatcher has not enabled"):
            self.queue.wait(self.queue.lease.mkdir)
        self.assertFalse(self.queue.queue.exists())


if __name__ == "__main__":
    unittest.main()

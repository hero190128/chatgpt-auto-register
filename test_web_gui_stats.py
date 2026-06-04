import json
import tempfile
from pathlib import Path
import threading
import unittest
from unittest import mock

import web_gui

CONFIG_FILE = Path(web_gui.__file__).with_name("config.json")


class WebGuiStatsTests(unittest.TestCase):
    def setUp(self):
        self._saved_state = dict(web_gui._state)
        self._config_existed = CONFIG_FILE.exists()
        self._config_backup = CONFIG_FILE.read_text(encoding="utf-8") if self._config_existed else None

    def tearDown(self):
        web_gui._state.clear()
        web_gui._state.update(self._saved_state)
        if self._config_existed:
            CONFIG_FILE.write_text(self._config_backup, encoding="utf-8")
        elif CONFIG_FILE.exists():
            CONFIG_FILE.unlink()

    def test_api_status_includes_current_and_total_stats(self):
        web_gui._state["running"] = True
        web_gui._state["results"] = [{"ok": True}, {"ok": False}]
        web_gui._state["stats"] = {
            "current_success": 1,
            "current_fail": 1,
            "total_success": 5,
            "total_fail": 3,
        }

        with web_gui.app.test_client() as client:
            resp = client.get("/api/status")

        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(
            data["stats"],
            {
                "current_success": 1,
                "current_fail": 1,
                "total_success": 5,
                "total_fail": 3,
            },
        )

    def test_log_writer_keeps_buffers_separate_per_thread(self):
        entries = []
        writer = web_gui._LogWriter(
            lambda msg, tag="info", thread_id=None: entries.append(
                {"msg": msg, "tag": tag, "thread": thread_id}
            )
        )
        ready = threading.Barrier(2)

        def worker(thread_id, part1, part2):
            writer.bind_thread(thread_id)
            try:
                writer.write(part1)
                ready.wait(timeout=2)
                writer.write(part2)
                writer.flush()
            finally:
                writer.unbind_thread()

        t1 = threading.Thread(target=worker, args=(1, "A", "1\n"), daemon=True)
        t2 = threading.Thread(target=worker, args=(2, "B", "2\n"), daemon=True)
        t1.start()
        t2.start()
        t1.join(timeout=2)
        t2.join(timeout=2)

        self.assertEqual(
            entries,
            [
                {"msg": "B2", "tag": "info", "thread": 2},
                {"msg": "A1", "tag": "info", "thread": 1},
            ],
        )

    def test_api_config_roundtrips_plus_fields(self):
        payload = {
            "plus_method": "paypal",
            "plus_email": "pay@example.com",
            "plus_phone": "+6281234567890",
            "plus_pin": "123456",
            "plus_country": "ID",
            "plus_currency": "IDR",
        }

        with web_gui.app.test_client() as client:
            resp = client.post("/api/config", json=payload)
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertTrue(data["ok"])

            resp = client.get("/api/config")
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()

        cfg = data["config"]
        self.assertEqual(cfg["plus_method"], "paypal")
        self.assertEqual(cfg["plus_email"], "pay@example.com")
        self.assertEqual(cfg["plus_phone"], "+6281234567890")
        self.assertEqual(cfg["plus_pin"], "123456")
        self.assertEqual(cfg["plus_country"], "ID")
        self.assertEqual(cfg["plus_currency"], "IDR")

    def test_api_config_roundtrips_outlook_pool_text(self):
        payload = {
            "email_provider": "outlook",
            "outlook_pool": "a@outlook.com----pw----cid----rt",
        }

        with web_gui.app.test_client() as client:
            resp = client.post("/api/config", json=payload)
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertTrue(data["ok"])

            resp = client.get("/api/config")
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()

        cfg = data["config"]
        self.assertEqual(cfg["email_provider"], "outlook")
        self.assertEqual(cfg["outlook_pool"], "a@outlook.com----pw----cid----rt")

    def test_api_outlook_pool_summary_and_list_classify_entries_from_local_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            pool_path = Path(tmp) / "outlook.txt"
            used_path = Path(tmp) / "outlook_used.txt"
            results_dir = Path(tmp) / "results"
            results_dir.mkdir()

            pool_path.write_text(
                "\n".join(
                    [
                        "success@outlook.com----pw----cid----rt",
                        "bad@outlook.com----pw----cid----rt",
                        "verify@outlook.com----pw----cid----rt",
                        "reserved@outlook.com----pw----cid----rt",
                        "failed@outlook.com----pw----cid----rt",
                        "unused@outlook.com----pw----cid----rt",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            used_path.write_text(
                "\n".join(
                    [
                        "2026-06-04 10:00:00\tsuccess@outlook.com\tbad",
                        "2026-06-04 10:01:00\tbad@outlook.com\tbad",
                        "2026-06-04 10:02:00\tverify@outlook.com\tverify_failed",
                        "2026-06-04 10:03:00\treserved@outlook.com\treserved",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (results_dir / "111_20260604_100500.json").write_text(
                json.dumps(
                    {
                        "ok": True,
                        "phone": "+111",
                        "bind_email": "success@outlook.com",
                        "sub2api_id": "sub-111",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (results_dir / "222_20260604_100600.json").write_text(
                json.dumps(
                    {
                        "ok": True,
                        "phone": "+222-new",
                        "bind_email": "failed@outlook.com",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (results_dir / "222_20260604_100100.json").write_text(
                json.dumps(
                    {
                        "ok": True,
                        "phone": "+222-old",
                        "bind_email": "failed@outlook.com",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (results_dir / "_all.json").write_text(
                json.dumps(
                    [
                        {
                            "ok": True,
                            "phone": "+333",
                            "bind_email": "verify@outlook.com",
                        }
                    ],
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            web_gui._state["config"] = {
                "outlook_pool": str(pool_path),
                "outlook_used": str(used_path),
                "bind_email": "failed@outlook.com",
                "email_provider": "outlook",
            }

            with mock.patch.object(web_gui, "_outlook_results_dir", return_value=results_dir, create=True):
                with web_gui.app.test_client() as client:
                    summary_resp = client.get("/api/outlook-pool/summary")
                    list_resp = client.get("/api/outlook-pool/list")
                    detail_resp = client.get("/api/outlook-pool/detail", query_string={"email": "failed@outlook.com"})

            self.assertEqual(summary_resp.status_code, 200)
            self.assertEqual(list_resp.status_code, 200)
            self.assertEqual(detail_resp.status_code, 200)

            summary = summary_resp.get_json()
            self.assertTrue(summary["ok"])
            self.assertEqual(summary["total"], 6)
            self.assertEqual(
                summary["counts"],
                {
                    "unused": 1,
                    "reserved": 1,
                    "success": 1,
                    "register_failed": 1,
                    "verify_failed": 1,
                    "bad": 1,
                },
            )
            self.assertEqual(summary["current_bind_email"], "failed@outlook.com")

            items = list_resp.get_json()["items"]
            by_email = {item["email"]: item for item in items}
            self.assertEqual(items[0]["email"], "unused@outlook.com")
            self.assertEqual(items[1]["email"], "reserved@outlook.com")
            self.assertEqual(by_email["success@outlook.com"]["status"], "success")
            self.assertEqual(by_email["bad@outlook.com"]["status"], "bad")
            self.assertEqual(by_email["verify@outlook.com"]["status"], "verify_failed")
            self.assertEqual(by_email["failed@outlook.com"]["status"], "register_failed")
            self.assertEqual(by_email["unused@outlook.com"]["status"], "unused")
            self.assertTrue(by_email["success@outlook.com"]["has_result"])
            self.assertTrue(by_email["failed@outlook.com"]["has_result"])

            detail = detail_resp.get_json()["entry"]
            self.assertEqual(detail["email"], "failed@outlook.com")
            self.assertEqual(detail["status"], "register_failed")
            self.assertEqual(detail["phone"], "+222-new")
            self.assertEqual(detail["bind_email"], "failed@outlook.com")
            self.assertEqual(detail["sub2api_id"], "")

    def test_api_outlook_pool_actions_update_config_and_used_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            pool_path = Path(tmp) / "outlook.txt"
            used_path = Path(tmp) / "outlook_used.txt"
            results_dir = Path(tmp) / "results"
            results_dir.mkdir()

            pool_path.write_text(
                "\n".join(
                    [
                        "bad@outlook.com----pw----cid----rt",
                        "unused-a@outlook.com----pw----cid----rt",
                        "unused-b@outlook.com----pw----cid----rt",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            used_path.write_text(
                "2026-06-04 11:00:00\tbad@outlook.com\tbad\n",
                encoding="utf-8",
            )
            web_gui._state["config"] = {
                "outlook_pool": str(pool_path),
                "outlook_used": str(used_path),
                "bind_email": "",
                "email_provider": "",
            }

            with mock.patch.object(web_gui, "_outlook_results_dir", return_value=results_dir, create=True):
                with mock.patch.object(web_gui, "_save_config_file") as save_cfg:
                    with web_gui.app.test_client() as client:
                        bad_assign = client.post(
                            "/api/outlook-pool/action",
                            json={"action": "assign_for_run", "email": "bad@outlook.com"},
                        )
                        reserve_next = client.post(
                            "/api/outlook-pool/action",
                            json={"action": "reserve_next_unused"},
                        )
                        assign_specific = client.post(
                            "/api/outlook-pool/action",
                            json={"action": "assign_for_run", "email": "unused-b@outlook.com"},
                        )
                        mark_resp = client.post(
                            "/api/outlook-pool/action",
                            json={"action": "mark_status", "email": "unused-b@outlook.com", "status": "verify_failed"},
                        )

            self.assertEqual(bad_assign.status_code, 400)
            self.assertFalse(bad_assign.get_json()["ok"])

            reserve_data = reserve_next.get_json()
            self.assertEqual(reserve_next.status_code, 200)
            self.assertTrue(reserve_data["ok"])
            self.assertEqual(reserve_data["email"], "unused-a@outlook.com")
            self.assertEqual(web_gui._state["config"]["bind_email"], "unused-b@outlook.com")
            self.assertEqual(web_gui._state["config"]["email_provider"], "outlook")
            self.assertEqual(save_cfg.call_count, 2)

            assign_data = assign_specific.get_json()
            self.assertEqual(assign_specific.status_code, 200)
            self.assertEqual(assign_data["email"], "unused-b@outlook.com")
            self.assertEqual(assign_data["entry"]["status"], "reserved")

            mark_data = mark_resp.get_json()
            self.assertEqual(mark_resp.status_code, 200)
            self.assertEqual(mark_data["entry"]["status"], "verify_failed")

            lines = used_path.read_text(encoding="utf-8").splitlines()
            self.assertTrue(any("unused-a@outlook.com\treserved" in line for line in lines))
            self.assertTrue(any("unused-b@outlook.com\treserved" in line for line in lines))
            self.assertTrue(any("unused-b@outlook.com\tverify_failed" in line for line in lines))

    def test_api_outlook_pool_messages_returns_recent_mail_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            pool_path = Path(tmp) / "outlook.txt"
            used_path = Path(tmp) / "outlook_used.txt"
            results_dir = Path(tmp) / "results"
            results_dir.mkdir()
            pool_path.write_text(
                "mailbox@outlook.com----pw----cid----rt\n",
                encoding="utf-8",
            )
            web_gui._state["config"] = {
                "outlook_pool": str(pool_path),
                "outlook_used": str(used_path),
                "bind_email": "",
                "email_provider": "outlook",
            }

            fake_messages = [
                {
                    "id": "m1",
                    "from": "noreply@openai.com",
                    "subject": "code",
                    "body": "654321",
                }
            ]

            fake_client = mock.Mock()
            fake_client.list_recent_messages.return_value = fake_messages

            with mock.patch.object(web_gui, "_outlook_results_dir", return_value=results_dir, create=True):
                with mock.patch.object(web_gui, "OutlookMailClient", return_value=fake_client, create=True):
                    with web_gui.app.test_client() as client:
                        resp = client.get(
                            "/api/outlook-pool/messages",
                            query_string={"email": "mailbox@outlook.com", "limit": 20},
                        )

            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertTrue(data["ok"])
            self.assertEqual(data["email"], "mailbox@outlook.com")
            self.assertEqual(data["items"], fake_messages)
            fake_client.list_recent_messages.assert_called_once_with(limit=20, include_body=True)


if __name__ == "__main__":
    unittest.main()

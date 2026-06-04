import subprocess
import unittest

import web_gui


class WebGuiHtmlTests(unittest.TestCase):
    def test_inline_script_block_wraps_ui_bootstrap_code(self):
        html = web_gui._HTML
        js_start = html.index("function G(id)")
        script_open = html.rfind("<script>", 0, js_start)
        script_close = html.find("</script>", js_start)

        self.assertNotEqual(script_open, -1, "UI bootstrap JS 前缺少 <script> 标签")
        self.assertNotEqual(script_close, -1, "UI bootstrap JS 后缺少 </script> 标签")
        self.assertLess(script_open, js_start)
        self.assertGreater(script_close, js_start)


    def test_stats_and_thread_log_ui_are_present(self):
        html = web_gui._HTML

        self.assertIn('id="total-ok-count"', html)
        self.assertIn('id="total-fail-count"', html)
        self.assertIn('id="log-tabs"', html)
        self.assertIn("function setActiveLogTab", html)

    def test_plus_form_fields_are_persisted_and_restored(self):
        html = web_gui._HTML

        self.assertIn("plus_method:G('plus_method').value", html)
        self.assertIn("plus_email:G('plus_email').value", html)
        self.assertIn("plus_phone:G('plus_phone').value", html)
        self.assertIn("plus_pin:G('plus_pin').value", html)
        self.assertIn("plus_country:G('plus_country').value", html)
        self.assertIn("plus_currency:G('plus_currency').value", html)
        self.assertIn("G('plus_method').value=c.plus_method||'gopay'", html)
        self.assertIn("G('plus_email').value=c.plus_email||''", html)
        self.assertIn("G('plus_country').value=c.plus_country||'ID'", html)
        self.assertIn("G('plus_currency').value=c.plus_currency||'IDR'", html)
        self.assertIn("logTabsEl.innerHTML=`<button", html)

    def test_outlook_pool_textarea_is_persisted_and_restored(self):
        html = web_gui._HTML

        self.assertIn('id="outlook_pool"', html)
        self.assertIn("outlook_pool:G('outlook_pool').value", html)
        self.assertIn("G('outlook_pool').value=c.outlook_pool||''", html)
        self.assertIn("G('outlook-group').style.display", html)

    def test_outlook_pool_view_and_actions_are_present(self):
        html = web_gui._HTML

        self.assertIn('id="nav-outlook-pool"', html)
        self.assertIn('id="view-main"', html)
        self.assertIn('id="view-outlook-pool"', html)
        self.assertIn('id="outlook-pool-summary"', html)
        self.assertIn('id="outlook-pool-list"', html)
        self.assertIn('id="outlook-pool-detail"', html)
        self.assertIn('id="outlook-pool-messages"', html)
        self.assertIn("function switchView", html)
        self.assertIn("function loadOutlookPoolSummary", html)
        self.assertIn("function loadOutlookPoolList", html)
        self.assertIn("function loadOutlookPoolDetail", html)
        self.assertIn("function loadOutlookPoolMessages", html)
        self.assertIn("function actOnOutlookPool", html)

    def test_outlook_pool_view_has_visible_import_controls(self):
        html = web_gui._HTML

        self.assertIn('id="outlook-pool-editor"', html)
        self.assertIn('id="outlook-pool-save"', html)
        self.assertIn('id="outlook-pool-file"', html)
        self.assertIn("function saveOutlookPoolEditor", html)
        self.assertIn("function syncOutlookPoolEditor", html)
        self.assertIn("function importOutlookPoolFile", html)

    def test_inline_script_is_parseable_by_node(self):
        html = web_gui._HTML
        js_start = html.index("<script>") + len("<script>")
        js_end = html.rindex("</script>")
        script = html[js_start:js_end]

        proc = subprocess.run(
            [
                "node",
                "-e",
                "const fs=require('fs'); const src=fs.readFileSync(0,'utf8'); new Function(src);",
            ],
            input=script.encode("utf-8"),
            capture_output=True,
        )

        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", errors="replace"))

    def test_primary_labels_are_not_mojibake(self):
        html = web_gui._HTML

        self.assertIn("就绪", html)
        self.assertIn("下载结果", html)
        self.assertIn("注册配置", html)
        self.assertIn("运行日志", html)


if __name__ == "__main__":
    unittest.main()

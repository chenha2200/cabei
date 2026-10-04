import importlib.util
import os
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("email_status", "scripts/email-status.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class StatusTests(unittest.TestCase):
    def test_status_messages(self):
        env={"GITHUB_SERVER_URL":"https://github.com","GITHUB_REPOSITORY":"chenha2200/cabei","GITHUB_RUN_ID":"123"}
        with patch.dict(os.environ,env), patch.object(module,"api",return_value={"jobs":[]}):
            self.assertIn("部署成功",module.compose("success","success")[0])
            self.assertIn("部署尚未確認",module.compose("success","pending")[0])
            self.assertIn("部署失敗",module.compose("success","failure")[0])
            self.assertIn("更新失敗",module.compose("failure","success")[0])
    def test_missing_secrets_never_sends(self):
        with patch.dict(os.environ,{},clear=True), patch.object(module,"send") as send:
            module.main()
            send.assert_not_called()

unittest.main()

import json
import tempfile
import unittest
from pathlib import Path

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover
    FastAPI = None
    TestClient = None

from backend.models.task import Task


@unittest.skipIf(FastAPI is None, "fastapi is not installed in this Python environment")
class ApiSmokeTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        self.old_data_file = Task.DATA_FILE
        Task.DATA_FILE = str(self.tmp_path / "tasks.json")

        final_path = self.tmp_path / "final.png"
        model_path = self.tmp_path / "model.png"
        dress_path = self.tmp_path / "dress.png"
        png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        final_path.write_bytes(png_bytes)
        model_path.write_bytes(png_bytes)
        dress_path.write_bytes(png_bytes)

        task_data = {
            "task_id": "api1",
            "name": "api smoke",
            "status": "completed",
            "progress": 100,
            "model_file": str(model_path),
            "dress_file": str(dress_path),
            "face_file": None,
            "scene": "影棚",
            "scene_prompt": "",
            "resolution": "1k",
            "face_swap": False,
            "pose": "保持原姿势",
            "pose_mode": "stable",
            "preserve_face": True,
            "generation_mode": "stable",
            "parent_task_id": None,
            "rerun_index": 1,
            "output_files": {"final": str(final_path)},
            "error_message": "",
            "created_at": "2026-06-30T00:00:00",
            "completed_at": "2026-06-30T00:01:00",
            "steps": {
                "dress": "completed",
                "face": "skipped",
                "scene": "completed",
                "upscale": "skipped",
            },
        }
        Path(Task.DATA_FILE).write_text(
            json.dumps([task_data], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        from backend.routers import result, task

        app = FastAPI()
        app.include_router(task.router)
        app.include_router(result.router)
        self.client = TestClient(app)

    def tearDown(self):
        Task.DATA_FILE = self.old_data_file
        self.tmpdir.cleanup()

    def test_tasks_endpoint(self):
        response = self.client.get("/api/tasks")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["tasks"][0]["task_id"], "api1")
        self.assertEqual(data["tasks"][0]["output_files"], {"final": True})

    def test_result_endpoint(self):
        response = self.client.get("/api/task/api1/result")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/png")


if __name__ == "__main__":
    unittest.main()

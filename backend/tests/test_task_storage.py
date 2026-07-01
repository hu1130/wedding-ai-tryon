import json
import os
import tempfile
import unittest
from pathlib import Path

from backend.models.task import Task


def make_task(task_id: str, **overrides):
    data = {
        "task_id": task_id,
        "name": f"任务_{task_id}",
        "status": "completed",
        "progress": 100,
        "model_file": "uploads/model.png",
        "dress_file": "uploads/dress.png",
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
        "output_files": {"final": f"outputs/{task_id}/final.png"},
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
    data.update(overrides)
    return data


class TaskStorageTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.old_data_file = Task.DATA_FILE
        Task.DATA_FILE = str(Path(self.tmpdir.name) / "tasks.json")

    def tearDown(self):
        Task.DATA_FILE = self.old_data_file
        self.tmpdir.cleanup()

    def write_tasks(self, data):
        Path(Task.DATA_FILE).write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def read_raw_tasks(self):
        return json.loads(Path(Task.DATA_FILE).read_text(encoding="utf-8-sig"))

    def test_historical_value_wrapper_is_flattened_without_ghost_task(self):
        self.write_tasks([
            {"value": [make_task("wrapped1")], "Count": 1},
            make_task("top1"),
            {"name": "bad record without task id"},
        ])

        tasks = Task.list_all()
        self.assertEqual(len(tasks), 2)
        self.assertIsNotNone(Task.get("wrapped1"))
        self.assertIsNotNone(Task.get("top1"))
        self.assertIsNone(Task.get("missing"))
        self.assertFalse(any(not item["model_file"] for item in tasks))

    def test_from_dict_rejects_missing_task_id(self):
        with self.assertRaises(ValueError):
            Task.from_dict({"value": [], "Count": 0})

    def test_save_writes_project_relative_paths(self):
        project_root = Task.project_root()
        model_abs = os.path.join(project_root, "uploads", "model.png")
        dress_abs = os.path.join(project_root, "uploads", "dress.png")
        final_abs = os.path.join(project_root, "outputs", "save1", "final.png")

        task = Task(task_id="save1", model_file=model_abs, dress_file=dress_abs)
        task.output_files["final"] = final_abs
        task.save()

        raw = self.read_raw_tasks()
        self.assertEqual(raw[0]["model_file"], "uploads/model.png")
        self.assertEqual(raw[0]["dress_file"], "uploads/dress.png")
        self.assertEqual(raw[0]["output_files"]["final"], "outputs/save1/final.png")

    def test_delete_removes_record(self):
        self.write_tasks([make_task("delete1"), make_task("keep1")])

        deleted = Task.delete("delete1")
        self.assertIsNotNone(deleted)
        self.assertIsNone(Task.get("delete1"))
        self.assertIsNotNone(Task.get("keep1"))
        self.assertEqual(len(Task.list_all()), 1)


if __name__ == "__main__":
    unittest.main()

"""任务数据模型"""
import json
import os
import threading
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class StepStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


class Task:
    """任务模型，用 JSON 文件持久化"""

    DATA_FILE = ""
    _FILE_LOCK = threading.Lock()
    _PATH_ROOT_NAMES = ("uploads", "outputs")

    def __init__(
        self,
        task_id: Optional[str] = None,
        name: str = "",
        model_file: str = "",
        dress_file: str = "",
        face_file: Optional[str] = None,
        scene: str = "海边",
        scene_prompt: str = "",
        resolution: str = "1k",
        face_swap: bool = False,
        pose: str = "保持原姿势",
        pose_mode: str = "stable",
        preserve_face: bool = True,
        generation_mode: str = "stable",
        parent_task_id: Optional[str] = None,
        rerun_index: int = 1,
    ):
        self.task_id = task_id or uuid.uuid4().hex[:12]
        self.name = name or f"任务_{self.task_id}"
        self.status = TaskStatus.PENDING
        self.progress = 0.0  # 0~100
        self.model_file = model_file
        self.dress_file = dress_file
        self.face_file = face_file
        self.scene = scene
        self.scene_prompt = scene_prompt
        self.resolution = resolution
        self.face_swap = face_swap
        self.pose = pose
        self.pose_mode = pose_mode
        self.preserve_face = preserve_face
        self.generation_mode = generation_mode
        self.parent_task_id = parent_task_id
        self.rerun_index = rerun_index
        self.output_files = {}
        self.error_message = ""
        self.created_at = datetime.now().isoformat()
        self.completed_at = ""
        self.steps = {
            "dress": StepStatus.PENDING,
            "face": StepStatus.PENDING,
            "scene": StepStatus.PENDING,
            "upscale": StepStatus.PENDING,
        }

    def to_dict(self):
        return {
            "task_id": self.task_id,
            "name": self.name,
            "status": self.status.value,
            "progress": self.progress,
            "model_file": self.to_storage_path(self.model_file),
            "dress_file": self.to_storage_path(self.dress_file),
            "face_file": self.to_storage_path(self.face_file),
            "scene": self.scene,
            "scene_prompt": self.scene_prompt,
            "resolution": self.resolution,
            "face_swap": self.face_swap,
            "pose": self.pose,
            "pose_mode": self.pose_mode,
            "preserve_face": self.preserve_face,
            "generation_mode": self.generation_mode,
            "parent_task_id": self.parent_task_id,
            "rerun_index": self.rerun_index,
            "output_files": {
                key: self.to_storage_path(path)
                for key, path in self.output_files.items()
            },
            "error_message": self.error_message,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "steps": {k: v.value for k, v in self.steps.items()},
        }

    def to_public_dict(self):
        data = self.to_dict()
        for key in ["model_file", "dress_file", "face_file"]:
            if data.get(key):
                data[key] = os.path.basename(data[key])
        data["output_files"] = {
            key: True
            for key, path in self.output_files.items()
            if path and os.path.exists(self.resolve_storage_path(path))
        }
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        if not isinstance(data, dict) or not data.get("task_id"):
            raise ValueError("无效任务记录：缺少 task_id")

        task = cls(
            task_id=data.get("task_id"),
            name=data.get("name", ""),
            model_file=cls.resolve_storage_path(data.get("model_file", "")),
            dress_file=cls.resolve_storage_path(data.get("dress_file", "")),
            face_file=cls.resolve_storage_path(data.get("face_file")),
            scene=data.get("scene", "海边"),
            scene_prompt=data.get("scene_prompt", ""),
            resolution=data.get("resolution", "1k"),
            face_swap=data.get("face_swap", False),
            pose=data.get("pose", "保持原姿势"),
            pose_mode=data.get("pose_mode", "stable"),
            preserve_face=data.get("preserve_face", True),
            generation_mode=data.get("generation_mode", "stable"),
            parent_task_id=data.get("parent_task_id"),
            rerun_index=int(data.get("rerun_index", 1) or 1),
        )
        task.status = TaskStatus(data.get("status", "pending"))
        task.progress = data.get("progress", 0)
        task.output_files = {
            key: cls.resolve_storage_path(path)
            for key, path in data.get("output_files", {}).items()
        }
        task.error_message = data.get("error_message", "")
        task.created_at = data.get("created_at", datetime.now().isoformat())
        task.completed_at = data.get("completed_at", "")
        raw_steps = data.get("steps", {})
        for k, v in raw_steps.items():
            if k in task.steps:
                task.steps[k] = StepStatus(v)
        return task

    @classmethod
    def _data_path(cls) -> str:
        if not cls.DATA_FILE:
            cls.DATA_FILE = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "tasks.json"
            )
        return cls.DATA_FILE

    @classmethod
    def project_root(cls) -> str:
        return os.path.abspath(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        )

    @classmethod
    def _relative_from_known_root(cls, path: str) -> Optional[str]:
        normalized = path.replace("\\", "/")
        lowered_parts = [part.lower() for part in normalized.split("/")]
        for root_name in cls._PATH_ROOT_NAMES:
            if root_name in lowered_parts:
                index = lowered_parts.index(root_name)
                return "/".join(normalized.split("/")[index:])
        return None

    @classmethod
    def to_storage_path(cls, path: Optional[str]) -> Optional[str]:
        """把运行时路径写成可迁移的项目相对路径。"""
        if not path:
            return path

        path = str(path)
        project_root = cls.project_root()
        path_abs = os.path.abspath(path) if os.path.isabs(path) else None

        if path_abs:
            try:
                if os.path.commonpath([project_root, path_abs]) == project_root:
                    return os.path.relpath(path_abs, project_root).replace("\\", "/")
            except ValueError:
                pass

            relative = cls._relative_from_known_root(path_abs)
            if relative:
                current_path = os.path.abspath(os.path.join(project_root, relative))
                if os.path.exists(current_path):
                    return relative
            return path

        return path.replace("\\", "/")

    @classmethod
    def resolve_storage_path(cls, path: Optional[str]) -> Optional[str]:
        """把任务记录中的相对路径、文件 ID 或历史绝对路径解析为运行时路径。"""
        if not path:
            return path

        path = str(path)
        if os.path.isabs(path):
            if os.path.exists(path):
                return path

            relative = cls._relative_from_known_root(path)
            if relative:
                current_path = os.path.abspath(os.path.join(cls.project_root(), relative))
                if os.path.exists(current_path):
                    return current_path
            return path

        normalized = path.replace("\\", "/")
        if "/" not in normalized:
            upload_path = os.path.abspath(
                os.path.join(cls.project_root(), "uploads", normalized)
            )
            if os.path.exists(upload_path):
                return upload_path

        return os.path.abspath(os.path.join(cls.project_root(), normalized))

    @classmethod
    def _normalize_task_records(cls, raw_tasks) -> list[dict]:
        """兼容历史 {value: [...], Count: n} 包装格式，并过滤无 task_id 的坏记录。"""
        if not isinstance(raw_tasks, list):
            return []

        records = []
        for item in raw_tasks:
            if not isinstance(item, dict):
                continue

            if item.get("task_id"):
                records.append(item)
                continue

            wrapped = item.get("value")
            if isinstance(wrapped, list):
                records.extend(
                    record
                    for record in wrapped
                    if isinstance(record, dict) and record.get("task_id")
                )
        return records

    @classmethod
    def _read_task_records(cls) -> list[dict]:
        path = cls._data_path()
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8-sig") as f:
            return cls._normalize_task_records(json.load(f))

    def save(self):
        """保存到 tasks.json"""
        path = self._data_path()
        with self._FILE_LOCK:
            tasks = []
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8-sig") as f:
                        tasks = self._normalize_task_records(json.load(f))
                except FileNotFoundError:
                    tasks = []
                except json.JSONDecodeError as exc:
                    raise RuntimeError("任务数据文件损坏，请先修复 tasks.json") from exc

            # 更新或新增
            updated = False
            for i, t in enumerate(tasks):
                if t.get("task_id") == self.task_id:
                    tasks[i] = self.to_dict()
                    updated = True
                    break
            if not updated:
                tasks.append(self.to_dict())

            tmp_path = f"{path}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(tasks, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, path)

    @classmethod
    def get(cls, task_id: str) -> Optional["Task"]:
        path = cls._data_path()
        if not os.path.exists(path):
            return None
        with cls._FILE_LOCK:
            tasks = cls._read_task_records()
        for t in tasks:
            if t.get("task_id") == task_id:
                return cls.from_dict(t)
        return None

    @classmethod
    def list_all(cls) -> list[dict]:
        path = cls._data_path()
        if not os.path.exists(path):
            return []
        with cls._FILE_LOCK:
            tasks = cls._read_task_records()
        public_tasks = [cls.from_dict(t).to_public_dict() for t in tasks]
        return sorted(public_tasks, key=lambda x: x.get("created_at", ""), reverse=True)

    @classmethod
    def list_internal(cls) -> list["Task"]:
        path = cls._data_path()
        if not os.path.exists(path):
            return []
        with cls._FILE_LOCK:
            tasks = cls._read_task_records()
        return [cls.from_dict(t) for t in tasks]

    @classmethod
    def delete(cls, task_id: str) -> Optional["Task"]:
        path = cls._data_path()
        if not os.path.exists(path):
            return None

        with cls._FILE_LOCK:
            tasks = cls._read_task_records()

            deleted = None
            remaining = []
            for item in tasks:
                if item.get("task_id") == task_id:
                    deleted = item
                else:
                    remaining.append(item)

            if deleted is None:
                return None

            tmp_path = f"{path}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(remaining, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, path)

        return cls.from_dict(deleted)

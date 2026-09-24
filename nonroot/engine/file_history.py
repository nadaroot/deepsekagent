"""
File History and Rollback Manager for NonRoot.
Tracks file creations, edits, and directory creations per agent turn,
enabling reliable file rollbacks when reverting agent actions.
"""

import os
import time
import json
import uuid
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional, Set


class FileHistoryManager:
    def __init__(self, workspace: Path):
        self.workspace = Path(workspace).resolve()
        self.current_turn: int = 0
        self.history_dir = self._get_history_dir()
        self.snapshots_dir = self.history_dir / "snapshots"
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.entries_file = self.history_dir / "entries.json"
        self.entries: List[Dict[str, Any]] = self._load_entries()

    def set_workspace(self, workspace: Path):
        self.workspace = Path(workspace).resolve()
        self.history_dir = self._get_history_dir()
        self.snapshots_dir = self.history_dir / "snapshots"
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.entries_file = self.history_dir / "entries.json"
        self.entries = self._load_entries()

    def _get_history_dir(self) -> Path:
        ws_hash = hex(abs(hash(str(self.workspace))))[2:10]
        candidates = [
            Path.home() / ".nonroot" / "file_history" / ws_hash,
            self.workspace / ".nonroot_history",
            Path(tempfile.gettempdir()) / "nonroot_file_history" / ws_hash
        ]
        for c in candidates:
            try:
                c.mkdir(parents=True, exist_ok=True)
                test_file = c / ".test_write"
                test_file.touch()
                test_file.unlink()
                return c
            except Exception:
                continue
        fallback = Path(tempfile.gettempdir()) / f"nonroot_hist_{ws_hash}"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback

    def _load_entries(self) -> List[Dict[str, Any]]:
        if self.entries_file.exists():
            try:
                with open(self.entries_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save_entries(self):
        try:
            with open(self.entries_file, "w", encoding="utf-8") as f:
                json.dump(self.entries, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def set_turn(self, turn: int):
        self.current_turn = max(0, int(turn))

    def record_file_before_change(self, file_path: Path):
        """
        Records the file state before a write or edit operation.
        """
        p = Path(file_path).resolve()
        p_str = str(p)

        # If already recorded in the current turn for this exact path,
        # we keep the initial snapshot so rolling back returns to pre-turn state!
        for e in self.entries:
            if e.get("turn") == self.current_turn and e.get("path") == p_str:
                return

        if p.exists() and p.is_file():
            snap_id = f"snap_{self.current_turn}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
            bak_path = self.snapshots_dir / snap_id
            try:
                shutil.copy2(p, bak_path)
                self.entries.append({
                    "turn": self.current_turn,
                    "action": "modify",
                    "path": p_str,
                    "backup_file": str(bak_path),
                    "timestamp": time.time()
                })
                self._save_entries()
            except Exception:
                pass
        else:
            self.entries.append({
                "turn": self.current_turn,
                "action": "create",
                "path": p_str,
                "backup_file": None,
                "timestamp": time.time()
            })
            self._save_entries()

    def record_dir_before_create(self, dir_path: Path):
        """
        Records a directory before creation (e.g. cloned website folder).
        """
        p = Path(dir_path).resolve()
        p_str = str(p)

        for e in self.entries:
            if e.get("turn") == self.current_turn and e.get("path") == p_str:
                return

        if not p.exists():
            self.entries.append({
                "turn": self.current_turn,
                "action": "create_dir",
                "path": p_str,
                "backup_file": None,
                "timestamp": time.time()
            })
            self._save_entries()

    def rollback_to_turn(self, target_turn: int) -> List[str]:
        """
        Reverts all file operations recorded with turn >= target_turn
        in reverse chronological order.
        """
        target_turn = max(0, int(target_turn))
        to_revert = [e for e in self.entries if e.get("turn", 0) >= target_turn]
        remaining = [e for e in self.entries if e.get("turn", 0) < target_turn]

        affected: Set[str] = set()

        for entry in reversed(to_revert):
            action = entry.get("action")
            p = Path(entry.get("path", ""))

            if action == "create":
                if p.exists() and p.is_file():
                    try:
                        p.unlink()
                        affected.add(str(p))
                    except Exception:
                        pass
                self._clean_empty_parents(p.parent)

            elif action == "create_dir":
                if p.exists() and p.is_dir():
                    try:
                        shutil.rmtree(p, ignore_errors=True)
                        affected.add(str(p))
                    except Exception:
                        pass
                self._clean_empty_parents(p.parent)

            elif action == "modify":
                bak_str = entry.get("backup_file")
                bak = Path(bak_str) if bak_str else None
                if bak and bak.exists():
                    try:
                        p.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(bak, p)
                        affected.add(str(p))
                    except Exception:
                        pass
                # Clean up backup file
                if bak and bak.exists():
                    try:
                        bak.unlink()
                    except Exception:
                        pass

        self.entries = remaining
        self._save_entries()
        self.current_turn = target_turn
        return sorted(list(affected))

    def _clean_empty_parents(self, parent: Path):
        """Recursively removes empty parent directories up to workspace."""
        try:
            curr = parent.resolve()
            while curr != self.workspace and curr != self.workspace.parent and curr.exists() and curr.is_dir():
                if not any(curr.iterdir()):
                    curr.rmdir()
                    curr = curr.parent.resolve()
                else:
                    break
        except Exception:
            pass

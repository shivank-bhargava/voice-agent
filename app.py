import json
import queue
import re
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import requests
import sounddevice as sd
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from vosk import KaldiRecognizer, Model


DATA_PATH = Path("list_data.json")
LEARNING_DATA_PATH = Path("user_learning.json")
VOSK_MODEL_CANDIDATES = [
    Path("vosk-model-en-us-0.22"),
]
OLLAMA_MODEL = "llama3.1:8b"
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
USE_FALLBACK_WHEN_OLLAMA_UNAVAILABLE = False
INTENT_MODE = "ambient"  # "ambient" captures implied tasks; "strict" requires explicit commands.
SAMPLE_RATE = 16000
OLLAMA_MIN_CONFIDENCE = 0.65
AUTO_START_LISTENING = True  # Automatically start listening on startup
IGNORE_PHRASES = {
    "hello",
    "hi",
    "how are you",
    "what time is it",
    "thanks",
    "thank you",
    "good morning",
    "good night",
    "good afternoon",
    "good evening",
    "bye",
    "goodbye",
    "see you",
    "okay",
    "ok",
    "alright",
    "sure",
    "yes",
    "no",
    "maybe",
    "i think so",
    "i don't know",
    "i'm not sure",
    "whatever",
    "cool",
    "nice",
    "great",
    "awesome",
    "wow",
    "oh",
    "ah",
    "um",
    "uh",
    "hmm",
    "interesting",
    "really",
    "seriously",
    "literally",
    "actually",
    "basically",
    "anyway",
    "anyways",
    "so",
    "well",
    "like",
    "you know",
    "right",
    "yeah",
    "yep",
    "yup",
    "nope",
    "uh-huh",
    "uh-oh",
    "oops",
    "sorry",
    "excuse me",
    "pardon me",
    "watch out",
    "be careful",
    "take care",
    "good luck",
    "have fun",
    "enjoy",
    "cheers",
    "congratulations",
    "congrats",
    "happy birthday",
    "merry christmas",
    "happy holidays",
    "bless you",
    "gesundheit",
    "amen",
    "hallelujah",
    "omg",
    "oh my god",
    "oh my gosh",
    "holy cow",
    "holy moly",
    "good grief",
    "for crying out loud",
    "give me a break",
    "come on",
    "seriously",
    "you're kidding",
    "you're joking",
    "no way",
    "yes way",
    "totally",
    "absolutely",
    "definitely",
    "certainly",
    "of course",
    "sure thing",
    "no problem",
    "no worries",
    "it's fine",
    "it's okay",
    "that's fine",
    "that's okay",
    "all good",
    "no big deal",
    "no biggie",
    "not a problem",
    "don't worry about it",
    "forget it",
    "never mind",
    "nevermind",
}
TRAILING_FILLER_WORDS = {"to", "too", "today", "please", "now"}


class ListItem(BaseModel):
    id: int
    text: str
    source_text: str
    list_type: str
    created_at: str
    completed: bool = False
    priority: int = 1  # 1=low, 2=medium, 3=high


class PendingItem(BaseModel):
    id: int
    text: str
    suggested_list_type: str
    confidence: float
    reason: str
    source_text: str
    created_at: str


class ListsResponse(BaseModel):
    grocery: List[ListItem]
    todo: List[ListItem]
    pending_review: List[PendingItem]
    transcript_log: List[str]
    listening: bool
    asr_status: str
    asr_model: str | None
    ollama_status: str
    ollama_model: str


class LocalAgentApp:
    def __init__(self) -> None:
        self.state_lock = threading.Lock()
        self.running = False
        self.audio_queue: queue.Queue[bytes] = queue.Queue()
        self.listening_thread: threading.Thread | None = None
        self.parser_thread: threading.Thread | None = None
        self.next_id = 1
        self.data = {
            "grocery": [],
            "todo": [],
            "pending_review": [],
            "transcript_log": [],
        }
        self.recent_additions: List[tuple[str, str]] = []
        self.vosk_model_path: Path | None = None
        self.vosk_model: Model | None = None
        self.model_lock = threading.Lock()
        self.is_model_loading = False
        self.ollama_status = "unknown"
        self.ollama_last_checked_at = 0.0
        self.ollama_check_interval_seconds = 3.0
        self._load_data()
        self._load_learning_data()

    def _load_data(self) -> None:
        if not DATA_PATH.exists():
            return
        raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        self.data["grocery"] = raw.get("grocery", [])
        self.data["todo"] = raw.get("todo", [])
        self.data["pending_review"] = raw.get("pending_review", [])
        self.data["transcript_log"] = raw.get("transcript_log", [])

        all_ids = [item["id"] for item in self.data["grocery"] + self.data["todo"]]
        self.next_id = max(all_ids) + 1 if all_ids else 1

    def _load_learning_data(self) -> None:
        """Load user learning data for adaptive behavior"""
        self.learning_data = {
            "user_corrections": [],  # Track when user corrects AI decisions
            "ignored_patterns": [],  # Patterns user consistently rejects
            "accepted_patterns": [],  # Patterns user consistently accepts
            "joke_indicators": [],  # User-specific joke patterns
            "confidence_adjustments": {},  # Per-pattern confidence adjustments
        }
        if LEARNING_DATA_PATH.exists():
            try:
                raw = json.loads(LEARNING_DATA_PATH.read_text(encoding="utf-8"))
                self.learning_data.update(raw)
            except Exception:
                pass

    def _save_learning_data(self) -> None:
        """Save user learning data"""
        LEARNING_DATA_PATH.write_text(json.dumps(self.learning_data, indent=2), encoding="utf-8")

    def record_user_feedback(self, transcript: str, item_text: str, accepted: bool, was_pending: bool = False) -> None:
        """Record user feedback for learning"""
        feedback = {
            "transcript": transcript,
            "item_text": item_text,
            "accepted": accepted,
            "was_pending": was_pending,
            "timestamp": datetime.utcnow().isoformat(),
        }
        with self.state_lock:
            self.learning_data["user_corrections"].append(feedback)
            # Keep only last 1000 corrections
            if len(self.learning_data["user_corrections"]) > 1000:
                self.learning_data["user_corrections"] = self.learning_data["user_corrections"][-1000:]
            self._save_learning_data()

    def _save_data(self) -> None:
        DATA_PATH.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def get_lists(self) -> Dict[str, Any]:
        with self.model_lock:
            if self.is_model_loading:
                asr_status = "loading"
            elif self.vosk_model:
                asr_status = "ready"
            elif self._resolve_vosk_model_path():
                asr_status = "not_loaded"
            else:
                asr_status = "missing_model"
            resolved_path = self.vosk_model_path or self._resolve_vosk_model_path()
            asr_model = resolved_path.name if resolved_path else None
        ollama_status = self._get_ollama_status()
        with self.state_lock:
            return {
                "grocery": self.data["grocery"],
                "todo": self.data["todo"],
                "pending_review": self.data["pending_review"],
                "transcript_log": self.data["transcript_log"][-40:],
                "listening": self.running,
                "asr_status": asr_status,
                "asr_model": asr_model,
                "ollama_status": ollama_status,
                "ollama_model": OLLAMA_MODEL,
            }

    def add_manual_item(self, text: str, list_type: str, priority: int = 1) -> Dict[str, Any]:
        if list_type not in {"grocery", "todo", "auto"}:
            raise ValueError("list_type must be grocery, todo, or auto")
        if priority not in {1, 2, 3}:
            raise ValueError("priority must be 1 (low), 2 (medium), or 3 (high)")
        if list_type == "auto":
            extracted, confidence, reason = self._extract_items_with_ollama(text)
            if extracted is None:
                raise ValueError("Ollama unavailable for auto classification")
            if not extracted:
                raise ValueError("No actionable list item detected")
            if confidence < OLLAMA_MIN_CONFIDENCE:
                pending = self.add_pending_item(
                    extracted[0].get("text", text),
                    extracted[0].get("list_type", "todo"),
                    confidence,
                    reason or "manual auto low confidence",
                    text,
                )
                return {"status": "queued_for_review", "pending_item": pending}
            item = extracted[0]
            list_type = item.get("list_type", "todo")
            text = self._clean_item_text(item.get("text", text))
        item = {
            "id": self.next_id,
            "text": text.strip(),
            "source_text": "manual",
            "list_type": list_type,
            "created_at": datetime.utcnow().isoformat(),
            "completed": False,
            "priority": priority,
        }
        with self.state_lock:
            self.data[list_type].append(item)
            self.next_id += 1
            self._save_data()
        return item

    def add_pending_item(
        self, text: str, suggested_list_type: str, confidence: float, reason: str, source_text: str
    ) -> Dict[str, Any]:
        pending = {
            "id": self.next_id,
            "text": text,
            "suggested_list_type": suggested_list_type if suggested_list_type in {"grocery", "todo"} else "todo",
            "confidence": round(confidence, 3),
            "reason": reason,
            "source_text": source_text,
            "created_at": datetime.utcnow().isoformat(),
        }
        with self.state_lock:
            self.data["pending_review"].append(pending)
            self.next_id += 1
            self._save_data()
        return pending

    def confirm_pending_item(self, pending_id: int, list_type: str, priority: int = 1) -> Dict[str, Any]:
        if list_type not in {"grocery", "todo"}:
            raise ValueError("list_type must be grocery or todo")
        if priority not in {1, 2, 3}:
            raise ValueError("priority must be 1 (low), 2 (medium), or 3 (high)")
        with self.state_lock:
            for idx, pending in enumerate(self.data["pending_review"]):
                if pending["id"] != pending_id:
                    continue
                item = {
                    "id": self.next_id,
                    "text": pending["text"],
                    "source_text": pending.get("source_text", "pending-review"),
                    "list_type": list_type,
                    "created_at": datetime.utcnow().isoformat(),
                    "completed": False,
                    "priority": priority,
                }
                self.data[list_type].append(item)
                self.data["pending_review"].pop(idx)
                self.next_id += 1
                self._save_data()
                # Record user feedback for learning
                self.record_user_feedback(
                    pending.get("source_text", ""),
                    pending["text"],
                    accepted=True,
                    was_pending=True
                )
                return item
        raise ValueError("Pending item not found")

    def remove_pending_item(self, pending_id: int) -> None:
        with self.state_lock:
            before = len(self.data["pending_review"])
            removed_item = None
            for item in self.data["pending_review"]:
                if item["id"] == pending_id:
                    removed_item = item
                    break
            self.data["pending_review"] = [
                x for x in self.data["pending_review"] if x["id"] != pending_id
            ]
            if len(self.data["pending_review"]) != before:
                self._save_data()
                # Record user feedback for learning
                if removed_item:
                    self.record_user_feedback(
                        removed_item.get("source_text", ""),
                        removed_item["text"],
                        accepted=False,
                        was_pending=True
                    )
                return
        raise ValueError("Pending item not found")

    def clear_pending_items(self) -> None:
        with self.state_lock:
            self.data["pending_review"] = []
            self._save_data()

    def confirm_all_pending_items(self, list_type: str, priority: int = 1) -> int:
        if list_type not in {"grocery", "todo"}:
            raise ValueError("list_type must be grocery or todo")
        if priority not in {1, 2, 3}:
            raise ValueError("priority must be 1 (low), 2 (medium), or 3 (high)")
        with self.state_lock:
            pending_items = list(self.data["pending_review"])
            if not pending_items:
                return 0
            for pending in pending_items:
                item = {
                    "id": self.next_id,
                    "text": pending["text"],
                    "source_text": pending.get("source_text", "pending-review"),
                    "list_type": list_type,
                    "created_at": datetime.utcnow().isoformat(),
                    "completed": False,
                    "priority": priority,
                }
                self.data[list_type].append(item)
                self.next_id += 1
            self.data["pending_review"] = []
            self._save_data()
            return len(pending_items)

    def clear_transcript_log(self) -> None:
        with self.state_lock:
            self.data["transcript_log"] = []
            self._save_data()

    def toggle_item(self, item_id: int) -> None:
        with self.state_lock:
            for list_name in ("grocery", "todo"):
                for item in self.data[list_name]:
                    if item["id"] == item_id:
                        item["completed"] = not item["completed"]
                        self._save_data()
                        return
        raise ValueError("Item not found")

    def remove_item(self, item_id: int) -> None:
        with self.state_lock:
            for list_name in ("grocery", "todo"):
                before = len(self.data[list_name])
                removed_item = None
                for item in self.data[list_name]:
                    if item["id"] == item_id:
                        removed_item = item
                        break
                self.data[list_name] = [x for x in self.data[list_name] if x["id"] != item_id]
                if len(self.data[list_name]) != before:
                    self._save_data()
                    # Record user feedback for learning (deleting indicates rejection)
                    if removed_item:
                        self.record_user_feedback(
                            removed_item.get("source_text", ""),
                            removed_item["text"],
                            accepted=False,
                            was_pending=False
                        )
                    return
        raise ValueError("Item not found")

    def update_item_priority(self, item_id: int, priority: int) -> None:
        if priority not in {1, 2, 3}:
            raise ValueError("priority must be 1 (low), 2 (medium), or 3 (high)")
        with self.state_lock:
            for list_name in ("grocery", "todo"):
                for item in self.data[list_name]:
                    if item["id"] == item_id:
                        item["priority"] = priority
                        self._save_data()
                        return
        raise ValueError("Item not found")

    def sort_list(self, list_type: str, sort_by: str = "priority") -> None:
        if list_type not in {"grocery", "todo"}:
            raise ValueError("list_type must be grocery or todo")
        if sort_by not in {"priority", "created_at", "text"}:
            raise ValueError("sort_by must be priority, created_at, or text")
        
        with self.state_lock:
            if sort_by == "priority":
                # Sort by priority descending (high first), then by created_at
                self.data[list_type].sort(key=lambda x: (-x.get("priority", 1), x.get("created_at", "")))
            elif sort_by == "created_at":
                # Sort by created_at descending (newest first)
                self.data[list_type].sort(key=lambda x: x.get("created_at", ""), reverse=True)
            elif sort_by == "text":
                # Sort by text alphabetically
                self.data[list_type].sort(key=lambda x: x.get("text", "").lower())
            self._save_data()

    def start(self) -> None:
        if self.running:
            return
        self.vosk_model_path = self._resolve_vosk_model_path()
        if not self.vosk_model_path:
            raise RuntimeError(
                "No Vosk model found. Download one of these folders into project root: "
                + ", ".join(str(x) for x in VOSK_MODEL_CANDIDATES)
            )
        self._ensure_model_loaded()
        self._append_log(f"using vosk model: {self.vosk_model_path.name}")
        self.running = True
        self.listening_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.parser_thread = threading.Thread(target=self._parse_loop, daemon=True)
        self.listening_thread.start()
        self.parser_thread.start()

    def stop(self) -> None:
        self.running = False

    def _listen_loop(self) -> None:
        if not self.vosk_model:
            return
        recognizer = KaldiRecognizer(self.vosk_model, SAMPLE_RATE)
        last_partial = ""

        def callback(indata, frames, timing, status):  # type: ignore[no-untyped-def]
            if status:
                return
            self.audio_queue.put(bytes(indata))

        with sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            blocksize=8000,
            dtype="int16",
            channels=1,
            callback=callback,
        ):
            while self.running:
                chunk = self.audio_queue.get()
                if recognizer.AcceptWaveform(chunk):
                    text = json.loads(recognizer.Result()).get("text", "").strip()
                    if text:
                        normalized = self._normalize_transcript(text)
                        if normalized:
                            self._handle_transcript(normalized)
                else:
                    partial = json.loads(recognizer.PartialResult()).get("partial", "")
                    partial = self._normalize_transcript(partial)
                    if partial and partial != last_partial:
                        self._append_log(f"partial: {partial}")
                        last_partial = partial

    def _parse_loop(self) -> None:
        while self.running:
            time.sleep(0.1)

    def _append_log(self, line: str) -> None:
        with self.state_lock:
            self.data["transcript_log"].append(line)
            if len(self.data["transcript_log"]) > 200:
                self.data["transcript_log"] = self.data["transcript_log"][-200:]
            self._save_data()

    def _handle_transcript(self, transcript: str) -> None:
        self._append_log(f"heard: {transcript}")
        extracted, confidence, reason = self._extract_items_with_ollama(transcript)
        if extracted is None:
            if USE_FALLBACK_WHEN_OLLAMA_UNAVAILABLE:
                extracted = self._extract_items_fallback(transcript)
                confidence = 1.0
                reason = "fallback parser"
            else:
                self._append_log("ignored: ollama unavailable")
                return
        if not extracted:
            self._append_log("ignored: no list items detected")
            return
        for item in extracted:
            list_type = item.get("list_type")
            text = self._clean_item_text(item.get("text", ""))
            if list_type not in ("grocery", "todo") or not text:
                continue
            if not self._passes_item_quality(text):
                continue
            if self._is_recent_duplicate(list_type, text):
                self._append_log(f"ignored duplicate: [{list_type}] {text}")
                continue
            if confidence < OLLAMA_MIN_CONFIDENCE:
                self.add_pending_item(text, list_type, confidence, reason, transcript)
                self._append_log(f"queued for review: [{list_type}] {text} ({confidence:.2f})")
                continue
            with self.state_lock:
                self.data[list_type].append(
                    {
                        "id": self.next_id,
                        "text": text,
                        "source_text": transcript,
                        "list_type": list_type,
                        "created_at": datetime.utcnow().isoformat(),
                        "completed": False,
                        "priority": 1,  # Default to low priority for auto-added items
                    }
                )
                self._remember_item(list_type, text)
                self.next_id += 1
                self._save_data()

    def _extract_items_with_ollama(
        self, transcript: str
    ) -> tuple[List[Dict[str, str]] | None, float, str]:
        mode_rules = (
            "- Ambient mode: capture implied actionable items from natural conversation.\n"
            "- If speaker mentions obligations, plans, errands, reminders, purchases, or needs, extract them.\n"
            "- Example: 'i need to do my homework' => todo: 'do my homework'.\n"
            "- Example: 'we're out of milk' => grocery: 'milk'.\n"
            "- Example: 'i should call mom tomorrow' => todo: 'call mom tomorrow'.\n"
            if INTENT_MODE == "ambient"
            else "- Strict mode: only explicit add/remind/list commands should be extracted.\n"
        )
        
        # Add learning context from user feedback
        learning_context = ""
        with self.state_lock:
            recent_rejections = [f for f in self.learning_data["user_corrections"][-20:] if not f["accepted"]]
            if recent_rejections:
                learning_context = "\nUser has recently rejected these items (learn to avoid similar patterns):\n"
                for rejection in recent_rejections[-5:]:
                    learning_context += f"- '{rejection['item_text']}' from '{rejection['transcript']}'\n"
        
        prompt = (
            "You are an intelligent intent classifier and extractor for a voice assistant.\n"
            "Decide whether spoken text should add anything to either a grocery list or a todo list.\n"
            "Return ONLY valid JSON with this exact schema:\n"
            '{"should_add":true|false,"confidence":0.0,"items":[{"list_type":"grocery|todo","text":"string"}],"reason":"short string"}\n'
            "Rules:\n"
            "- Use semantic understanding, not keyword matching.\n"
            "- You are the primary decision maker. Do not rely on strict phrase templates.\n"
            "- Keep items short and specific (2-8 words max).\n"
            "- If speech has no actionable content, set should_add=false and items=[].\n"
            "- If speech implies a task or shopping intent, set should_add=true and extract items.\n"
            "- If the text appears garbled/noisy/asr-broken, set should_add=false with low confidence.\n"
            "- confidence must be between 0 and 1.\n"
            "- Do not guess items that were not spoken.\n"
            "- IGNORE: greetings, goodbyes, small talk, filler phrases, expressions of opinion, general statements.\n"
            "- IGNORE: 'i think', 'maybe', 'i don't know', 'not sure', 'probably' - these indicate uncertainty.\n"
            "- IGNORE: statements about past events unless they imply a recurring task.\n"
            "- IGNORE: compliments, complaints, or emotional expressions without actionable intent.\n"
            "- IGNORE: questions that don't imply a task (e.g., 'what's for dinner?' unless speaker needs to buy/make it).\n"
            "- IGNORE: jokes, sarcasm, humor, exaggeration, hyperbole.\n"
            "- IGNORE: phrases like 'just kidding', 'i'm joking', 'seriously', 'not really', 'just kidding around'.\n"
            "- IGNORE: obviously absurd or impossible items (e.g., 'buy a unicorn', 'fly to the moon').\n"
            "- IGNORE: hypothetical scenarios (e.g., 'if i were rich i would buy...').\n"
            "- IGNORE: song lyrics, movie quotes, jokes, puns.\n"
            "- EXTRACT: obligations, reminders, errands, shopping needs, appointments, deadlines.\n"
            "- EXTRACT: 'need to', 'have to', 'must', 'should', 'going to', 'planning to', 'want to'.\n"
            "- EXTRACT: 'out of', 'need more', 'running low on', 'forgot to buy' -> grocery.\n"
            "- EXTRACT: 'call', 'email', 'text', 'meet', 'visit', 'pick up', 'drop off' -> todo.\n"
            "- EXTRACT: 'clean', 'wash', 'fix', 'repair', 'organize', 'prepare' -> todo.\n"
            "- EXTRACT: 'pay bill', 'renew', 'register', 'sign up', 'apply' -> todo.\n"
            "- EXTRACT: 'buy', 'get', 'purchase', 'order' -> determine context (grocery vs todo).\n"
            + learning_context
            + mode_rules
            + "Output must be pure JSON only.\n"
            f"Speech: {transcript}"
        )
        body = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }
        try:
            response = requests.post(OLLAMA_URL, json=body, timeout=30)
            response.raise_for_status()
            content = response.json().get("response", "{}")
            parsed = json.loads(content)
            should_add = bool(parsed.get("should_add", False))
            confidence = float(parsed.get("confidence", 0.0))
            if confidence < OLLAMA_MIN_CONFIDENCE:
                return [], confidence, "low confidence"
            if not should_add:
                reason = str(parsed.get("reason", "")).strip()
                if reason:
                    self._append_log(f"ollama ignored: {reason}")
                return [], confidence, reason
            items = parsed.get("items", [])
            if not isinstance(items, list):
                return [], confidence, "invalid item list"
            cleaned: List[Dict[str, str]] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                list_type = item.get("list_type")
                text = self._clean_item_text(str(item.get("text", "")))
                if list_type in ("grocery", "todo") and self._passes_item_quality(text):
                    cleaned.append({"list_type": list_type, "text": text})
            reason = str(parsed.get("reason", "")).strip()
            return cleaned, confidence, reason
        except Exception as exc:
            self._append_log(f"ollama error: {exc}")
            return None, 0.0, "ollama error"

    def _extract_items_fallback(self, transcript: str) -> List[Dict[str, str]]:
        # Intentionally minimal fallback: when Ollama is unavailable and fallback is enabled,
        # we do not guess list type from brittle hardcoded rules.
        self._append_log("fallback unavailable: ollama-only decision mode")
        return []

    def _normalize_transcript(self, text: str) -> str:
        cleaned = re.sub(r"\s+", " ", text.strip().lower())
        if not cleaned:
            return ""
        # Remove repeated leading artifacts from streaming ASR.
        cleaned = re.sub(r"^(the\s+)+i\s+", "i ", cleaned)
        cleaned = re.sub(r"^(the\s+){2,}", "", cleaned)
        cleaned = re.sub(r"^the dude i\s+", "i ", cleaned)
        cleaned = re.sub(r"^the dude\s+", "", cleaned)
        # Common Vosk mishearing in this workflow.
        cleaned = cleaned.replace("my home", "my homework")
        cleaned = cleaned.replace("do my home", "do my homework")
        cleaned = re.sub(r"\bhomework(?:work)+\b", "homework", cleaned)
        cleaned = re.sub(r"\bgrocery(?:ry)+\b", "grocery", cleaned)
        cleaned = re.sub(r"\b(?:to)(?:o){2,}\b", "to", cleaned)
        # Trim repeated filler at end.
        cleaned = re.sub(r"\b(the|uh|um)\s*$", "", cleaned).strip()
        return cleaned

    def _passes_item_quality(self, text: str) -> bool:
        if len(text) < 2 or len(text) > 64:
            return False
        lowered = text.lower()
        if lowered in IGNORE_PHRASES:
            return False
        if len(lowered.split()) > 10:
            return False
        alpha_chars = sum(ch.isalpha() for ch in lowered)
        if alpha_chars < 3:
            return False
        
        # Additional quality checks for non-task phrases
        # Check for uncertainty indicators
        uncertainty_words = {"maybe", "might", "could", "possibly", "perhaps", "probably", "think about", "consider"}
        if any(word in lowered for word in uncertainty_words):
            return False
        
        # Check for questions (unless they imply a task)
        if lowered.endswith("?") or lowered.startswith(("what", "when", "where", "who", "why", "how")):
            # Allow certain question types that imply tasks
            task_questions = {"what should i", "what do i need", "when should i", "where can i"}
            if not any(q in lowered for q in task_questions):
                return False
        
        # Check for past tense statements that aren't recurring tasks
        past_tense_indicators = {"did", "went", "was", "were", "had", "bought", "got", "did"}
        # But allow past tense with recurring indicators
        recurring_indicators = {"every", "always", "usually", "typically", "regularly"}
        if any(indicator in lowered for indicator in past_tense_indicators) and not any(r in lowered for r in recurring_indicators):
            return False
        
        # Check for opinion/statements
        opinion_words = {"feel like", "seems like", "looks like", "sounds like", "kind of", "sort of"}
        if any(word in lowered for word in opinion_words):
            return False
        
        return True

    def _clean_item_text(self, text: str) -> str:
        cleaned = re.sub(r"\s+", " ", text.strip().lower())
        cleaned = re.sub(r"^(please\s+|uh\s+|um\s+)", "", cleaned).strip()
        cleaned = cleaned.strip(" .!?")
        words = cleaned.split()
        while words and words[-1] in TRAILING_FILLER_WORDS:
            words.pop()
        return " ".join(words).strip()

    def _is_recent_duplicate(self, list_type: str, text: str) -> bool:
        key = (list_type, text)
        return key in self.recent_additions


    def _remember_item(self, list_type: str, text: str) -> None:
        self.recent_additions.append((list_type, text))
        if len(self.recent_additions) > 30:
            self.recent_additions = self.recent_additions[-30:]

    def _resolve_vosk_model_path(self) -> Path | None:
        for model_path in VOSK_MODEL_CANDIDATES:
            if model_path.exists() and model_path.is_dir():
                return model_path
        return None

    def _ensure_model_loaded(self) -> None:
        with self.model_lock:
            if self.vosk_model:
                return
            if not self.vosk_model_path:
                return
            self.is_model_loading = True
        self._append_log(f"loading vosk model: {self.vosk_model_path.name}")
        try:
            loaded_model = Model(str(self.vosk_model_path))
            with self.model_lock:
                self.vosk_model = loaded_model
            self._append_log("vosk model loaded")
        finally:
            with self.model_lock:
                self.is_model_loading = False

    def preload_model_if_available(self) -> None:
        if self.vosk_model:
            return
        model_path = self._resolve_vosk_model_path()
        if not model_path:
            return
        self.vosk_model_path = model_path
        try:
            self._ensure_model_loaded()
        except Exception as exc:
            self._append_log(f"vosk preload error: {exc}")

    def _get_ollama_status(self) -> str:
        now = time.time()
        if now - self.ollama_last_checked_at < self.ollama_check_interval_seconds:
            return self.ollama_status
        self.ollama_last_checked_at = now
        try:
            response = requests.get("http://127.0.0.1:11434/api/version", timeout=0.8)
            response.raise_for_status()
            self.ollama_status = "connected"
        except Exception:
            self.ollama_status = "disconnected"
        return self.ollama_status


agent = LocalAgentApp()
app = FastAPI(title="Voice Grocery/Todo Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.on_event("startup")
def on_startup() -> None:
    """Startup event handler"""
    threading.Thread(target=agent.preload_model_if_available, daemon=True).start()
    
    # Auto-start listening if enabled
    if AUTO_START_LISTENING:
        def auto_start():
            time.sleep(3)  # Wait for model to preload
            try:
                agent.start()
                agent._append_log("auto-started listening")
            except RuntimeError as e:
                agent._append_log(f"auto-start failed: {e}")
        threading.Thread(target=auto_start, daemon=True).start()
    
    # Auto-open browser in desktop mode
    if getattr(sys, 'frozen', False):
        # Running as packaged executable
        threading.Thread(target=open_browser_delayed, daemon=True).start()

def open_browser_delayed() -> None:
    """Open browser after a short delay to ensure server is ready"""
    time.sleep(2)
    webbrowser.open("http://127.0.0.1:8000")


class AddItemRequest(BaseModel):
    text: str
    list_type: str
    priority: int = 1


class ConfirmPendingRequest(BaseModel):
    list_type: str
    priority: int = 1


class ConfirmAllPendingRequest(BaseModel):
    list_type: str
    priority: int = 1


class UpdatePriorityRequest(BaseModel):
    priority: int


class SortRequest(BaseModel):
    sort_by: str = "priority"


@app.get("/", response_class=HTMLResponse)
def root() -> str:
    return Path("templates/index.html").read_text(encoding="utf-8")


@app.get("/api/lists", response_model=ListsResponse)
def get_lists() -> Dict[str, Any]:
    return agent.get_lists()


@app.post("/api/list-items")
def add_item(req: AddItemRequest) -> Dict[str, Any]:
    try:
        return agent.add_manual_item(req.text, req.list_type)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@app.post("/api/list-items/{item_id}/toggle")
def toggle_item(item_id: int) -> Dict[str, str]:
    try:
        agent.toggle_item(item_id)
        return {"status": "ok"}
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err


@app.delete("/api/list-items/{item_id}")
def delete_item(item_id: int) -> Dict[str, str]:
    try:
        agent.remove_item(item_id)
        return {"status": "ok"}
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err


@app.post("/api/listening/start")
def start_listening() -> Dict[str, str]:
    try:
        agent.start()
        return {"status": "started"}
    except RuntimeError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@app.post("/api/listening/stop")
def stop_listening() -> Dict[str, str]:
    agent.stop()
    return {"status": "stopped"}


@app.post("/api/transcript/clear")
def clear_transcript() -> Dict[str, str]:
    agent.clear_transcript_log()
    return {"status": "ok"}


@app.post("/api/pending/{pending_id}/confirm")
def confirm_pending(pending_id: int, req: ConfirmPendingRequest) -> Dict[str, Any]:
    try:
        return agent.confirm_pending_item(pending_id, req.list_type)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@app.delete("/api/pending/{pending_id}")
def remove_pending(pending_id: int) -> Dict[str, str]:
    try:
        agent.remove_pending_item(pending_id)
        return {"status": "ok"}
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err


@app.post("/api/pending/clear")
def clear_pending() -> Dict[str, str]:
    agent.clear_pending_items()
    return {"status": "ok"}


@app.post("/api/pending/confirm-all")
def confirm_all_pending(req: ConfirmAllPendingRequest) -> Dict[str, Any]:
    try:
        count = agent.confirm_all_pending_items(req.list_type, req.priority)
        return {"status": "ok", "moved_count": count}
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@app.put("/api/list-items/{item_id}/priority")
def update_item_priority(item_id: int, req: UpdatePriorityRequest) -> Dict[str, str]:
    try:
        agent.update_item_priority(item_id, req.priority)
        return {"status": "ok"}
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@app.post("/api/lists/{list_type}/sort")
def sort_list(list_type: str, req: SortRequest) -> Dict[str, str]:
    try:
        agent.sort_list(list_type, req.sort_by)
        return {"status": "ok"}
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@app.get("/api/setup/status")
def get_setup_status() -> Dict[str, Any]:
    """Get the status of required dependencies"""
    # Check Vosk models
    vosk_available = agent._resolve_vosk_model_path() is not None
    
    # Check Ollama
    ollama_connected = agent._get_ollama_status() == "connected"
    
    # Check if running as packaged app
    is_packaged = getattr(sys, 'frozen', False)
    
    return {
        "vosk_available": vosk_available,
        "ollama_connected": ollama_connected,
        "is_packaged": is_packaged,
        "vosk_model_path": str(agent.vosk_model_path) if agent.vosk_model_path else None,
    }


@app.post("/api/setup/run")
def run_setup() -> Dict[str, Any]:
    """Run the setup wizard (if available)"""
    try:
        # Import setup wizard if available
        try:
            from setup_wizard import SetupWizard
            wizard = SetupWizard()
            # Run in background thread
            def run_wizard():
                wizard.run_setup(auto_download=True)
            threading.Thread(target=run_wizard, daemon=True).start()
            return {"status": "started", "message": "Setup wizard started"}
        except ImportError:
            return {"status": "unavailable", "message": "Setup wizard not available"}
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err)) from err


if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)

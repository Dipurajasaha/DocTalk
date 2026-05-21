#!/usr/bin/env python3
"""
Cleanup script to clear old conversations and keep only the last 10 per account.

Usage: python cleanup_old_conversations.py
"""

import os
import json
import shutil
from pathlib import Path

DATA_ROOT = os.path.join(os.path.dirname(__file__), "..", "data")
PATIENT_DATA_ROOT = os.path.join(DATA_ROOT, "patients")
DOCTOR_DATA_ROOT = os.path.join(DATA_ROOT, "doctors")

MAX_CONVERSATIONS = 10


def cleanup_patient_chats():
    """Trim patient chat_sessions.json to keep only last 10 conversations."""
    if not os.path.exists(PATIENT_DATA_ROOT):
        print(f"❌ Patient data directory not found: {PATIENT_DATA_ROOT}")
        return
    
    cleaned = 0
    for username in os.listdir(PATIENT_DATA_ROOT):
        user_dir = os.path.join(PATIENT_DATA_ROOT, username)
        chat_file = os.path.join(user_dir, "chat_sessions.json")
        
        if os.path.isfile(chat_file):
            try:
                with open(chat_file, "r", encoding="utf-8") as f:
                    sessions = json.load(f)
                
                if isinstance(sessions, list) and len(sessions) > MAX_CONVERSATIONS:
                    old_count = len(sessions)
                    sessions = sessions[-MAX_CONVERSATIONS:]
                    
                    with open(chat_file, "w", encoding="utf-8") as f:
                        json.dump(sessions, f, ensure_ascii=False, indent=2)
                    
                    print(f"✓ Patient '{username}': trimmed {old_count} → {len(sessions)} sessions")
                    cleaned += 1
            except Exception as e:
                print(f"⚠ Error processing {username}: {e}")
    
    print(f"\n✅ Cleaned up {cleaned} patient accounts\n")


def cleanup_doctor_chats():
    """Trim doctor assistant_chat.json and patient_chats.json to keep only last 10 per patient."""
    if not os.path.exists(DOCTOR_DATA_ROOT):
        print(f"❌ Doctor data directory not found: {DOCTOR_DATA_ROOT}")
        return
    
    cleaned = 0
    for doctor_id in os.listdir(DOCTOR_DATA_ROOT):
        doctor_dir = os.path.join(DOCTOR_DATA_ROOT, doctor_id)
        
        # Cleanup assistant_chat.json
        assistant_file = os.path.join(doctor_dir, "assistant_chat.json")
        if os.path.isfile(assistant_file):
            try:
                with open(assistant_file, "r", encoding="utf-8") as f:
                    chats = json.load(f)
                
                if isinstance(chats, list) and len(chats) > MAX_CONVERSATIONS:
                    old_count = len(chats)
                    chats = chats[-MAX_CONVERSATIONS:]
                    
                    with open(assistant_file, "w", encoding="utf-8") as f:
                        json.dump(chats, f, ensure_ascii=False, indent=2)
                    
                    print(f"✓ Doctor '{doctor_id}' assistant_chat: trimmed {old_count} → {len(chats)} conversations")
                    cleaned += 1
            except Exception as e:
                print(f"⚠ Error processing assistant_chat for {doctor_id}: {e}")
        
        # Cleanup patient_chats.json
        patient_chats_file = os.path.join(doctor_dir, "patient_chats.json")
        if os.path.isfile(patient_chats_file):
            try:
                with open(patient_chats_file, "r", encoding="utf-8") as f:
                    patient_chats = json.load(f)
                
                if isinstance(patient_chats, dict):
                    trimmed_any = False
                    for patient_id in patient_chats:
                        if isinstance(patient_chats[patient_id], list) and len(patient_chats[patient_id]) > MAX_CONVERSATIONS:
                            old_count = len(patient_chats[patient_id])
                            patient_chats[patient_id] = patient_chats[patient_id][-MAX_CONVERSATIONS:]
                            print(f"✓ Doctor '{doctor_id}' with patient '{patient_id}': trimmed {old_count} → {len(patient_chats[patient_id])} messages")
                            trimmed_any = True
                    
                    if trimmed_any:
                        with open(patient_chats_file, "w", encoding="utf-8") as f:
                            json.dump(patient_chats, f, ensure_ascii=False, indent=2)
                        cleaned += 1
            except Exception as e:
                print(f"⚠ Error processing patient_chats for {doctor_id}: {e}")
    
    print(f"\n✅ Cleaned up {cleaned} doctor accounts\n")


def main():
    print("=" * 60)
    print("🧹 Conversation Cleanup - Keep Last 10 Per Account")
    print("=" * 60 + "\n")
    
    print("Cleaning patient conversations...")
    cleanup_patient_chats()
    
    print("Cleaning doctor conversations...")
    cleanup_doctor_chats()
    
    print("=" * 60)
    print("✅ Cleanup Complete! All accounts now limited to 10 conversations.")
    print("=" * 60)


if __name__ == "__main__":
    main()

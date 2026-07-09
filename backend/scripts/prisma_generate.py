"""
Run this script to regenerate the Prisma client after schema changes.
It generates the client and copies all generated files into the local venv.

Usage (from DocTalk/ folder):
    .venv/Scripts/python.exe backend/scripts/prisma_generate.py
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = REPO_ROOT / "backend" / "prisma" / "schema.prisma"
VENV_PRISMA = REPO_ROOT / ".venv" / "Lib" / "site-packages" / "prisma"


def find_global_prisma() -> Path | None:
    """Locate the global Python's prisma site-packages directory."""
    result = subprocess.run(
        ["python", "-c", "import prisma; import os; print(os.path.dirname(prisma.__file__))"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        p = Path(result.stdout.strip())
        if p.exists():
            return p

    # Fallback: look in known global locations
    for candidate in Path(sys.executable).parents:
        for sub in candidate.rglob("prisma/__init__.py"):
            return sub.parent
    return None


def main():
    print(f"Schema: {SCHEMA}")
    print(f"Venv prisma: {VENV_PRISMA}")

    # 1. Run prisma generate
    print("\n→ Running prisma generate…")
    result = subprocess.run(
        [sys.executable, "-m", "prisma", "generate", "--schema", str(SCHEMA)],
        cwd=str(REPO_ROOT),
    )
    if result.returncode != 0:
        print("✗ prisma generate failed")
        sys.exit(1)

    # 2. Find where files were generated (may be global Python)
    global_prisma = find_global_prisma()
    if not global_prisma:
        print("✗ Could not find global prisma package")
        sys.exit(1)

    generated_files = [
        "client.py", "models.py", "partials.py", "types.py",
        "enums.py", "actions.py", "bases.py", "http.py", "metadata.py",
    ]

    # 3. Copy into venv if different location
    if global_prisma.resolve() != VENV_PRISMA.resolve():
        print(f"\n→ Copying generated files from {global_prisma} → {VENV_PRISMA}")
        copied = 0
        for fname in generated_files:
            src = global_prisma / fname
            if src.exists():
                shutil.copy2(src, VENV_PRISMA / fname)
                print(f"  ✓ {fname}")
                copied += 1
        print(f"  Copied {copied} file(s)")
    else:
        print("  Generated directly into venv — no copy needed")

    # 4. Verify
    print("\n→ Verifying import…")
    check = subprocess.run(
        [str(REPO_ROOT / ".venv" / "Scripts" / "python.exe"),
         "-c", "from prisma import Prisma; print('  ✓ Prisma client OK')"],
        cwd=str(REPO_ROOT),
    )
    if check.returncode != 0:
        print("✗ Import check failed — check errors above")
        sys.exit(1)

    print("\n✅ Done — Prisma client is ready.")


if __name__ == "__main__":
    main()

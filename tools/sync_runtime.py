from pathlib import Path
import shutil


ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT / "energy_ledger"
TARGET=ROOT / "energy-ledger" / "rootfs" / "usr" / "src" / "app" / "energy_ledger"


def main():
	TARGET.mkdir(parents=True, exist_ok=True)
	for source in SOURCE.rglob("*"):
		if not source.is_file() or "__pycache__" in source.parts:
			continue
		relative=source.relative_to(SOURCE)
		destination=TARGET / relative
		destination.parent.mkdir(parents=True, exist_ok=True)
		shutil.copy2(source, destination)


if __name__ == "__main__":
	main()

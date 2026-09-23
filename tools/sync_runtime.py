from pathlib import Path
import shutil


ROOT=Path(__file__).resolve().parents[1]
PACKAGES=(
	("energy_ledger", "energy-ledger"),
	("battery_charge_controller", "battery-charge-controller"),
)


def sync_package(source_name: str, app_name: str):
	source_root=ROOT / source_name
	target_root=ROOT / app_name / "rootfs" / "usr" / "src" / "app" / source_name
	if not target_root.resolve().is_relative_to(ROOT.resolve()):
		raise RuntimeError(f"Generated target escapes repository: {target_root}")
	target_root.mkdir(parents=True, exist_ok=True)
	expected=set()
	for source in source_root.rglob("*"):
		if not source.is_file() or "__pycache__" in source.parts:
			continue
		relative=source.relative_to(source_root)
		expected.add(relative)
		destination=target_root / relative
		destination.parent.mkdir(parents=True, exist_ok=True)
		shutil.copy2(source, destination)
	for generated in sorted(target_root.rglob("*"), reverse=True):
		if generated.is_file() and generated.relative_to(target_root) not in expected:
			generated.unlink()
		elif generated.is_dir() and not any(generated.iterdir()):
			generated.rmdir()


def main():
	for source_name,app_name in PACKAGES:
		sync_package(source_name, app_name)


if __name__ == "__main__":
	main()

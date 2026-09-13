import rdkit, openff.toolkit, openmm, meeko, subprocess, os
v = subprocess.run(["vina", "--version"], capture_output=True, text=True).stdout.strip().splitlines()[0]
print(f"vina: {v}")
print(f"rdkit {rdkit.__version__} | openff {openff.toolkit.__version__} | "
      f"openmm {openmm.version.version} | meeko {meeko.__version__}")
print(f"cores: {os.cpu_count()} | MOLDESIGN_LAB={os.environ.get('MOLDESIGN_LAB')}")

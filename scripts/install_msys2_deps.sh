#!/bin/bash
# Install MSYS2 dependencies for Smina compilation
echo "=== MSYS2 Smina deps install ==="
echo "Time: $(date)"
pacman --noconfirm -Syu
pacman --noconfirm -S mingw-w64-x86_64-cmake mingw-w64-x86_64-openbabel mingw-w64-x86_64-eigen3
echo "=== Done: $(date) ==="

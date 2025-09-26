{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = with pkgs; [
    python3
    python3Packages.pip
    # additional tools for data processing
    jq
    csvkit
    gnumeric  # for ssconvert utility
  ];

  shellHook = ''
    echo "Python environment loaded for match_names.py"
    echo "Python version: $(python3 --version)"
    echo "Available tools: python3, pip, jq, csvkit, ssconvert"
    echo "Project directory: $(pwd)"
  '';
}

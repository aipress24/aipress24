{
  description = "Abilian development environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable"; # Using nixos-unstable directly
    nixpkgs-old.url = "github:NixOS/nixpkgs/96e18717904dfedcd884541e5a92bf9ff632cf39";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, nixpkgs-old, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
        };
        pkgs-old = import nixpkgs-old {
          inherit system;
        };

      in
      {
        devShells.default = pkgs.mkShell {
          name = "abilian-env";
          buildInputs = with pkgs; [
            python310
            python311
            python312
            poetry

            # Allow installation of binary wheels by (a) providing manylinux2014
            # support, and (b) patching binaries installed into the Poetry virtualenv.
            autoPatchelfHook
            pythonManylinuxPackages.manylinux2014
          ];
          shellHook = ''
            # Create a poetry environment using python3.10
            poetry env use "${pkgs.python310}/bin/python3"

            # Check if the environment exists, and install/update if it doesn't or is outdated.
            # The lock file check isn't perfect, but significantly reduces redundant installs.
            if [[ ! -f "$(poetry env info --path)/pyproject.toml" ]] || [[ "$(poetry env info --path)/poetry.lock" -ot "poetry.lock" ]]; then
              echo "Creating or updating Poetry environment..."
              poetry install --sync --with=dev
            else
              echo "Poetry environment is up-to-date."
            fi

            # Patch binaries in the Poetry virtualenv to link against Nix deps
            autoPatchelf "$(poetry env info --path)"

            # Activate the Poetry environment
            source "$(poetry env info --path)/bin/activate"
          '';
        };
      }
    );
}


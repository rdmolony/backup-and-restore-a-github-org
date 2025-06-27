{
  inputs = {
    utils.url = "github:numtide/flake-utils";
    claude-sync = {
      url = "github:rdmolony/sync-claude-code-with-github-issues/sync-deterministically";
      inputs.utils.follows = "utils";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };
  outputs = { self, nixpkgs, utils, ... }@inputs: utils.lib.eachDefaultSystem (system:
    let
      pkgs = nixpkgs.legacyPackages.${system};
      claude-sync = inputs.claude-sync.packages.${system}.default;
    in
    {
      devShell = pkgs.mkShell {
        buildInputs = with pkgs; [
          claude-sync
          python3
        ];
      };
    }
  );
}

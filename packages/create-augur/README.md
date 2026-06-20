# create-augur

`create-augur` is the shell fallback for users who want the full repo-first workspace. The public fast-launch promise is: Get to know your AI setup, build your local second brain, and talk with your projects. The desktop-chat install prompt asks "Which folder should I initialize?", then runs `uv run aug init --project <folder>` from the Augur install directory to create `project-brain/` and refresh the read-only AI artifact inventory. Next action: Ask Augur about this project.

## Usage

```bash
npx create-augur@latest my-brain
cd my-brain
uv run aug init --project .
```

`create-augur` clones Augur, initializes a fresh git repository, and installs Python and Node dependencies when available with `uv` and `pnpm`.

## Links

- Website: https://augur.run
- GitHub: https://github.com/augur-os/augur-os

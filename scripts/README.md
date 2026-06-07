Scripts to quickly start/stop the development environment

Usage

- Make scripts executable (one-time):

```bash
chmod +x scripts/*.sh
```

- Start both backend and frontend (background):

```bash
./scripts/start.sh
```

- Stop them:

```bash
./scripts/stop.sh
```

Notes
- `start.sh` uses the first available `python3` in your PATH. If you prefer a specific interpreter, set the `PYTHON_CMD` at the top of the script or run with `PYTHON_CMD=/path/to/python ./scripts/start.sh`.
- The frontend uses `npm --prefix frontend run dev`; ensure `npm install` has been run beforehand.
- Logs are saved to `/tmp/real-estate-ai-backend.log` and `/tmp/real-estate-ai-frontend.log`.
- Backend defaults to port `8000` (unless you override `PORT`).

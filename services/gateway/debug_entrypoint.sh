#!/bin/sh
# Usado em dev: DEBUG_PORT set → inicia debugpy, caso contrário usa uvicorn normal
if [ -n "$DEBUG_PORT" ]; then
  echo "[debug] debugpy aguardando VS Code na porta $DEBUG_PORT..."
  exec python -m debugpy --listen 0.0.0.0:$DEBUG_PORT \
    -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
else
  exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload
fi

FROM e2b/code-interpreter-v1

# Pre-install opencode so sandboxes start immediately without an install step
RUN npm install -g opencode-ai@latest

FROM e2b/code-interpreter-v1

# Pre-install opencode so sandboxes start immediately without an install step
RUN npm install -g opencode-ai@latest

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Pre-install bot Python deps
RUN uv pip install --system python-telegram-bot pydantic-settings
